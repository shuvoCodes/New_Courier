from database import SessionLocal
from datetime import datetime, timedelta
from fastapi import APIRouter,Depends,HTTPException
from fastapi.responses import JSONResponse
from models import Parcels, Addresses, ParcelStatusHistory, Notifications, Agents
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Annotated,Optional
import random

from router.auth import get_current_user, require_roles
from router.audit import log_action
from router.pricing import calculate_delivery_fee
from router.status_workflow import is_transition_allowed, STATUSES


route = APIRouter()


class CreateParcel(BaseModel):
    pickup_address_id : int
    delivery_address_id : int
    parcel_type : str
    service_type : Optional[str] = Field(default= 'standard')
    weight : float = Field(default= 0.5, gt= 0)
    cod_amount : Optional[float] = Field(default= 0.0, ge= 0)
    notes : Optional[str] = Field(default= None)
    origin_branch_id : Optional[int] = Field(default= None)
    destination_branch_id : Optional[int] = Field(default= None)
    zone : Optional[str] = Field(default= 'inside_city')

class UpdateParcel(BaseModel):
    pickup_address_id : Optional[int] = Field(default= None)
    delivery_address_id : Optional[int] = Field(default= None)
    parcel_type : Optional[str] = Field(default= None)
    service_type : Optional[str] = Field(default= None)
    weight : Optional[float] = Field(default= None, gt= 0)
    cod_amount : Optional[float] = Field(default= None, ge= 0)
    notes : Optional[str] = Field(default= None)

class UpdateStatus(BaseModel):
    status : str
    note : Optional[str] = Field(default= None)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependency = Annotated[Session, Depends(get_db)]
user_dependency = Annotated[dict, Depends(get_current_user)]


def generate_tracking_code(db: Session) -> str:
    year = datetime.now().year
    while True:
        code = f'CDR-{year}-{random.randint(10000,99999)}'
        exist = db.query(Parcels).filter(Parcels.tracking_code == code).first()
        if exist is None:
            return code


def add_status_history(db: Session, parcel_id: int, status: str, changed_by_id, note: str = None):
    history = ParcelStatusHistory(
        parcel_id = parcel_id,
        status = status,
        changed_by_id = changed_by_id,
        note = note
    )
    db.add(history)
    db.commit()


def notify_user(db: Session, user_id: int, message: str):
    if user_id is None:
        return
    notification = Notifications(user_id = user_id, message = message)
    db.add(notification)
    db.commit()


@route.post('/parcels')
def create_parcel(user : user_dependency, db : db_dependency, new_parcel : CreateParcel):
    if user is None:
        raise HTTPException(status_code= 401, detail= 'Failed Authentication.')

    pickup = db.query(Addresses).filter(Addresses.id == new_parcel.pickup_address_id).first()
    delivery = db.query(Addresses).filter(Addresses.id == new_parcel.delivery_address_id).first()

    if pickup is None or delivery is None:
        raise HTTPException(status_code= 404, detail= 'Pickup or Delivery Address Not Found.')

    if user.get('role') == 'customer' and (pickup.user_id != user.get('id') or delivery.user_id != user.get('id')):
        raise HTTPException(status_code= 403, detail= 'Address does not belong to you.')

    fee = calculate_delivery_fee(new_parcel.weight, new_parcel.service_type, new_parcel.cod_amount, new_parcel.zone)

    parcel_model = Parcels(
        tracking_code = generate_tracking_code(db),
        customer_id = user.get('id'),
        pickup_address_id = new_parcel.pickup_address_id,
        delivery_address_id = new_parcel.delivery_address_id,
        origin_branch_id = new_parcel.origin_branch_id,
        destination_branch_id = new_parcel.destination_branch_id,
        parcel_type = new_parcel.parcel_type,
        service_type = new_parcel.service_type,
        weight = new_parcel.weight,
        cod_amount = new_parcel.cod_amount,
        delivery_fee = fee,
        notes = new_parcel.notes,
        status = 'CREATED',
        payment_status = 'PENDING',
        estimated_delivery = datetime.now() + timedelta(days= 2 if new_parcel.service_type == 'express' else 4)
    )
    db.add(parcel_model)
    db.commit()
    db.refresh(parcel_model)

    add_status_history(db, parcel_model.id, 'CREATED', user.get('id'), 'Parcel created')
    log_action(db, user.get('id'), 'CREATE_PARCEL', 'parcel', parcel_model.id)

    return JSONResponse(status_code= 201, content= {
        'Message' : 'Parcel Created Sucessfully.',
        'tracking_code' : parcel_model.tracking_code,
        'delivery_fee' : fee
    })


def _scope_query_by_role(db: Session, user: dict):
    query = db.query(Parcels)

    if user.get('role') == 'customer':
        query = query.filter(Parcels.customer_id == user.get('id'))
    elif user.get('role') == 'agent':
        agent = db.query(Agents).filter(Agents.user_id == user.get('id')).first()
        agent_id = agent.id if agent else -1
        query = query.filter(Parcels.assigned_agent_id == agent_id)
    # staff / admin -> unrestricted

    return query


@route.get('/parcels')
def list_parcels(user : user_dependency, db : db_dependency,
                  search : Optional[str] = None, status : Optional[str] = None,
                  payment_status : Optional[str] = None,
                  origin_branch_id : Optional[int] = None, destination_branch_id : Optional[int] = None,
                  assigned_agent_id : Optional[int] = None,
                  date_from : Optional[str] = None, date_to : Optional[str] = None,
                  sort_by : str = 'create_at', sort_order : str = 'desc',
                  page : int = 1, page_size : int = 20):
    if user is None:
        raise HTTPException(status_code= 401, detail= 'Failed Authentication.')

    query = _scope_query_by_role(db, user)

    if search:
        like = f'%{search}%'
        query = query.filter(
            (Parcels.tracking_code.ilike(like)) |
            (Parcels.notes.ilike(like)) |
            (Parcels.parcel_type.ilike(like))
        )
    if status:
        query = query.filter(Parcels.status == status)
    if payment_status:
        query = query.filter(Parcels.payment_status == payment_status)
    if origin_branch_id:
        query = query.filter(Parcels.origin_branch_id == origin_branch_id)
    if destination_branch_id:
        query = query.filter(Parcels.destination_branch_id == destination_branch_id)
    if assigned_agent_id:
        query = query.filter(Parcels.assigned_agent_id == assigned_agent_id)
    if date_from:
        query = query.filter(Parcels.create_at >= date_from)
    if date_to:
        query = query.filter(Parcels.create_at <= date_to)

    sort_column = getattr(Parcels, sort_by, Parcels.create_at)
    query = query.order_by(sort_column.desc() if sort_order == 'desc' else sort_column.asc())

    total_items = query.count()
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


def _get_scoped_parcel_or_404(db: Session, user: dict, parcel_id: int) -> Parcels:
    find = db.query(Parcels).filter(Parcels.id == parcel_id).first()
    if find is None:
        raise HTTPException(status_code= 404, detail= 'Parcel Not Found.')

    if user.get('role') == 'customer' and find.customer_id != user.get('id'):
        raise HTTPException(status_code= 403, detail= 'Not enough permission.')

    if user.get('role') == 'agent':
        agent = db.query(Agents).filter(Agents.user_id == user.get('id')).first()
        if agent is None or find.assigned_agent_id != agent.id:
            raise HTTPException(status_code= 403, detail= 'Not enough permission.')

    return find


@route.get('/parcels/{parcel_id}')
def get_parcel(user : user_dependency, db : db_dependency, parcel_id : int):
    if user is None:
        raise HTTPException(status_code= 401, detail= 'Failed Authentication.')

    return _get_scoped_parcel_or_404(db, user, parcel_id)


@route.put('/parcels/{parcel_id}')
def update_parcel(user : user_dependency, db : db_dependency, parcel_id : int, update_info : UpdateParcel):
    if user is None:
        raise HTTPException(status_code= 401, detail= 'Failed Authentication.')

    find = _get_scoped_parcel_or_404(db, user, parcel_id)

    if find.status != 'CREATED':
        raise HTTPException(status_code= 400, detail= 'Parcel can only be edited before it is confirmed.')

    update = update_info.model_dump(exclude_unset= True)
    for key,value in update.items():
        setattr(find,key,value)

    # Recalculate fee if weight, service type or cod amount changed.
    if any(k in update for k in ('weight','service_type','cod_amount')):
        find.delivery_fee = calculate_delivery_fee(find.weight, find.service_type, find.cod_amount)

    db.commit()
    log_action(db, user.get('id'), 'UPDATE_PARCEL', 'parcel', parcel_id)

    return JSONResponse(status_code= 200, content= {'Message' : 'Parcel Updated Sucessfully.'})


@route.patch('/parcels/{parcel_id}/cancel')
def cancel_parcel(user : user_dependency, db : db_dependency, parcel_id : int):
    if user is None:
        raise HTTPException(status_code= 401, detail= 'Failed Authentication.')

    find = _get_scoped_parcel_or_404(db, user, parcel_id)

    if not is_transition_allowed(find.status, 'CANCELLED'):
        raise HTTPException(status_code= 400, detail= f'Parcel in status {find.status} cannot be cancelled.')

    find.status = 'CANCELLED'
    db.commit()

    add_status_history(db, parcel_id, 'CANCELLED', user.get('id'), 'Cancelled by user')
    notify_user(db, find.customer_id, f'Your parcel {find.tracking_code} has been cancelled.')
    log_action(db, user.get('id'), 'CANCEL_PARCEL', 'parcel', parcel_id)

    return JSONResponse(status_code= 200, content= {'Message' : 'Parcel Cancelled Sucessfully.'})


@route.delete('/parcels/{parcel_id}')
def delete_parcel(user : user_dependency, db : db_dependency, parcel_id : int):
    require_roles(user, 'admin')

    find = db.query(Parcels).filter(Parcels.id == parcel_id).first()
    if find is None:
        raise HTTPException(status_code= 404, detail= 'Parcel Not Found.')

    db.query(Parcels).filter(Parcels.id == parcel_id).delete()
    db.commit()

    log_action(db, user.get('id'), 'DELETE_PARCEL', 'parcel', parcel_id)

    return JSONResponse(status_code= 200, content= {'Message' : 'Parcel Deleted Sucessfully.'})


@route.patch('/parcels/{parcel_id}/status')
def update_parcel_status(user : user_dependency, db : db_dependency, parcel_id : int, body : UpdateStatus):
    require_roles(user, 'admin','staff','agent')

    find = db.query(Parcels).filter(Parcels.id == parcel_id).first()
    if find is None:
        raise HTTPException(status_code= 404, detail= 'Parcel Not Found.')

    if user.get('role') == 'agent':
        agent = db.query(Agents).filter(Agents.user_id == user.get('id')).first()
        if agent is None or find.assigned_agent_id != agent.id:
            raise HTTPException(status_code= 403, detail= 'Not enough permission.')

    if not is_transition_allowed(find.status, body.status):
        raise HTTPException(status_code= 400, detail= f'Cannot change status from {find.status} to {body.status}.')

    find.status = body.status
    if body.status == 'DELIVERED':
        find.payment_status = 'PAID' if find.payment_status != 'PAID' else find.payment_status
    db.commit()

    add_status_history(db, parcel_id, body.status, user.get('id'), body.note)
    notify_user(db, find.customer_id, f'Your parcel {find.tracking_code} is now {body.status.replace("_"," ").title()}.')
    log_action(db, user.get('id'), 'UPDATE_PARCEL_STATUS', 'parcel', parcel_id, body.status)

    return JSONResponse(status_code= 200, content= {'Message' : 'Parcel Status Updated Sucessfully.'})


@route.get('/parcels/{parcel_id}/history')
def get_parcel_history(user : user_dependency, db : db_dependency, parcel_id : int):
    if user is None:
        raise HTTPException(status_code= 401, detail= 'Failed Authentication.')

    _get_scoped_parcel_or_404(db, user, parcel_id)

    return db.query(ParcelStatusHistory).filter(
        ParcelStatusHistory.parcel_id == parcel_id
    ).order_by(ParcelStatusHistory.create_at.asc()).all()
