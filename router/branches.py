from database import SessionLocal
from fastapi import APIRouter,Depends,HTTPException
from fastapi.responses import JSONResponse
from models import Branches
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Annotated,Optional
from router.auth import get_current_user, require_roles
from router.audit import log_action


route = APIRouter()


class CreateBranch(BaseModel):
    name : str
    address : str
    city : str

class UpdateBranch(BaseModel):
    name : Optional[str] = Field(default= None)
    address : Optional[str] = Field(default= None)
    city : Optional[str] = Field(default= None)

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


@route.post('/branches')
def create_branch(user : user_dependency, db : db_dependency, new_branch : CreateBranch):
    require_roles(user, 'admin','staff')

    branch_model = Branches(**new_branch.model_dump())
    db.add(branch_model)
    db.commit()
    db.refresh(branch_model)

    log_action(db, user.get('id'), 'CREATE_BRANCH', 'branch', branch_model.id)

    return JSONResponse(status_code= 201, content= {'Message' : 'Branch Created Sucessfully.'})


@route.get('/branches')
def list_branches(user : user_dependency, db : db_dependency,
                   search : Optional[str] = None, city : Optional[str] = None,
                   status : Optional[str] = None, page : int = 1, page_size : int = 20):
    require_roles(user, 'admin','staff')

    query = db.query(Branches)

    if search:
        like = f'%{search}%'
        query = query.filter((Branches.name.ilike(like)) | (Branches.city.ilike(like)))
    if city:
        query = query.filter(Branches.city.ilike(f'%{city}%'))
    if status:
        query = query.filter(Branches.status == status)

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


@route.get('/branches/{branch_id}')
def get_branch(user : user_dependency, db : db_dependency, branch_id : int):
    require_roles(user, 'admin','staff')

    find = db.query(Branches).filter(Branches.id == branch_id).first()
    if find is None:
        raise HTTPException(status_code= 404, detail= 'Branch Not Found.')

    return find


@route.put('/branches/{branch_id}')
def update_branch(user : user_dependency, db : db_dependency, branch_id : int, update_info : UpdateBranch):
    require_roles(user, 'admin','staff')

    find = db.query(Branches).filter(Branches.id == branch_id).first()
    if find is None:
        raise HTTPException(status_code= 404, detail= 'Branch Not Found.')

    update = update_info.model_dump(exclude_unset= True)
    for key,value in update.items():
        setattr(find,key,value)

    db.commit()
    return JSONResponse(status_code= 200, content= {'Message' : 'Branch Updated Sucessfully.'})


@route.delete('/branches/{branch_id}')
def delete_branch(user : user_dependency, db : db_dependency, branch_id : int):
    require_roles(user, 'admin')

    find = db.query(Branches).filter(Branches.id == branch_id).first()
    if find is None:
        raise HTTPException(status_code= 404, detail= 'Branch Not Found.')

    db.query(Branches).filter(Branches.id == branch_id).delete()
    db.commit()

    return JSONResponse(status_code= 200, content= {'Message' : 'Branch Deleted Sucessfully.'})


@route.patch('/branches/{branch_id}/status')
def update_branch_status(user : user_dependency, db : db_dependency, branch_id : int, body : UpdateStatus):
    require_roles(user, 'admin','staff')

    find = db.query(Branches).filter(Branches.id == branch_id).first()
    if find is None:
        raise HTTPException(status_code= 404, detail= 'Branch Not Found.')

    find.status = body.status
    db.commit()

    return JSONResponse(status_code= 200, content= {'Message' : 'Branch Status Updated Sucessfully.'})
