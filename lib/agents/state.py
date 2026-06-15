"""
Shared LangGraph state schemas — agent-core-infra
Each product extends BaseJobState with its own fields.
"""
from typing import TypedDict, Optional


class BaseJobState(TypedDict):
    job_id: str
    user_email: str
    product: str          # 'agentcv' | 'agentaudit' | 'agentlegal' | …
    status: str           # 'processing' | 'done' | 'error'
    progress: int         # 0–100
    artifact_urls: dict   # {"name": "signed_url", …}
    error: Optional[str]


class BaseProgressEvent(TypedDict):
    job_id: str
    status: str
    progress: int
    message: str
    artifact_urls: dict
    error: Optional[str]
