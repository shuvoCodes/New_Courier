from fastapi import FastAPI
import models
from database import engine
from router import auth, users, addresses, branches, agents, parcels, assignments, tracking, payments, notifications, reports, audit, pricing

app = FastAPI(title= 'Courier / Parcel Delivery Management System')

models.Base.metadata.create_all(bind= engine)

app.include_router(auth.route, tags= ['Authentication'])
app.include_router(users.route, tags= ['User Management'])
app.include_router(addresses.route, tags= ['Address Management'])
app.include_router(branches.route, tags= ['Branch / Hub Management'])
app.include_router(agents.route, tags= ['Delivery Agent Management'])
app.include_router(parcels.route, tags= ['Parcel Management'])
app.include_router(assignments.route, tags= ['Parcel Assignment'])
app.include_router(tracking.route, tags= ['Public Tracking'])
app.include_router(pricing.route, tags= ['Delivery Fee Calculation'])
app.include_router(payments.route, tags= ['Payment / COD'])
app.include_router(notifications.route, tags= ['Notifications'])
app.include_router(reports.route, tags= ['Dashboard & Reports'])
app.include_router(audit.route, tags= ['Audit Log'])


@app.get('/')
def root():
    return {'Message' : 'Courier / Parcel Delivery Management System API is running.'}
