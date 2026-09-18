from database import SessionLocal
from fastapi import APIRouter,Depends,HTTPException
from fastapi.responses import JSONResponse
from models import Users
from pydantic import BaseModel, Field
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from typing import Annotated,Optional
from router.auth import get_current_user, require_roles
from router.audit import log_action


route = APIRouter()

bcrypt_context = CryptContext(schemes= ['bcrypt'], deprecated = 'auto')


class CreateUser(BaseModel):
    email : str
    username: str
    fastname: str
    lastname: str
    phone : Optional[str] = Field(default= None)
    password: str
    role : str

class UpdateUser(BaseModel):
    email : Optional[str] = Field(default= None)
    username: Optional[str] = Field(default= None)
    fastname: Optional[str] = Field(default= None)
    lastname: Optional[str] = Field(default= None)
    phone : Optional[str] = Field(default= None)

class UpdateRole(BaseModel):
    role : str

class UpdateStatus(BaseModel):
    is_active : bool


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependency = Annotated[Session, Depends(get_db)]
user_dependency = Annotated[Session, Depends(get_current_user)]


@route.post('/users')
def create_user(user : user_dependency, db : db_dependency, new_user : CreateUser):
    require_roles(user, 'admin')

    exist = db.query(Users).filter(
        (Users.email == new_user.email) | (Users.username == new_user.username)
    ).first()
    if exist is not None:
        raise HTTPException(status_code= 400, detail= 'Email or Username already registered.')

    user_model = Users(
        email = new_user.email,
        username = new_user.username,
        fastname = new_user.fastname,
        lastname = new_user.lastname,
        phone = new_user.phone,
        hash_password = bcrypt_context.hash(new_user.password),
        is_active = True,
        role = new_user.role
    )
    db.add(user_model)
    db.commit()
    db.refresh(user_model)

    log_action(db, user.get('id'), 'CREATE_USER', 'user', user_model.id)

    return JSONResponse(status_code= 201, content= {'Message' : 'User Created Sucessfully.'})


@route.get('/users')
def list_users(user : user_dependency, db : db_dependency,
                search : Optional[str] = None, role : Optional[str] = None,
                is_active : Optional[bool] = None,
                sort_by : str = 'create_at', sort_order : str = 'desc',
                page : int = 1, page_size : int = 20):
    require_roles(user, 'admin','staff')

    query = db.query(Users)

    if search:
        like = f'%{search}%'
        query = query.filter(
            (Users.username.ilike(like)) |
            (Users.email.ilike(like)) |
            (Users.fastname.ilike(like)) |
            (Users.lastname.ilike(like))
        )
    if role:
        query = query.filter(Users.role == role)
    if is_active is not None:
        query = query.filter(Users.is_active == is_active)

    sort_column = getattr(Users, sort_by, Users.create_at)
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


@route.get('/users/{user_id}')
def get_user_by_id(user : user_dependency, db : db_dependency, user_id : int):
    require_roles(user, 'admin','staff')

    find = db.query(Users).filter(Users.id == user_id).first()
    if find is None:
        raise HTTPException(status_code= 404, detail= 'User Not Found.')

    return find


@route.put('/users/{user_id}')
def update_user(user : user_dependency, db : db_dependency, user_id : int, update_info : UpdateUser):
    require_roles(user, 'admin')

    find = db.query(Users).filter(Users.id == user_id).first()
    if find is None:
        raise HTTPException(status_code= 404, detail= 'User Not Found.')

    update = update_info.model_dump(exclude_unset= True)
    for key,value in update.items():
        setattr(find,key,value)

    db.commit()
    log_action(db, user.get('id'), 'UPDATE_USER', 'user', user_id)

    return JSONResponse(status_code= 200, content= {'Message' : 'User Updated Sucessfully.'})


@route.delete('/users/{user_id}')
def delete_user(user : user_dependency, db : db_dependency, user_id : int):
    require_roles(user, 'admin')

    find = db.query(Users).filter(Users.id == user_id).first()
    if find is None:
        raise HTTPException(status_code= 404, detail= 'User Not Found.')

    db.query(Users).filter(Users.id == user_id).delete()
    db.commit()

    log_action(db, user.get('id'), 'DELETE_USER', 'user', user_id)

    return JSONResponse(status_code= 200, content= {'Message' : 'User Deleted Sucessfully.'})


@route.patch('/users/{user_id}/role')
def update_user_role(user : user_dependency, db : db_dependency, user_id : int, body : UpdateRole):
    require_roles(user, 'admin')

    find = db.query(Users).filter(Users.id == user_id).first()
    if find is None:
        raise HTTPException(status_code= 404, detail= 'User Not Found.')

    old_role = find.role
    find.role = body.role
    db.commit()

    log_action(db, user.get('id'), 'CHANGE_ROLE', 'user', user_id, f'{old_role} -> {body.role}')

    return JSONResponse(status_code= 200, content= {'Message' : 'User Role Updated Sucessfully.'})


@route.patch('/users/{user_id}/status')
def update_user_status(user : user_dependency, db : db_dependency, user_id : int, body : UpdateStatus):
    require_roles(user, 'admin')

    find = db.query(Users).filter(Users.id == user_id).first()
    if find is None:
        raise HTTPException(status_code= 404, detail= 'User Not Found.')

    find.is_active = body.is_active
    db.commit()

    log_action(db, user.get('id'), 'CHANGE_USER_STATUS', 'user', user_id, str(body.is_active))

    return JSONResponse(status_code= 200, content= {'Message' : 'User Status Updated Sucessfully.'})
