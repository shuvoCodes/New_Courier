from database import SessionLocal
from fastapi import APIRouter,Depends,HTTPException
from fastapi.responses import JSONResponse
from models import Addresses
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Annotated,Optional
from router.auth import get_current_user


route = APIRouter()


class CreateAddress(BaseModel):
    label : str
    address_line : str
    city : str
    area : Optional[str] = Field(default= None)
    phone : Optional[str] = Field(default= None)
    is_default : Optional[bool] = Field(default= False)

class UpdateAddress(BaseModel):
    label : Optional[str] = Field(default= None)
    address_line : Optional[str] = Field(default= None)
    city : Optional[str] = Field(default= None)
    area : Optional[str] = Field(default= None)
    phone : Optional[str] = Field(default= None)
    is_default : Optional[bool] = Field(default= None)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependency = Annotated[Session, Depends(get_db)]
user_dependency = Annotated[Session, Depends(get_current_user)]


@route.post('/addresses')
def create_address(user : user_dependency, db : db_dependency, new_address : CreateAddress):
    if user is None:
        raise HTTPException(status_code= 401, detail= 'Failed Authentication.')

    if new_address.is_default:
        db.query(Addresses).filter(Addresses.user_id == user.get('id')).update({'is_default' : False})

    address_model = Addresses(
        user_id = user.get('id'),
        **new_address.model_dump()
    )
    db.add(address_model)
    db.commit()

    return JSONResponse(status_code= 201, content= {'Message' : 'Address Added Sucessfully.'})


@route.get('/addresses')
def list_addresses(user : user_dependency, db : db_dependency):
    if user is None:
        raise HTTPException(status_code= 401, detail= 'Failed Authentication.')

    return db.query(Addresses).filter(Addresses.user_id == user.get('id')).all()


@route.get('/addresses/{address_id}')
def get_address(user : user_dependency, db : db_dependency, address_id : int):
    if user is None:
        raise HTTPException(status_code= 401, detail= 'Failed Authentication.')

    find = db.query(Addresses).filter(Addresses.id == address_id, Addresses.user_id == user.get('id')).first()
    if find is None:
        raise HTTPException(status_code= 404, detail= 'Address Not Found.')

    return find


@route.put('/addresses/{address_id}')
def update_address(user : user_dependency, db : db_dependency, address_id : int, update_info : UpdateAddress):
    if user is None:
        raise HTTPException(status_code= 401, detail= 'Failed Authentication.')

    find = db.query(Addresses).filter(Addresses.id == address_id, Addresses.user_id == user.get('id')).first()
    if find is None:
        raise HTTPException(status_code= 404, detail= 'Address Not Found.')

    update = update_info.model_dump(exclude_unset= True)

    if update.get('is_default'):
        db.query(Addresses).filter(Addresses.user_id == user.get('id')).update({'is_default' : False})

    for key,value in update.items():
        setattr(find,key,value)

    db.commit()
    return JSONResponse(status_code= 200, content= {'Message' : 'Address Updated Sucessfully.'})


@route.delete('/addresses/{address_id}')
def delete_address(user : user_dependency, db : db_dependency, address_id : int):
    if user is None:
        raise HTTPException(status_code= 401, detail= 'Failed Authentication.')

    find = db.query(Addresses).filter(Addresses.id == address_id, Addresses.user_id == user.get('id')).first()
    if find is None:
        raise HTTPException(status_code= 404, detail= 'Address Not Found.')

    db.query(Addresses).filter(Addresses.id == address_id).delete()
    db.commit()

    return JSONResponse(status_code= 200, content= {'Message' : 'Address Deleted Sucessfully.'})
