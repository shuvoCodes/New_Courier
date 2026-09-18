STATUSES = [
    'CREATED','CONFIRMED','PICKED_UP','AT_ORIGIN_HUB','IN_TRANSIT',
    'AT_DESTINATION_HUB','OUT_FOR_DELIVERY','DELIVERED','CANCELLED',
    'FAILED_DELIVERY','RETURNED'
]

# What a parcel currently in status X is allowed to move to next.
ALLOWED_TRANSITIONS = {
    'CREATED'             : ['CONFIRMED','CANCELLED'],
    'CONFIRMED'           : ['PICKED_UP','CANCELLED'],
    'PICKED_UP'           : ['AT_ORIGIN_HUB','FAILED_DELIVERY'],
    'AT_ORIGIN_HUB'       : ['IN_TRANSIT'],
    'IN_TRANSIT'          : ['AT_DESTINATION_HUB','FAILED_DELIVERY'],
    'AT_DESTINATION_HUB'  : ['OUT_FOR_DELIVERY'],
    'OUT_FOR_DELIVERY'    : ['DELIVERED','FAILED_DELIVERY'],
    'FAILED_DELIVERY'     : ['OUT_FOR_DELIVERY','RETURNED'],
    'DELIVERED'           : [],
    'CANCELLED'           : [],
    'RETURNED'            : [],
}


def is_transition_allowed(current_status: str, new_status: str) -> bool:
    if new_status not in STATUSES:
        return False
    return new_status in ALLOWED_TRANSITIONS.get(current_status, [])
