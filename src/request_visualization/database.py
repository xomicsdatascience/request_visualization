# Database operations for agent requests.
# Provides functions to create, read, update, and manage agent requests
# including status transitions (approve, reject, complete, cancel, revise).

import sqlite3
import struct
from datetime import datetime
from pathlib import Path

import httpx

from .models import AgentRequest

DEFAULT_DB_PATH = Path("./articles.sqlite")
DEFAULT_ENDPOINT_FILE = Path.home() / ".claude" / "azure.endpoint"
DEFAULT_API_KEY_FILE = Path.home() / ".claude" / "azure.key"
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"

# Valid request statuses
VALID_STATUSES = ("pending", "approved", "rejected", "implemented", "completed", "cancelled")

# Inactive statuses (requests that don't need attention)
INACTIVE_STATUSES = ("completed", "rejected", "cancelled")


def get_connection(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Create a database connection.

    Parameters
    ----------
    db_path : Path
        Path to the SQLite database file.

    Returns
    -------
    sqlite3.Connection
        Database connection object.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_table_exists(db_path: Path = DEFAULT_DB_PATH) -> None:
    """Create the agent_requests table if it doesn't exist.

    The table supports the following statuses:
    - pending: Initial state, awaiting review
    - approved: Approved for implementation
    - rejected: Rejected with a reason
    - implemented: Implementation completed, awaiting verification
    - completed: Implementation verified and accepted
    - cancelled: Cancelled after implementation

    Parameters
    ----------
    db_path : Path
        Path to the SQLite database file.
    """
    conn = get_connection(db_path)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS agent_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_name TEXT NOT NULL,
                creation_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                request TEXT NOT NULL,
                reason_for_request TEXT,
                request_status TEXT DEFAULT 'pending'
                    CHECK (request_status IN ('pending', 'approved', 'rejected', 'implemented', 'completed', 'cancelled')),
                status_reason TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                embedding BLOB,
                embedding_model VARCHAR(100)
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_agent_requests_status "
            "ON agent_requests(request_status)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_agent_requests_creation "
            "ON agent_requests(creation_time)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_agent_requests_agent "
            "ON agent_requests(agent_name)"
        )
        conn.commit()
    finally:
        conn.close()


def _row_to_request(row: sqlite3.Row) -> AgentRequest:
    """Convert a database row to an AgentRequest object.

    Parameters
    ----------
    row : sqlite3.Row
        Database row with agent request data.

    Returns
    -------
    AgentRequest
        AgentRequest object populated from the row.
    """
    creation_time = row["creation_time"]
    if isinstance(creation_time, str):
        creation_time = datetime.fromisoformat(creation_time)
    updated_at = row["updated_at"]
    if isinstance(updated_at, str):
        updated_at = datetime.fromisoformat(updated_at)
    assigned_time = row["assigned_time"]
    if isinstance(assigned_time, str):
        assigned_time = datetime.fromisoformat(assigned_time)

    return AgentRequest(
        id=row["id"],
        agent_name=row["agent_name"],
        creation_time=creation_time,
        request=row["request"],
        reason_for_request=row["reason_for_request"],
        request_status=row["request_status"],
        status_reason=row["status_reason"],
        updated_at=updated_at,
        assigned_time=assigned_time,
        embedding=row["embedding"],
        embedding_model=row["embedding_model"],
    )


def get_pending_requests(db_path: Path = DEFAULT_DB_PATH) -> list[AgentRequest]:
    """Fetch all pending requests, ordered by creation time (oldest first).

    Parameters
    ----------
    db_path : Path
        Path to the SQLite database file.

    Returns
    -------
    list[AgentRequest]
        List of pending agent requests.
    """
    conn = get_connection(db_path)
    try:
        cursor = conn.execute(
            """
            SELECT id, agent_name, creation_time, request, reason_for_request,
                   request_status, status_reason, updated_at, assigned_time,
                   embedding, embedding_model
            FROM agent_requests
            WHERE request_status = 'pending'
            ORDER BY creation_time ASC
            """
        )
        return [_row_to_request(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_all_requests(
    db_path: Path = DEFAULT_DB_PATH, status_filter: str | None = None
) -> list[AgentRequest]:
    """Fetch all requests with optional status filter.

    Parameters
    ----------
    db_path : Path
        Path to the SQLite database file.
    status_filter : str | None
        Optional status to filter by ('pending', 'approved', 'rejected',
        'implemented', 'completed', 'cancelled').

    Returns
    -------
    list[AgentRequest]
        List of agent requests matching the filter.
    """
    conn = get_connection(db_path)
    try:
        if status_filter:
            cursor = conn.execute(
                """
                SELECT id, agent_name, creation_time, request, reason_for_request,
                       request_status, status_reason, updated_at, assigned_time,
                       embedding, embedding_model
                FROM agent_requests
                WHERE request_status = ?
                ORDER BY creation_time ASC
                """,
                (status_filter,),
            )
        else:
            cursor = conn.execute(
                """
                SELECT id, agent_name, creation_time, request, reason_for_request,
                       request_status, status_reason, updated_at, assigned_time,
                       embedding, embedding_model
                FROM agent_requests
                ORDER BY creation_time ASC
                """
            )
        return [_row_to_request(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_active_requests(db_path: Path = DEFAULT_DB_PATH) -> list[AgentRequest]:
    """Fetch all active requests (not completed, rejected, or cancelled).

    Active requests are those that may still require attention: pending,
    approved, in_progress, or implemented.

    Parameters
    ----------
    db_path : Path
        Path to the SQLite database file.

    Returns
    -------
    list[AgentRequest]
        List of active agent requests.
    """
    conn = get_connection(db_path)
    try:
        placeholders = ",".join("?" for _ in INACTIVE_STATUSES)
        cursor = conn.execute(
            f"""
            SELECT id, agent_name, creation_time, request, reason_for_request,
                   request_status, status_reason, updated_at, assigned_time,
                   embedding, embedding_model
            FROM agent_requests
            WHERE request_status NOT IN ({placeholders})
            ORDER BY creation_time ASC
            """,
            INACTIVE_STATUSES,
        )
        return [_row_to_request(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def approve_request(
    request_id: int, reason: str | None = None, db_path: Path = DEFAULT_DB_PATH
) -> bool:
    """Approve a request by setting its status to 'approved'.

    Parameters
    ----------
    request_id : int
        ID of the request to approve.
    reason : str | None
        Optional reason for the approval.
    db_path : Path
        Path to the SQLite database file.

    Returns
    -------
    bool
        True if the request was updated, False if not found.
    """
    conn = get_connection(db_path)
    try:
        cursor = conn.execute(
            """
            UPDATE agent_requests
            SET request_status = 'approved',
                status_reason = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (reason, request_id),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def reject_request(
    request_id: int, reason: str, db_path: Path = DEFAULT_DB_PATH
) -> bool:
    """Reject a request by setting its status to 'rejected' with a reason.

    Parameters
    ----------
    request_id : int
        ID of the request to reject.
    reason : str
        Reason for the rejection.
    db_path : Path
        Path to the SQLite database file.

    Returns
    -------
    bool
        True if the request was updated, False if not found.
    """
    conn = get_connection(db_path)
    try:
        cursor = conn.execute(
            """
            UPDATE agent_requests
            SET request_status = 'rejected',
                status_reason = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (reason, request_id),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def complete_request(
    request_id: int, reason: str | None = None, db_path: Path = DEFAULT_DB_PATH
) -> bool:
    """Mark a request as completed (implementation verified and accepted).

    Parameters
    ----------
    request_id : int
        ID of the request to mark as completed.
    reason : str | None
        Optional reason/notes for completion.
    db_path : Path
        Path to the SQLite database file.

    Returns
    -------
    bool
        True if the request was updated, False if not found.
    """
    conn = get_connection(db_path)
    try:
        cursor = conn.execute(
            """
            UPDATE agent_requests
            SET request_status = 'completed',
                status_reason = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (reason, request_id),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def cancel_request(
    request_id: int, reason: str | None = None, db_path: Path = DEFAULT_DB_PATH
) -> bool:
    """Cancel a request by setting its status to 'cancelled'.

    Parameters
    ----------
    request_id : int
        ID of the request to cancel.
    reason : str | None
        Optional reason for cancellation.
    db_path : Path
        Path to the SQLite database file.

    Returns
    -------
    bool
        True if the request was updated, False if not found.
    """
    conn = get_connection(db_path)
    try:
        cursor = conn.execute(
            """
            UPDATE agent_requests
            SET request_status = 'cancelled',
                status_reason = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (reason, request_id),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def revise_request(
    request_id: int,
    new_request_text: str,
    db_path: Path = DEFAULT_DB_PATH,
    embedding_model: str = DEFAULT_EMBEDDING_MODEL,
) -> bool:
    """Revise a request's text and set its status back to 'approved'.

    This is used when an implemented request needs modifications. The request
    text is updated and status is set to 'approved' so it can be re-implemented.
    A new embedding is generated for the updated text.

    Parameters
    ----------
    request_id : int
        ID of the request to revise.
    new_request_text : str
        The updated request text.
    db_path : Path
        Path to the SQLite database file.
    embedding_model : str
        Name of the embedding model to use for the new text.

    Returns
    -------
    bool
        True if the request was updated, False if not found or update failed.
    """
    # Generate new embedding for the revised text
    try:
        embedding = get_text_embedding(new_request_text, deployment_name=embedding_model)
        embedding_blob = _embedding_to_blob(embedding)
    except Exception:
        # If embedding fails, still update the request but without new embedding
        embedding_blob = None

    conn = get_connection(db_path)
    try:
        if embedding_blob:
            cursor = conn.execute(
                """
                UPDATE agent_requests
                SET request = ?,
                    request_status = 'approved',
                    status_reason = 'Revised for re-implementation',
                    updated_at = CURRENT_TIMESTAMP,
                    embedding = ?,
                    embedding_model = ?
                WHERE id = ?
                """,
                (new_request_text, embedding_blob, embedding_model, request_id),
            )
        else:
            cursor = conn.execute(
                """
                UPDATE agent_requests
                SET request = ?,
                    request_status = 'approved',
                    status_reason = 'Revised for re-implementation',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (new_request_text, request_id),
            )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def get_request_by_id(
    request_id: int, db_path: Path = DEFAULT_DB_PATH
) -> AgentRequest | None:
    """Fetch a single request by its ID.

    Parameters
    ----------
    request_id : int
        ID of the request to fetch.
    db_path : Path
        Path to the SQLite database file.

    Returns
    -------
    AgentRequest | None
        The request if found, None otherwise.
    """
    conn = get_connection(db_path)
    try:
        cursor = conn.execute(
            """
            SELECT id, agent_name, creation_time, request, reason_for_request,
                   request_status, status_reason, updated_at, assigned_time,
                   embedding, embedding_model
            FROM agent_requests
            WHERE id = ?
            """,
            (request_id,),
        )
        row = cursor.fetchone()
        return _row_to_request(row) if row else None
    finally:
        conn.close()


def _embedding_to_blob(embedding: list[float]) -> bytes:
    """Convert an embedding list to a binary blob.

    Parameters
    ----------
    embedding : list[float]
        List of floats representing the embedding vector.

    Returns
    -------
    bytes
        Binary representation of the embedding.
    """
    return struct.pack(f"{len(embedding)}f", *embedding)


def _get_azure_credentials(
    endpoint_file: Path | None = None,
    api_key_file: Path | None = None,
) -> tuple[str, str]:
    """Get Azure OpenAI credentials from files.

    Parameters
    ----------
    endpoint_file : Path | None
        Path to file containing the Azure OpenAI endpoint URL.
    api_key_file : Path | None
        Path to file containing the Azure OpenAI API key.

    Returns
    -------
    tuple[str, str]
        Tuple of (endpoint, api_key).

    Raises
    ------
    FileNotFoundError
        If credential files cannot be found.
    """
    endpoint_path = endpoint_file or DEFAULT_ENDPOINT_FILE
    api_key_path = api_key_file or DEFAULT_API_KEY_FILE

    if not endpoint_path.exists():
        raise FileNotFoundError(f"Endpoint file not found: {endpoint_path}")
    if not api_key_path.exists():
        raise FileNotFoundError(f"API key file not found: {api_key_path}")

    endpoint = endpoint_path.read_text().strip()
    api_key = api_key_path.read_text().strip()

    return endpoint, api_key


def get_text_embedding(
    text: str,
    endpoint_file: Path | None = None,
    api_key_file: Path | None = None,
    deployment_name: str = DEFAULT_EMBEDDING_MODEL,
    api_version: str = "2024-02-01",
) -> list[float]:
    """Get text embedding from Azure OpenAI synchronously.

    Parameters
    ----------
    text : str
        The text to embed.
    endpoint_file : Path | None
        Path to file containing the Azure OpenAI endpoint URL.
    api_key_file : Path | None
        Path to file containing the Azure OpenAI API key.
    deployment_name : str
        Name of the embedding model deployment in Azure.
    api_version : str
        Azure OpenAI API version.

    Returns
    -------
    list[float]
        List of floats representing the embedding vector.

    Raises
    ------
    httpx.HTTPError
        If the API request fails.
    """
    endpoint, api_key = _get_azure_credentials(endpoint_file, api_key_file)

    url = f"{endpoint}/openai/deployments/{deployment_name}/embeddings"
    params = {"api-version": api_version}
    headers = {"api-key": api_key, "Content-Type": "application/json"}
    payload = {"input": text}

    with httpx.Client() as client:
        response = client.post(
            url, params=params, headers=headers, json=payload, timeout=30.0
        )
        response.raise_for_status()
        data = response.json()

    return data["data"][0]["embedding"]


def create_request(
    agent_name: str,
    request: str,
    reason_for_request: str | None = None,
    db_path: Path = DEFAULT_DB_PATH,
    embedding_model: str = DEFAULT_EMBEDDING_MODEL,
) -> int | None:
    """Create a new agent request in the database with an embedding.

    Parameters
    ----------
    agent_name : str
        Name of the agent creating the request.
    request : str
        The request text/content.
    reason_for_request : str | None
        Optional reason explaining why the request was made.
    db_path : Path
        Path to the SQLite database file.
    embedding_model : str
        Name of the embedding model to use.

    Returns
    -------
    int | None
        The ID of the newly created request, or None if creation failed.

    Raises
    ------
    Exception
        If embedding generation or database insertion fails.
    """
    # Generate embedding first
    embedding = get_text_embedding(request, deployment_name=embedding_model)
    embedding_blob = _embedding_to_blob(embedding)

    conn = get_connection(db_path)
    try:
        cursor = conn.execute(
            """
            INSERT INTO agent_requests
                (agent_name, request, reason_for_request, embedding, embedding_model)
            VALUES (?, ?, ?, ?, ?)
            """,
            (agent_name, request, reason_for_request, embedding_blob, embedding_model),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def set_request_status(
    request_id: int,
    status: str,
    reason: str | None = None,
    db_path: Path = DEFAULT_DB_PATH,
) -> bool:
    """Set the status of a request to any valid status.

    Parameters
    ----------
    request_id : int
        ID of the request to update.
    status : str
        New status value. Must be one of: 'pending', 'approved', 'rejected',
        'implemented', 'completed', 'cancelled'.
    reason : str | None
        Optional reason for the status change.
    db_path : Path
        Path to the SQLite database file.

    Returns
    -------
    bool
        True if the request was updated, False if not found or invalid status.
    """
    if status not in VALID_STATUSES:
        return False

    conn = get_connection(db_path)
    try:
        cursor = conn.execute(
            """
            UPDATE agent_requests
            SET request_status = ?,
                status_reason = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (status, reason, request_id),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def update_request_embedding(
    request_id: int,
    embedding: bytes,
    model: str,
    db_path: Path = DEFAULT_DB_PATH,
) -> bool:
    """Update the embedding for a request.

    Parameters
    ----------
    request_id : int
        ID of the request to update.
    embedding : bytes
        The embedding vector as bytes.
    model : str
        Name of the model used to generate the embedding.
    db_path : Path
        Path to the SQLite database file.

    Returns
    -------
    bool
        True if the request was updated, False if not found.
    """
    conn = get_connection(db_path)
    try:
        cursor = conn.execute(
            """
            UPDATE agent_requests
            SET embedding = ?,
                embedding_model = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (embedding, model, request_id),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()
