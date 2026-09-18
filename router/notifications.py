from database import SessionLocal
from fastapi import APIRouter,Depends,HTTPException
from fastapi.responses import JSONResponse
from models import Notifications
from sqlalchemy.orm import Session
from typing import Annotated


route = APIRouter()

from router.auth import get_current_user


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependency = Annotated[Session, Depends(get_db)]
user_dependency = Annotated[Session, Depends(get_current_user)]


@route.get('/notifications')
def list_notifications(user : user_dependency, db : db_dependency, is_read : bool = None):
    if user is None:
        raise HTTPException(status_code= 401, detail= 'Failed Authentication.')

    query = db.query(Notifications).filter(Notifications.user_id == user.get('id'))
    if is_read is not None:
        query = query.filter(Notifications.is_read == is_read)

    return query.order_by(Notifications.create_at.desc()).all()


@route.patch('/notifications/{notification_id}/read')
def mark_notification_read(user : user_dependency, db : db_dependency, notification_id : int):
    if user is None:
        raise HTTPException(status_code= 401, detail= 'Failed Authentication.')

    find = db.query(Notifications).filter(
        Notifications.id == notification_id, Notifications.user_id == user.get('id')
    ).first()
    if find is None:
        raise HTTPException(status_code= 404, detail= 'Notification Not Found.')

    find.is_read = True
    db.commit()

    return JSONResponse(status_code= 200, content= {'Message' : 'Notification Marked as Read.'})


@route.patch('/notifications/read-all')
def mark_all_notifications_read(user : user_dependency, db : db_dependency):
    if user is None:
        raise HTTPException(status_code= 401, detail= 'Failed Authentication.')

    db.query(Notifications).filter(
        Notifications.user_id == user.get('id'), Notifications.is_read == False
    ).update({'is_read' : True})
    db.commit()

    return JSONResponse(status_code= 200, content= {'Message' : 'All Notifications Marked as Read.'})
