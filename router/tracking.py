from database import SessionLocal
from fastapi import APIRouter,Depends,HTTPException
from models import Parcels, ParcelStatusHistory, Branches
from sqlalchemy.orm import Session
from typing import Annotated


route = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependency = Annotated[Session, Depends(get_db)]


@route.get('/tracking/{tracking_code}')
def track_parcel(db : db_dependency, tracking_code : str):
    parcel = db.query(Parcels).filter(Parcels.tracking_code == tracking_code).first()
    if parcel is None:
        raise HTTPException(status_code= 404, detail= 'Tracking Code Not Found.')

    origin = db.query(Branches).filter(Branches.id == parcel.origin_branch_id).first()
    destination = db.query(Branches).filter(Branches.id == parcel.destination_branch_id).first()

    history = db.query(ParcelStatusHistory).filter(
        ParcelStatusHistory.parcel_id == parcel.id
    ).order_by(ParcelStatusHistory.create_at.asc()).all()

    # Only publicly-safe fields are exposed - no customer personal information.
    return {
        'tracking_code' : parcel.tracking_code,
        'status' : parcel.status,
        'origin' : origin.city if origin else None,
        'destination' : destination.city if destination else None,
        'estimated_delivery' : parcel.estimated_delivery,
        'history' : [
            {'status' : h.status, 'note' : h.note, 'create_at' : h.create_at} for h in history
        ]
    }
