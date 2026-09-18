from database import SessionLocal
from datetime import datetime
from fastapi import APIRouter,Depends,HTTPException
from fastapi.responses import JSONResponse
from models import Assignments, Parcels, Agents
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Annotated

from router.auth import get_current_user, require_roles
from router.audit import log_action
from router.parcels import add_status_history, notify_user


route = APIRouter()


class CreateAssignment(BaseModel):
    parcel_id : int
    agent_id : int

class ReassignAgent(BaseModel):
    agent_id : int


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependency = Annotated[Session, Depends(get_db)]
user_dependency = Annotated[Session, Depends(get_current_user)]


@route.post('/assignments')
def create_assignment(user : user_dependency, db : db_dependency, body : CreateAssignment):
    require_roles(user, 'admin','staff')

    parcel = db.query(Parcels).filter(Parcels.id == body.parcel_id).first()
    if parcel is None:
        raise HTTPException(status_code= 404, detail= 'Parcel Not Found.')

    agent = db.query(Agents).filter(Agents.id == body.agent_id).first()
    if agent is None:
        raise HTTPException(status_code= 404, detail= 'Agent Not Found.')

    assignment_model = Assignments(
        parcel_id = body.parcel_id,
        agent_id = body.agent_id,
        assigned_by_id = user.get('id'),
        status = 'assigned'
    )
    db.add(assignment_model)

    parcel.assigned_agent_id = body.agent_id
    agent.status = 'busy'

    db.commit()

    notify_user(db, parcel.customer_id, f'Parcel {parcel.tracking_code} has been assigned to a delivery agent.')
    log_action(db, user.get('id'), 'CREATE_ASSIGNMENT', 'parcel', body.parcel_id, f'agent_id={body.agent_id}')

    return JSONResponse(status_code= 201, content= {'Message' : 'Parcel Assigned Sucessfully.'})


@route.patch('/assignments/{assignment_id}/reassign')
def reassign_assignment(user : user_dependency, db : db_dependency, assignment_id : int, body : ReassignAgent):
    require_roles(user, 'admin','staff')

    assignment = db.query(Assignments).filter(Assignments.id == assignment_id).first()
    if assignment is None:
        raise HTTPException(status_code= 404, detail= 'Assignment Not Found.')

    new_agent = db.query(Agents).filter(Agents.id == body.agent_id).first()
    if new_agent is None:
        raise HTTPException(status_code= 404, detail= 'Agent Not Found.')

    old_agent = db.query(Agents).filter(Agents.id == assignment.agent_id).first()
    if old_agent is not None:
        old_agent.status = 'available'

    assignment.status = 'reassigned'

    new_assignment = Assignments(
        parcel_id = assignment.parcel_id,
        agent_id = body.agent_id,
        assigned_by_id = user.get('id'),
        status = 'assigned'
    )
    db.add(new_assignment)

    parcel = db.query(Parcels).filter(Parcels.id == assignment.parcel_id).first()
    if parcel is not None:
        parcel.assigned_agent_id = body.agent_id

    new_agent.status = 'busy'
    db.commit()

    log_action(db, user.get('id'), 'REASSIGN_PARCEL', 'parcel', assignment.parcel_id, f'new_agent_id={body.agent_id}')

    return JSONResponse(status_code= 200, content= {'Message' : 'Parcel Reassigned Sucessfully.'})


@route.patch('/assignments/{assignment_id}/accept')
def accept_assignment(user : user_dependency, db : db_dependency, assignment_id : int):
    require_roles(user, 'agent')

    assignment = db.query(Assignments).filter(Assignments.id == assignment_id).first()
    if assignment is None:
        raise HTTPException(status_code= 404, detail= 'Assignment Not Found.')

    agent = db.query(Agents).filter(Agents.user_id == user.get('id')).first()
    if agent is None or assignment.agent_id != agent.id:
        raise HTTPException(status_code= 403, detail= 'Not enough permission.')

    assignment.status = 'accepted'
    assignment.responded_at = datetime.now()
    db.commit()

    parcel = db.query(Parcels).filter(Parcels.id == assignment.parcel_id).first()
    if parcel is not None:
        add_status_history(db, parcel.id, parcel.status, user.get('id'), 'Agent accepted the assignment')

    log_action(db, user.get('id'), 'ACCEPT_ASSIGNMENT', 'assignment', assignment_id)

    return JSONResponse(status_code= 200, content= {'Message' : 'Assignment Accepted Sucessfully.'})
