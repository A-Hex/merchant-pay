from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.config import Settings
from app.container import get_today


def test_demo_today_freezes_the_clock():
    assert get_today(Settings(demo_today=date(2026, 11, 20))) == date(2026, 11, 20)


def test_clock_defaults_to_today_in_the_merchant_timezone():
    settings = Settings(demo_today=None)  # explicit: an ambient DEMO_TODAY must not leak in
    assert get_today(settings) == datetime.now(ZoneInfo(settings.timezone)).date()
