"""FSM states for the Telegram bot conversation."""
from aiogram.fsm.state import State, StatesGroup


class Survey(StatesGroup):
    IDLE = State()
    PREMISES_OVERVIEW = State()
    ENTER_PREMISE = State()
    DISAMBIGUATE = State()
    CONFIRM_PREMISE = State()
    OFFER_PARKING_STORAGE = State()
    ENTER_PARKING_INPUT = State()
    OFFER_MORE = State()
    REMOVE_PREMISE = State()
    CONFIRM_REMOVE_PREMISE = State()
    VOTE_METHOD = State()
    BARRIER_VOTE = State()
    CONTACT_MANAGE = State()
    CONTACT_CONSENT = State()
    ENTER_PHONE = State()
    CONFIRM_DELETE = State()
    DONE = State()
    MY_DATA_VIEW = State()
    CONFIRM_FORGET = State()
    BROADCAST_WAIT_TEXT = State()
    TO_ADMINS_WAIT_TEXT = State()
