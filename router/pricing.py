from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Optional


route = APIRouter()

COD_CHARGE_PERCENT = 1.0          # 1% of cod_amount
COD_CHARGE_MIN = 10.0
EXPRESS_SURCHARGE = 50.0
ZONE_SURCHARGE = {
    'inside_city' : 0.0,
    'outside_city' : 40.0,
    'outside_zone' : 80.0
}


def weight_base_fee(weight: float) -> float:
    if weight <= 0:
        weight = 0.5
    if weight <= 2:
        return 80.0
    if weight <= 5:
        return 150.0
    # Beyond 5kg -> base for 5kg + extra per kg
    extra_kg = weight - 5
    return 150.0 + extra_kg * 30.0


def cod_charge(cod_amount: float) -> float:
    if not cod_amount or cod_amount <= 0:
        return 0.0
    charge = cod_amount * (COD_CHARGE_PERCENT / 100)
    return round(max(charge, COD_CHARGE_MIN), 2)


def calculate_delivery_fee(weight: float, service_type: str = 'standard', cod_amount: float = 0.0, zone: str = 'inside_city') -> float:
    fee = weight_base_fee(weight)
    fee += ZONE_SURCHARGE.get(zone, 0.0)

    if service_type == 'express':
        fee += EXPRESS_SURCHARGE

    fee += cod_charge(cod_amount)

    return round(fee, 2)


class PricingRequest(BaseModel):
    weight : float
    service_type : Optional[str] = Field(default= 'standard')
    cod_amount : Optional[float] = Field(default= 0.0)
    zone : Optional[str] = Field(default= 'inside_city')


@route.post('/pricing/calculate')
def calculate_pricing(body : PricingRequest):
    fee = calculate_delivery_fee(body.weight, body.service_type, body.cod_amount, body.zone)
    return {
        'weight' : body.weight,
        'service_type' : body.service_type,
        'zone' : body.zone,
        'cod_amount' : body.cod_amount,
        'delivery_fee' : fee
    }
