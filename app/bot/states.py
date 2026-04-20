from aiogram.fsm.state import State, StatesGroup


class AdGenerationStates(StatesGroup):
    waiting_niche = State()
    waiting_segment_selection = State()
    waiting_ads_count = State()
    waiting_cities = State()
    waiting_geo_type = State()
    waiting_confirmation = State()
