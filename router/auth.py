from database import SessionLocal
from datetime import timedelta, datetime, timezone
from fastapi import FastAPI,APIRouter,Depends,HTTPException
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm,OAuth2PasswordBearer
from models import Users
from pydantic import BaseModel, Field
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from typing import Annotated,Optional
from jose import jwt, JWTError
import secrets


route = APIRouter()

bcrypt_context = CryptContext(schemes= ['bcrypt'], deprecated = 'auto')
OAuth2_bearer = OAuth2PasswordBearer(tokenUrl= 'login')

SCERET_KEY = '5bb7def1ea99e60cba3ae25ca6fb31d701091d833b9d5b7bdd0c14c9e591cfc4'
ALGORITHM = 'HS256'
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7
RESET_TOKEN_EXPIRE_MINUTES = 15


class CreateUser(BaseModel):
    email : str
    username: str
    fastname: str
    lastname: str
    phone : Optional[str] = Field(default= None)
    password: str
    role : Optional[str] = Field(default= 'customer')

class UpdateUser(BaseModel):
    email : Optional[str] = Field (default= None)
    username: Optional[str] = Field (default= None)
    fastname: Optional[str] = Field (default= None)
    lastname: Optional[str] = Field (default= None)
    phone : Optional[str] = Field (default= None)

class UpdatePassword(BaseModel):
    current_password : str
    new_password : str

class RefreshRequest(BaseModel):
    refresh_token : str

class ForgotPassword(BaseModel):
    email : str

class ResetPassword(BaseModel):
    reset_token : str
    new_password : str


def authenticate_user(username,password,db):
    user = db.query(Users).filter(Users.username == username).first()
    if user is None:
        return False
    if not bcrypt_context.verify(password,user.hash_password):
        return False
    return user

def create_access_token(username: str, user_id: int, role:str, expires_delta = timedelta(minutes= ACCESS_TOKEN_EXPIRE_MINUTES)):
    encode = {
        'sub' : username,
        'id' : user_id,
        'role' : role,
        'type' : 'access'
    }
    expire = datetime.now(timezone.utc) + expires_delta
    encode.update({'exp':expire})
    return jwt.encode(encode, SCERET_KEY, algorithm= ALGORITHM)

def create_refresh_token(username: str, user_id: int, role:str, expires_delta = timedelta(days= REFRESH_TOKEN_EXPIRE_DAYS)):
    encode = {
        'sub' : username,
        'id' : user_id,
        'role' : role,
        'type' : 'refresh'
    }
    expire = datetime.now(timezone.utc) + expires_delta
    encode.update({'exp':expire})
    return jwt.encode(encode, SCERET_KEY, algorithm= ALGORITHM)

def get_current_user(token: Annotated[str, Depends(OAuth2_bearer)]):
    try:
        pyload = jwt.decode(token, SCERET_KEY, algorithms= ALGORITHM)
        username: str = pyload.get('sub')
        user_id : int = pyload.get('id')
        role : str = pyload.get('role')
        token_type : str = pyload.get('type')
        if username is None or user_id is None or token_type != 'access':
            raise HTTPException(status_code= 401, detail= 'Failed Authentication.')
        return {'username' : username, 'id' : user_id, 'role' : role}
    except JWTError:
        raise HTTPException(status_code= 401, detail= 'Failed Authentication.')


def require_roles(user, *roles):
    if user is None or user.get('role') not in roles:
        raise HTTPException(status_code= 403, detail= 'Not enough permission.')


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependancey = Annotated[Session,Depends(get_db)]
user_dependancey = Annotated[Session, Depends(get_current_user)]


@route.post('/auth/register')
def register(db : db_dependancey, new_user: CreateUser):

    exist = db.query(Users).filter(
        (Users.email == new_user.email) | (Users.username == new_user.username)
    ).first()
    if exist is not None:
        raise HTTPException(status_code= 400, detail= 'Email or Username already registered.')

    user_model = Users(
        email = new_user.email,
        username = new_user.username,
        fastname= new_user.fastname,
        lastname = new_user.lastname,
        phone = new_user.phone,
        hash_password = bcrypt_context.hash(new_user.password),
        is_active = True,
        role = new_user.role if new_user.role in ['customer','staff','admin','agent'] else 'customer'
    )
    db.add(user_model)
    db.commit()

    return JSONResponse(status_code= 201, content= {'Message' : 'User Registered Sucessfully.'})


@route.post('/auth/login')
def login(db: db_dependancey, from_data: Annotated[OAuth2PasswordRequestForm,Depends()]):
    user = authenticate_user(from_data.username, from_data.password,db)

    if not user:
        raise HTTPException(status_code= 401, detail= 'Failed Authentication.')

    if not user.is_active:
        raise HTTPException(status_code= 401, detail= 'Account is inactive.')

    access_token = create_access_token(user.username,user.id,user.role)
    refresh_token = create_refresh_token(user.username,user.id,user.role)

    return {
        'access_token' : access_token,
        'refresh_token' : refresh_token,
        'token_type' : 'bearer'
    }


@route.post('/auth/refresh')
def refresh(db: db_dependancey, body : RefreshRequest):
    try:
        pyload = jwt.decode(body.refresh_token, SCERET_KEY, algorithms= ALGORITHM)
        if pyload.get('type') != 'refresh':
            raise HTTPException(status_code= 401, detail= 'Invalid Refresh Token.')

        user = db.query(Users).filter(Users.id == pyload.get('id')).first()
        if user is None:
            raise HTTPException(status_code= 401, detail= 'Invalid Refresh Token.')

        access_token = create_access_token(user.username,user.id,user.role)
        return {'access_token' : access_token, 'token_type' : 'bearer'}
    except JWTError:
        raise HTTPException(status_code= 401, detail= 'Invalid Refresh Token.')


@route.post('/auth/logout')
def logout(user : user_dependancey):
    if user is None:
        raise HTTPException(status_code= 401, detail= 'Failed Authentication.')
    # Stateless JWT - client just discards the tokens.
    return JSONResponse(status_code= 200, content= {'Message' : 'Logged out Sucessfully.'})


@route.get('/auth/me')
def get_user(user: user_dependancey ,db: db_dependancey):
    if user is None:
        raise HTTPException(status_code=401, detail='Failed Authentication')

    curret_user = db.query(Users).filter(Users.id == user.get('id')).first()

    if curret_user is None:
        raise HTTPException(status_code=404, detail='User Not Found')

    return {
        'id' : curret_user.id,
        'email' : curret_user.email,
        'username'  : curret_user.username,
        'fastname'  : curret_user.fastname,
        'lastname'  : curret_user.lastname,
        'phone' : curret_user.phone,
        'is_active'  : curret_user.is_active,
        'role'  : curret_user.role
    }


@route.put('/auth/me')
def update_me(user: user_dependancey,db: db_dependancey, update_info: UpdateUser):
    if user is None:
        raise HTTPException(status_code= 401, detail='Failed Authentication')

    find = db.query(Users).filter(Users.id == user.get('id')).first()
    update = update_info.model_dump(exclude_unset= True)

    for key,value in update.items():
        setattr(find,key, value)

    db.commit()
    return JSONResponse(status_code= 200, content={'Message' : 'Profile Updated Successfully'})


@route.post('/auth/change-password')
def update_password(user: user_dependancey, db : db_dependancey, update_pass : UpdatePassword):
    if user is None:
        raise HTTPException(status_code= 401, detail='Failed Authentication')

    find = db.query(Users).filter(Users.id == user.get('id')).first()

    if not bcrypt_context.verify(update_pass.current_password,find.hash_password):
        raise HTTPException(status_code= 401, detail='Wrong Password')

    find.hash_password = bcrypt_context.hash(update_pass.new_password)
    db.commit()
    return JSONResponse(status_code=200, content= {'Message' : 'Password Updated Sucessfully'})


@route.post('/auth/forgot-password')
def forgot_password(db: db_dependancey, body: ForgotPassword):
    user = db.query(Users).filter(Users.email == body.email).first()

    # Do not reveal whether the email exists.
    if user is None:
        return JSONResponse(status_code= 200, content= {'Message' : 'If the email exists, a reset link has been sent.'})

    token = secrets.token_urlsafe(32)
    user.reset_token = token
    user.reset_token_expiry = datetime.now() + timedelta(minutes= RESET_TOKEN_EXPIRE_MINUTES)
    db.commit()

    # In production this token would be emailed to the user instead of returned here.
    return JSONResponse(status_code= 200, content= {'Message' : 'If the email exists, a reset link has been sent.', 'reset_token' : token})


@route.post('/auth/reset-password')
def reset_password(db: db_dependancey, body: ResetPassword):
    user = db.query(Users).filter(Users.reset_token == body.reset_token).first()

    if user is None or user.reset_token_expiry is None or user.reset_token_expiry < datetime.now():
        raise HTTPException(status_code= 400, detail= 'Reset token is invalid or expired.')

    user.hash_password = bcrypt_context.hash(body.new_password)
    user.reset_token = None
    user.reset_token_expiry = None
    db.commit()

    return JSONResponse(status_code= 200, content= {'Message' : 'Password Reset Sucessfully.'})
