from database import SessionLocal
from datetime import datetime
from fastapi import APIRouter,Depends,HTTPException
from fastapi.responses import JSONResponse
from models import Payments, Parcels
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Annotated,Optional

from router.auth import get_current_user, require_roles
from router.audit import log_action


route = APIRouter()


class CreatePayment(BaseModel):
    parcel_id : int
    amount : float
    method : str = Field(default= 'COD')
    transaction_id : Optional[str] = Field(default= None)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependency = Annotated[Session, Depends(get_db)]
user_dependency = Annotated[Session, Depends(get_current_user)]


@route.post('/payments')
def create_payment(user : user_dependency, db : db_dependency, body : CreatePayment):
    require_roles(user, 'admin','staff','agent')

    parcel = db.query(Parcels).filter(Parcels.id == body.parcel_id).first()
    if parcel is None:
        raise HTTPException(status_code= 404, detail= 'Parcel Not Found.')

    payment_model = Payments(
        parcel_id = body.parcel_id,
        amount = body.amount,
        method = body.method,
        transaction_id = body.transaction_id,
        status = 'PAID' if body.method == 'ONLINE' else 'PENDING',
        paid_at = datetime.now() if body.method == 'ONLINE' else None
    )
    db.add(payment_model)

    if body.method == 'ONLINE':
        parcel.payment_status = 'PAID'

    db.commit()
    db.refresh(payment_model)

    log_action(db, user.get('id'), 'CREATE_PAYMENT', 'payment', payment_model.id)

    return JSONResponse(status_code= 201, content= {'Message' : 'Payment Recorded Sucessfully.'})


@route.get('/payments')
def list_payments(user : user_dependency, db : db_dependency,
                   status : Optional[str] = None, date_from : Optional[str] = None,
                   date_to : Optional[str] = None, page : int = 1, page_size : int = 20):
    require_roles(user, 'admin','staff')

    query = db.query(Payments)

    if status:
        query = query.filter(Payments.status == status)
    if date_from:
        query = query.filter(Payments.create_at >= date_from)
    if date_to:
        query = query.filter(Payments.create_at <= date_to)

    total_items = query.count()
    items = query.order_by(Payments.create_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return {
        'items' : items,
        'page' : page,
        'page_size' : page_size,
        'total_items' : total_items,
        'total_pages' : (total_items + page_size - 1) // page_size,
        'has_next' : page * page_size < total_items,
        'has_previous' : page > 1
    }


@route.get('/payments/{payment_id}')
def get_payment(user : user_dependency, db : db_dependency, payment_id : int):
    require_roles(user, 'admin','staff')

    find = db.query(Payments).filter(Payments.id == payment_id).first()
    if find is None:
        raise HTTPException(status_code= 404, detail= 'Payment Not Found.')

    return find
