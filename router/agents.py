from database import SessionLocal
from fastapi import APIRouter,Depends,HTTPException
from fastapi.responses import JSONResponse
from models import Agents
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Annotated,Optional
from router.auth import get_current_user, require_roles
from router.audit import log_action


route = APIRouter()


class CreateAgent(BaseModel):
    user_id : Optional[int] = Field(default= None)
    branch_id : Optional[int] = Field(default= None)
    name : str
    phone : str
    vehicle_type : Optional[str] = Field(default= None)

class UpdateAgent(BaseModel):
    branch_id : Optional[int] = Field(default= None)
    name : Optional[str] = Field(default= None)
    phone : Optional[str] = Field(default= None)
    vehicle_type : Optional[str] = Field(default= None)

class UpdateStatus(BaseModel):
    status : str


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependency = Annotated[Session, Depends(get_db)]
user_dependency = Annotated[Session, Depends(get_current_user)]


@route.post('/agents')
def create_agent(user : user_dependency, db : db_dependency, new_agent : CreateAgent):
    require_roles(user, 'admin','staff')

    agent_model = Agents(**new_agent.model_dump())
    db.add(agent_model)
    db.commit()
    db.refresh(agent_model)

    log_action(db, user.get('id'), 'CREATE_AGENT', 'agent', agent_model.id)

    return JSONResponse(status_code= 201, content= {'Message' : 'Agent Created Sucessfully.'})


@route.get('/agents')
def list_agents(user : user_dependency, db : db_dependency,
                 search : Optional[str] = None, status : Optional[str] = None,
                 branch_id : Optional[int] = None, page : int = 1, page_size : int = 20):
    require_roles(user, 'admin','staff')

    query = db.query(Agents)

    if search:
        like = f'%{search}%'
        query = query.filter((Agents.name.ilike(like)) | (Agents.phone.ilike(like)))
    if status:
        query = query.filter(Agents.status == status)
    if branch_id:
        query = query.filter(Agents.branch_id == branch_id)

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


@route.get('/agents/{agent_id}')
def get_agent(user : user_dependency, db : db_dependency, agent_id : int):
    require_roles(user, 'admin','staff')

    find = db.query(Agents).filter(Agents.id == agent_id).first()
    if find is None:
        raise HTTPException(status_code= 404, detail= 'Agent Not Found.')

    return find


@route.put('/agents/{agent_id}')
def update_agent(user : user_dependency, db : db_dependency, agent_id : int, update_info : UpdateAgent):
    require_roles(user, 'admin','staff')

    find = db.query(Agents).filter(Agents.id == agent_id).first()
    if find is None:
        raise HTTPException(status_code= 404, detail= 'Agent Not Found.')

    update = update_info.model_dump(exclude_unset= True)
    for key,value in update.items():
        setattr(find,key,value)

    db.commit()
    return JSONResponse(status_code= 200, content= {'Message' : 'Agent Updated Sucessfully.'})


@route.delete('/agents/{agent_id}')
def delete_agent(user : user_dependency, db : db_dependency, agent_id : int):
    require_roles(user, 'admin')

    find = db.query(Agents).filter(Agents.id == agent_id).first()
    if find is None:
        raise HTTPException(status_code= 404, detail= 'Agent Not Found.')

    db.query(Agents).filter(Agents.id == agent_id).delete()
    db.commit()

    return JSONResponse(status_code= 200, content= {'Message' : 'Agent Deleted Sucessfully.'})


@route.patch('/agents/{agent_id}/status')
def update_agent_status(user : user_dependency, db : db_dependency, agent_id : int, body : UpdateStatus):
    require_roles(user, 'admin','staff')

    find = db.query(Agents).filter(Agents.id == agent_id).first()
    if find is None:
        raise HTTPException(status_code= 404, detail= 'Agent Not Found.')

    find.status = body.status
    db.commit()

    return JSONResponse(status_code= 200, content= {'Message' : 'Agent Status Updated Sucessfully.'})
