from database import Base
from sqlalchemy import Column,Integer,String,Boolean,DateTime,Float, ForeignKey, Text
from datetime import datetime


class Users(Base):

    __tablename__ = 'users'

    id = Column(Integer,primary_key= True, index= True)
    email = Column(String,unique= True, index= True)
    username = Column(String,unique= True, index= True)
    fastname = Column(String)
    lastname = Column(String)
    phone = Column(String, nullable= True)
    hash_password = Column(String)
    is_active = Column(Boolean, default= True)
    role = Column(String, default= 'customer')            # customer, staff, admin, agent
    reset_token = Column(String, nullable= True)
    reset_token_expiry = Column(DateTime, nullable= True)
    create_at = Column(DateTime, default= datetime.now)


class Addresses(Base):

    __tablename__ = 'addresses'

    id = Column(Integer, primary_key= True, index= True)
    user_id = Column(Integer, ForeignKey('users.id'))
    label = Column(String)                                 # Home, Office ...
    address_line = Column(String)
    city = Column(String)
    area = Column(String, nullable= True)
    phone = Column(String, nullable= True)
    is_default = Column(Boolean, default= False)
    create_at = Column(DateTime, default= datetime.now)


class Branches(Base):

    __tablename__ = 'branches'

    id = Column(Integer, primary_key= True, index= True)
    name = Column(String)
    address = Column(String)
    city = Column(String)
    status = Column(String, default= 'active')             # active, inactive
    create_at = Column(DateTime, default= datetime.now)


class Agents(Base):

    __tablename__ = 'agents'

    id = Column(Integer, primary_key= True, index= True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable= True)
    branch_id = Column(Integer, ForeignKey('branches.id'), nullable= True)
    name = Column(String)
    phone = Column(String)
    vehicle_type = Column(String, nullable= True)
    status = Column(String, default= 'available')          # available, busy, offline
    create_at = Column(DateTime, default= datetime.now)


class Parcels(Base):

    __tablename__ = 'parcels'

    id = Column(Integer, primary_key= True, index= True)
    tracking_code = Column(String, unique= True, index= True)
    customer_id = Column(Integer, ForeignKey('users.id'))
    pickup_address_id = Column(Integer, ForeignKey('addresses.id'))
    delivery_address_id = Column(Integer, ForeignKey('addresses.id'))
    origin_branch_id = Column(Integer, ForeignKey('branches.id'), nullable= True)
    destination_branch_id = Column(Integer, ForeignKey('branches.id'), nullable= True)
    assigned_agent_id = Column(Integer, ForeignKey('agents.id'), nullable= True)
    parcel_type = Column(String)                            # document, package, fragile ...
    service_type = Column(String, default= 'standard')       # standard, express
    weight = Column(Float, default= 0.5)
    cod_amount = Column(Float, default= 0.0)
    delivery_fee = Column(Float, default= 0.0)
    notes = Column(String, nullable= True)
    status = Column(String, default= 'CREATED')
    payment_status = Column(String, default= 'PENDING')      # PENDING, PAID, FAILED, REFUNDED
    estimated_delivery = Column(DateTime, nullable= True)
    create_at = Column(DateTime, default= datetime.now)
    update_at = Column(DateTime, default= datetime.now, onupdate= datetime.now)


class ParcelStatusHistory(Base):

    __tablename__ = 'parcel_status_history'

    id = Column(Integer, primary_key= True, index= True)
    parcel_id = Column(Integer, ForeignKey('parcels.id'))
    status = Column(String)
    note = Column(String, nullable= True)
    changed_by_id = Column(Integer, ForeignKey('users.id'), nullable= True)
    create_at = Column(DateTime, default= datetime.now)


class Assignments(Base):

    __tablename__ = 'assignments'

    id = Column(Integer, primary_key= True, index= True)
    parcel_id = Column(Integer, ForeignKey('parcels.id'))
    agent_id = Column(Integer, ForeignKey('agents.id'))
    assigned_by_id = Column(Integer, ForeignKey('users.id'), nullable= True)
    status = Column(String, default= 'assigned')             # assigned, accepted, rejected, reassigned
    assigned_at = Column(DateTime, default= datetime.now)
    responded_at = Column(DateTime, nullable= True)


class Payments(Base):

    __tablename__ = 'payments'

    id = Column(Integer, primary_key= True, index= True)
    parcel_id = Column(Integer, ForeignKey('parcels.id'))
    amount = Column(Float, default= 0.0)
    method = Column(String, default= 'COD')                  # COD, ONLINE
    status = Column(String, default= 'PENDING')               # PENDING, PAID, FAILED, REFUNDED
    transaction_id = Column(String, nullable= True)
    paid_at = Column(DateTime, nullable= True)
    create_at = Column(DateTime, default= datetime.now)


class Notifications(Base):

    __tablename__ = 'notifications'

    id = Column(Integer, primary_key= True, index= True)
    user_id = Column(Integer, ForeignKey('users.id'))
    message = Column(String)
    is_read = Column(Boolean, default= False)
    create_at = Column(DateTime, default= datetime.now)


class AuditLogs(Base):

    __tablename__ = 'audit_logs'

    id = Column(Integer, primary_key= True, index= True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable= True)
    action = Column(String)
    target_type = Column(String, nullable= True)
    target_id = Column(Integer, nullable= True)
    details = Column(Text, nullable= True)
    create_at = Column(DateTime, default= datetime.now)
