from database import SessionLocal
from fastapi import APIRouter,Depends,HTTPException
from models import AuditLogs
from sqlalchemy.orm import Session
from typing import Annotated,Optional
from router.auth import get_current_user, require_roles


route = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependency = Annotated[Session, Depends(get_db)]
user_dependency = Annotated[Session, Depends(get_current_user)]


def log_action(db: Session, user_id, action: str, target_type: str = None, target_id: int = None, details: str = None):
    entry = AuditLogs(
        user_id = user_id,
        action = action,
        target_type = target_type,
        target_id = target_id,
        details = details
    )
    db.add(entry)
    db.commit()


@route.get('/audit-logs')
def list_audit_logs(user : user_dependency, db : db_dependency,
                     action : Optional[str] = None, target_type : Optional[str] = None,
                     page : int = 1, page_size : int = 20):
    require_roles(user, 'admin')

    query = db.query(AuditLogs)

    if action:
        query = query.filter(AuditLogs.action.ilike(f'%{action}%'))
    if target_type:
        query = query.filter(AuditLogs.target_type == target_type)

    total_items = query.count()
    query = query.order_by(AuditLogs.create_at.desc())
    items = query.offset((page - 1) * page_size).limit(page_size).all()

    return {
        'items' : items,
        'page' : page,
        'page_size' : page_size,
        'total_items' : total_items,
        'total_pages' : (total_items + page_size - 1) // page_size,
        'has_next' : page * page_size < total_items,
        'has_previous' : page > 1
    }
