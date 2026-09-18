from database import SessionLocal
from fastapi import APIRouter,Depends,HTTPException
from models import Parcels, Payments, Branches, Agents
from sqlalchemy import func
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


@route.get('/reports/overview')
def reports_overview(user : user_dependency, db : db_dependency):
    require_roles(user, 'admin','staff')

    total_parcels = db.query(Parcels).count()
    pending = db.query(Parcels).filter(Parcels.status.in_(['CREATED','CONFIRMED'])).count()
    in_transit = db.query(Parcels).filter(
        Parcels.status.in_(['PICKED_UP','AT_ORIGIN_HUB','IN_TRANSIT','AT_DESTINATION_HUB','OUT_FOR_DELIVERY'])
    ).count()
    delivered = db.query(Parcels).filter(Parcels.status == 'DELIVERED').count()
    cancelled = db.query(Parcels).filter(Parcels.status == 'CANCELLED').count()
    total_revenue = db.query(func.coalesce(func.sum(Payments.amount), 0)).filter(Payments.status == 'PAID').scalar()

    return {
        'total_parcels' : total_parcels,
        'pending' : pending,
        'in_transit' : in_transit,
        'delivered' : delivered,
        'cancelled' : cancelled,
        'total_revenue' : total_revenue
    }


@route.get('/dashboard/customer')
def dashboard_customer(user : user_dependency, db : db_dependency):
    if user is None or user.get('role') != 'customer':
        raise HTTPException(status_code= 403, detail= 'Not enough permission.')

    base = db.query(Parcels).filter(Parcels.customer_id == user.get('id'))

    return {
        'total_parcels' : base.count(),
        'in_transit' : base.filter(
            Parcels.status.in_(['PICKED_UP','AT_ORIGIN_HUB','IN_TRANSIT','AT_DESTINATION_HUB','OUT_FOR_DELIVERY'])
        ).count(),
        'delivered' : base.filter(Parcels.status == 'DELIVERED').count(),
        'cancelled' : base.filter(Parcels.status == 'CANCELLED').count()
    }


@route.get('/dashboard/agent')
def dashboard_agent(user : user_dependency, db : db_dependency):
    if user is None or user.get('role') != 'agent':
        raise HTTPException(status_code= 403, detail= 'Not enough permission.')

    agent = db.query(Agents).filter(Agents.user_id == user.get('id')).first()
    agent_id = agent.id if agent else -1

    base = db.query(Parcels).filter(Parcels.assigned_agent_id == agent_id)

    return {
        'assigned_parcels' : base.count(),
        'out_for_delivery' : base.filter(Parcels.status == 'OUT_FOR_DELIVERY').count(),
        'delivered' : base.filter(Parcels.status == 'DELIVERED').count(),
        'failed_delivery' : base.filter(Parcels.status == 'FAILED_DELIVERY').count()
    }


@route.get('/reports/shipments')
def reports_shipments(user : user_dependency, db : db_dependency,
                       date_from : Optional[str] = None, date_to : Optional[str] = None):
    require_roles(user, 'admin','staff')

    query = db.query(Parcels)
    if date_from:
        query = query.filter(Parcels.create_at >= date_from)
    if date_to:
        query = query.filter(Parcels.create_at <= date_to)

    rows = query.with_entities(Parcels.status, func.count(Parcels.id)).group_by(Parcels.status).all()

    return {status : count for status, count in rows}


@route.get('/reports/revenue')
def reports_revenue(user : user_dependency, db : db_dependency,
                     date_from : Optional[str] = None, date_to : Optional[str] = None):
    require_roles(user, 'admin','staff')

    query = db.query(Payments).filter(Payments.status == 'PAID')
    if date_from:
        query = query.filter(Payments.create_at >= date_from)
    if date_to:
        query = query.filter(Payments.create_at <= date_to)

    total_revenue = query.with_entities(func.coalesce(func.sum(Payments.amount), 0)).scalar()
    payment_count = query.count()

    return {
        'date_from' : date_from,
        'date_to' : date_to,
        'total_revenue' : total_revenue,
        'payment_count' : payment_count
    }


@route.get('/reports/branches')
def reports_branches(user : user_dependency, db : db_dependency):
    require_roles(user, 'admin','staff')

    branches = db.query(Branches).all()
    result = []
    for branch in branches:
        outgoing = db.query(Parcels).filter(Parcels.origin_branch_id == branch.id).count()
        incoming = db.query(Parcels).filter(Parcels.destination_branch_id == branch.id).count()
        result.append({
            'branch_id' : branch.id,
            'name' : branch.name,
            'city' : branch.city,
            'outgoing_parcels' : outgoing,
            'incoming_parcels' : incoming
        })

    return result


@route.get('/reports/agents')
def reports_agents(user : user_dependency, db : db_dependency):
    require_roles(user, 'admin','staff')

    agents = db.query(Agents).all()
    result = []
    for agent in agents:
        base = db.query(Parcels).filter(Parcels.assigned_agent_id == agent.id)
        result.append({
            'agent_id' : agent.id,
            'name' : agent.name,
            'status' : agent.status,
            'assigned_parcels' : base.count(),
            'delivered' : base.filter(Parcels.status == 'DELIVERED').count(),
            'failed_delivery' : base.filter(Parcels.status == 'FAILED_DELIVERY').count()
        })

    return result
