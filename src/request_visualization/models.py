# Data models for agent requests.
# Defines the AgentRequest dataclass for representing requests stored in the database.

from dataclasses import dataclass
from datetime import datetime


@dataclass
class AgentRequest:
    """Represents an agent request stored in the database.

    Attributes
    ----------
    id : int
        Unique identifier for the request.
    agent_name : str
        Name of the agent that created the request.
    creation_time : datetime
        Timestamp when the request was created.
    request : str
        The actual request text/content.
    reason_for_request : str | None
        Optional reason explaining why the request was made.
    request_status : str
        Current status: 'pending', 'approved', 'rejected', 'implemented',
        'completed', or 'cancelled'.
    status_reason : str | None
        Optional reason for approval/rejection/completion/cancellation.
    updated_at : datetime
        Timestamp when the request was last updated.
    assigned_time : datetime | None
        Timestamp when the request was assigned to an agent for implementation.
    embedding : bytes | None
        Semantic embedding vector for the request (stored as BLOB).
    embedding_model : str | None
        Name of the model used to generate the embedding.
    """

    id: int
    agent_name: str
    creation_time: datetime
    request: str
    reason_for_request: str | None
    request_status: str
    status_reason: str | None
    updated_at: datetime
    assigned_time: datetime | None = None
    embedding: bytes | None = None
    embedding_model: str | None = None
