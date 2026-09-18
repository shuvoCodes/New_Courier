# Courier / Parcel Delivery Management System — Backend

FastAPI + SQLAlchemy (SQLite) backend implementing the full API surface described in the
project spec: authentication, user/address/branch/agent management, the parcel lifecycle
(create → assign → status workflow → tracking → payment), notifications, dashboards/reports
and an audit log.

Built in the same style/format as the uploaded `Library Managemant System` project:
`database.py` + `models.py` + `main.py` at the root, one `APIRouter` per domain under
`router/`, JWT auth via `python-jose`, password hashing via `passlib`/`bcrypt`, SQLAlchemy
`declarative_base`, `Annotated[...] = Depends(...)` dependency style, and
`JSONResponse(status_code=..., content={'Message': ...})` responses.

## Run it

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Interactive docs: `http://127.0.0.1:8000/docs`

## Roles

`customer`, `staff`, `admin`, `agent` — passed at registration (`role` field) or set later by
an admin via `PATCH /users/{user_id}/role`. Most endpoints check the caller's role with the
shared `require_roles()` helper in `router/auth.py`.

## Modules → files

| Spec section                | Router file                |
|------------------------------|-----------------------------|
| Authentication                | `router/auth.py`            |
| User Management                | `router/users.py`           |
| Address Management             | `router/addresses.py`       |
| Branch / Hub Management        | `router/branches.py`        |
| Delivery Agent Management      | `router/agents.py`          |
| Parcel CRUD / Search / Filter / Sort / Pagination / Status / History | `router/parcels.py` |
| Parcel Assignment               | `router/assignments.py`    |
| Public Tracking                 | `router/tracking.py`       |
| Delivery Fee Calculation        | `router/pricing.py`        |
| Payment / COD                   | `router/payments.py`       |
| Notifications                   | `router/notifications.py`  |
| Dashboard Statistics / Reports  | `router/reports.py`        |
| Audit Log                       | `router/audit.py`          |
| Status transition rules         | `router/status_workflow.py`|

## Parcel status workflow

```
CREATED -> CONFIRMED -> PICKED_UP -> AT_ORIGIN_HUB -> IN_TRANSIT
        -> AT_DESTINATION_HUB -> OUT_FOR_DELIVERY -> DELIVERED
CREATED/CONFIRMED -> CANCELLED
PICKED_UP/IN_TRANSIT/OUT_FOR_DELIVERY -> FAILED_DELIVERY -> OUT_FOR_DELIVERY | RETURNED
```

`PATCH /parcels/{id}/status` validates every transition against `router/status_workflow.py`
so the frontend can never push an invalid jump (e.g. `DELIVERED -> CREATED` is rejected with
a 400). Every accepted change is written to `parcel_status_history` (the data source for the
public tracking page) and triggers a notification to the customer.

## Delivery fee

`router/pricing.py` computes `weight tier + zone surcharge + express surcharge + COD charge`.
It's used both by `POST /pricing/calculate` and automatically inside `POST /parcels` — the
frontend-supplied fee is never trusted.

## Notes

- SQLite file `courier.db` is created automatically on first run (`Base.metadata.create_all`).
- Secrets (`SCERET_KEY` in `router/auth.py`) are placeholders — replace before deploying.
- `forgot-password` returns the reset token directly in the response for demo purposes; wire
  up an email provider before using this in production.
