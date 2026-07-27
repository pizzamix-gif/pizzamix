from aiogram.fsm.state import State, StatesGroup


class CheckoutStates(StatesGroup):
    waiting_address = State()
    waiting_phone = State()
    waiting_comment = State()


class AdminStates(StatesGroup):
    # Generic single-value text input state. Which field/flow it belongs to
    # is stored in FSM data under "action" (and related keys) — this avoids
    # declaring a separate State for every editable field.
    waiting_input = State()
