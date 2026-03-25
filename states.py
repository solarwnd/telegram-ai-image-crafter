from aiogram.fsm.state import State, StatesGroup


class BotStates(StatesGroup):
    waiting_for_intro_confirmation = State()
    waiting_for_mode_selection = State()
    waiting_for_view_selection = State()
    waiting_for_proportion_selection = State()
    processing_image = State()
