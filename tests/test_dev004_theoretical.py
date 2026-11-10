"""Pure source-level tests of DEV-004 theoretical quota projection."""
import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'custom_components' / 'tado_x'

def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / (name + '.py'))
    mod = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

projection = load('api_projection')
rolling = load('rolling_quota')

def settings(**overrides):
    data = dict(quota=20000, main_interval=30, multiplier=5, weather=True,
                air_comfort=True, running_times=True, flow_temp=False,
                holiday_mode=True, mobile_devices=False, hot_water=True,
                schedule_enabled=True, schedule_interval=3600, room_count=19)
    data.update(overrides)
    return projection.project_daily_api_usage(**data)

def test_fast_polling_breakdown():
    p = settings()
    assert p.main == 11520
    assert p.supplementary == 2305
    assert p.schedule == 912
    assert p.total == 14737
    assert round(p.percentage, 2) == 73.69

def test_multiplier_and_disabled_features():
    p = settings(multiplier=1)
    assert p.supplementary == 11531
    p = settings(weather=False, holiday_mode=False, schedule_enabled=False)
    assert p.supplementary == 1153
    assert p.schedule == 0

def test_slow_polling():
    p = settings(main_interval=3600, multiplier=10, schedule_interval=86400)
    assert p.main == 96
    assert p.supplementary == 10.6
    assert p.schedule == 38
    assert round(p.total, 1) == 144.6

def test_invalid_and_quota():
    assert settings(quota=0) is None
    assert settings(main_interval=0) is None
    assert settings(schedule_interval=0) is None
    assert settings(schedule_enabled=False, schedule_interval=0) is not None
    assert abs(settings(quota=100).percentage - settings().percentage * 200) < 1e-8

def test_rolling_freshness_tracks_main_interval():
    q = rolling.RollingQuotaEstimate()
    start = datetime(2026, 11, 8, tzinfo=timezone.utc)
    q.set_main_poll_interval(3600)
    q.observe(start, 20000, 0)
    q.observe(start + timedelta(hours=1), 20000, 10)
    assert q.estimate(start + timedelta(hours=1, minutes=30)) is not None
    assert q.estimate(start + timedelta(hours=2, minutes=31)) is None
    q.set_main_poll_interval(30)
    assert q.estimate(start + timedelta(hours=1, minutes=3)) is None
