# Standalone migration for the agent_requests table.
# Brings an existing articles.sqlite agent_requests table up to the canonical
# schema (odda_utils/src/odda_utils/static/schema.sql): adds the assigned_time
# column when missing and rebuilds the table when its request_status CHECK
# constraint does not allow all eight canonical statuses. The migration is
# idempotent and safe to run repeatedly. Exposed as the ``request-viz-migrate``
# console script via its ``main`` function.

import argparse
import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path("./articles.sqlite")

# Canonical column set for agent_requests, in schema order. Used to copy data
# across a table rebuild.
CANONICAL_COLUMNS = (
    "id",
    "agent_name",
    "creation_time",
    "request",
    "reason_for_request",
    "request_status",
    "status_reason",
    "assigned_time",
    "updated_at",
    "embedding",
    "embedding_model",
)

# All eight statuses the canonical request_status CHECK constraint must allow.
REQUIRED_STATUSES = (
    "pending",
    "approved",
    "rejected",
    "in_progress",
    "implemented",
    "incomplete",
    "completed",
    "cancelled",
)

# Columns that can be added in place with ALTER TABLE ADD COLUMN when they are
# missing but the CHECK constraint is already correct (no rebuild required).
_ADDABLE_COLUMNS = (
    ("assigned_time", "TIMESTAMP"),
    ("embedding", "BLOB"),
    ("embedding_model", "VARCHAR(100)"),
)

# Canonical CREATE TABLE statement, matching schema.sql exactly.
CANONICAL_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS agent_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        agent_name TEXT NOT NULL,
        creation_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        request TEXT NOT NULL,
        reason_for_request TEXT,
        request_status TEXT DEFAULT 'pending'
            CHECK (request_status IN ('pending', 'approved', 'rejected', 'in_progress', 'implemented', 'incomplete', 'completed', 'cancelled')),
        status_reason TEXT,
        assigned_time TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        embedding BLOB,
        embedding_model VARCHAR(100)
    )
"""

# Canonical indexes for agent_requests.
CANONICAL_INDEX_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_agent_requests_status ON agent_requests(request_status)",
    "CREATE INDEX IF NOT EXISTS idx_agent_requests_creation ON agent_requests(creation_time)",
    "CREATE INDEX IF NOT EXISTS idx_agent_requests_agent ON agent_requests(agent_name)",
    "CREATE INDEX IF NOT EXISTS idx_agent_requests_assigned ON agent_requests(assigned_time)",
)

_BACKUP_TABLE_NAME = "agent_requests_migration_backup"


def _get_table_sql(conn: sqlite3.Connection) -> str | None:
    """Return the CREATE statement stored for the agent_requests table.

    Parameters
    ----------
    conn : sqlite3.Connection
        Open connection to the target database.

    Returns
    -------
    str | None
        The SQL text used to create the table, or None if it does not exist.
    """
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'agent_requests'"
    ).fetchone()
    return row[0] if row and row[0] else None


def _get_column_names(conn: sqlite3.Connection) -> list[str]:
    """Return the column names of the agent_requests table.

    Parameters
    ----------
    conn : sqlite3.Connection
        Open connection to the target database.

    Returns
    -------
    list[str]
        Column names in table order.
    """
    cursor = conn.execute("PRAGMA table_info(agent_requests)")
    return [row[1] for row in cursor.fetchall()]


def _check_covers_all_statuses(table_sql: str) -> bool:
    """Determine whether the table's CHECK constraint allows all statuses.

    Parameters
    ----------
    table_sql : str
        The CREATE statement text for the table.

    Returns
    -------
    bool
        True if every canonical status appears as a quoted literal in the
        table definition, False otherwise (including when there is no CHECK
        constraint at all).
    """
    lowered = table_sql.lower()
    return all(f"'{status}'" in lowered for status in REQUIRED_STATUSES)


def _rebuild_table_with_canonical_schema(
    conn: sqlite3.Connection, existing_cols: list[str]
) -> None:
    """Recreate agent_requests with the canonical schema, preserving data.

    SQLite cannot alter a CHECK constraint in place, so the table is renamed,
    recreated from the canonical definition, repopulated from the columns the
    old and new tables have in common, and finally the backup is dropped.

    Parameters
    ----------
    conn : sqlite3.Connection
        Open connection to the target database.
    existing_cols : list[str]
        Column names present in the current table, used to build a safe
        column intersection for copying rows.
    """
    common = [col for col in CANONICAL_COLUMNS if col in existing_cols]
    col_list = ", ".join(common)

    conn.execute(f"DROP TABLE IF EXISTS {_BACKUP_TABLE_NAME}")
    conn.execute(f"ALTER TABLE agent_requests RENAME TO {_BACKUP_TABLE_NAME}")
    conn.execute(CANONICAL_TABLE_SQL)
    if col_list:
        conn.execute(
            f"INSERT INTO agent_requests ({col_list}) "
            f"SELECT {col_list} FROM {_BACKUP_TABLE_NAME}"
        )
    conn.execute(f"DROP TABLE {_BACKUP_TABLE_NAME}")


def migrate_agent_requests(db_path: Path = DEFAULT_DB_PATH) -> list[str]:
    """Migrate the agent_requests table to the canonical schema.

    The migration is idempotent: running it against an already-canonical table
    performs no changes. If the table does not exist it is created. Otherwise
    the migration ensures the ``assigned_time`` (and, for completeness,
    ``embedding``/``embedding_model``) columns exist and that the
    ``request_status`` CHECK constraint allows all eight canonical statuses,
    rebuilding the table only when the constraint needs to change.

    Parameters
    ----------
    db_path : Path
        Path to the SQLite database file. Connecting creates the file if it
        does not already exist.

    Returns
    -------
    list[str]
        Human-readable descriptions of the changes made. An empty list means
        the schema was already canonical and nothing was changed.
    """
    changes: list[str] = []
    conn = sqlite3.connect(str(db_path))
    try:
        table_sql = _get_table_sql(conn)

        if table_sql is None:
            conn.execute(CANONICAL_TABLE_SQL)
            for index_sql in CANONICAL_INDEX_SQL:
                conn.execute(index_sql)
            conn.commit()
            changes.append("created agent_requests table with canonical schema")
            return changes

        existing_cols = _get_column_names(conn)

        if not _check_covers_all_statuses(table_sql):
            _rebuild_table_with_canonical_schema(conn, existing_cols)
            changes.append(
                "rebuilt agent_requests so request_status allows all eight "
                "canonical statuses"
            )
            # The rebuilt table has every canonical column; report the ones
            # that the old table lacked (e.g. assigned_time).
            for col, _decl in _ADDABLE_COLUMNS:
                if col not in existing_cols:
                    changes.append(f"added missing '{col}' column")
        else:
            for col, decl in _ADDABLE_COLUMNS:
                if col not in existing_cols:
                    conn.execute(
                        f"ALTER TABLE agent_requests ADD COLUMN {col} {decl}"
                    )
                    changes.append(f"added missing '{col}' column")

        # Ensure the canonical indexes exist (idempotent).
        for index_sql in CANONICAL_INDEX_SQL:
            conn.execute(index_sql)

        conn.commit()
        return changes
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    """Run the agent_requests migration from the command line.

    Parameters
    ----------
    argv : list[str] | None
        Optional argument list (primarily for testing). When None, arguments
        are read from ``sys.argv``.

    Returns
    -------
    int
        Process exit code (0 on success).
    """
    parser = argparse.ArgumentParser(
        description=(
            "Migrate an existing articles.sqlite agent_requests table to the "
            "canonical schema (adds assigned_time and ensures all eight "
            "request statuses are allowed). Safe to run repeatedly."
        )
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="Path to the SQLite database file (default: ./articles.sqlite).",
    )
    args = parser.parse_args(argv)

    if not args.db.exists():
        print(
            f"Database {args.db} does not exist; it will be created with the "
            "canonical agent_requests table."
        )

    changes = migrate_agent_requests(args.db)

    if changes:
        print(f"Migration of {args.db} complete:")
        for change in changes:
            print(f"  - {change}")
    else:
        print(f"No migration needed for {args.db}; schema is already canonical.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
