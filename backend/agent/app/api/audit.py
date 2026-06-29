import json
from typing import Optional

from fastapi import APIRouter, Query

from app.db.database import get_connection
from app.repositories import sessions as session_repo

router = APIRouter()


@router.get("/audit")
def list_audit(
    session_id: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100, alias="pageSize"),
) -> dict:
    with get_connection() as conn:
        rows = session_repo.list_audit_events(
            conn, session_id=session_id, page=page, page_size=page_size
        )
    items = []
    for row in rows:
        items.append({
            "id": row["id"],
            "sessionId": row["session_id"],
            "action": row["action"],
            "detail": json.loads(row["detail_json"]) if row["detail_json"] else {},
            "createdAt": row["created_at"],
        })
    return {"items": items, "page": page, "pageSize": page_size}
