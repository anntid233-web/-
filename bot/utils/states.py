from enum import Enum


class UserState(Enum):
    NONE = "none"
    CHOOSING_PROXY_TYPE = "choosing_proxy_type"
    CHOOSING_COUNTRY = "choosing_country"
    CHOOSING_COUNT = "choosing_count"
    CHOOSING_PERIOD = "choosing_period"
    ENTERING_DEPOSIT_AMOUNT = "entering_deposit_amount"
    CHANGING_REF_CODE = "changing_ref_code"


class AdminState(Enum):
    NONE = "none"
    BROADCAST_TEXT = "broadcast_text"
    BROADCAST_CONFIRM = "broadcast_confirm"
    SEARCH_USER = "search_user"
    CHANGE_BALANCE = "change_balance"
    SET_MIN_DEPOSIT = "set_min_deposit"
    SET_REF_BONUS = "set_ref_bonus"
    SET_MARKUP = "set_markup"
    MESSAGE_USER = "message_user"
    ADD_PROXY = "add_proxy"


# Global state storage (in production, use Redis)
user_states = {}
admin_states = {}