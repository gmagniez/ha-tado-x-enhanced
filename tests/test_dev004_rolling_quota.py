"""Pure-Python tests for DEV-004 rolling quota projection."""
import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / 'custom_components/tado_x/rolling_quota.py'
spec = importlib.util.spec_from_file_location('rolling_quota_test', MODULE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_minimum_and_full_window():
    q = module.RollingQuotaEstimate()
    start = datetime(2026, 11, 8, tzinfo=timezone.utc)
    for minute in range(61):
        q.observe(start + timedelta(minutes=minute), 20000, minute * 10)
        if minute == 9:
            assert q.estimate(start + timedelta(minutes=minute)) is None
        if minute == 10:
            assert q.estimate(start + timedelta(minutes=minute)) == 72.0
    assert q.estimate(start + timedelta(minutes=60)) == 72.0
    assert q.estimate(start + timedelta(minutes=64)) is None


def test_recent_rate_replaces_old_rate():
    q = module.RollingQuotaEstimate()
    start = datetime(2026, 11, 8, tzinfo=timezone.utc)
    used = 0
    for minute in range(121):
        if minute:
            used += 20 if minute <= 60 else 5
        now = start + timedelta(minutes=minute)
        q.observe(now, 20000, used)
    assert q.estimate(now) == 36.0  # 5/min over last hour


def test_reset_and_quota_change():
    q = module.RollingQuotaEstimate()
    start = datetime(2026, 11, 8, tzinfo=timezone.utc)
    for minute in range(12):
        q.observe(start + timedelta(minutes=minute), 20000, minute * 10)
    assert q.estimate(start + timedelta(minutes=11)) == 72.0
    q.observe(start + timedelta(minutes=12), 20000, 1)
    assert q.estimate(start + timedelta(minutes=12)) is None
    for minute in range(13, 24):
        q.observe(start + timedelta(minutes=minute), 20000, 1 + (minute - 12) * 10)
    assert q.estimate(start + timedelta(minutes=23)) == 72.0
    q.observe(start + timedelta(minutes=24), 10000, 5)
    assert q.estimate(start + timedelta(minutes=24)) is None


def test_burst_and_invalid_samples():
    q = module.RollingQuotaEstimate()
    start = datetime(2026, 11, 8, tzinfo=timezone.utc)
    q.observe(start, 20000, 0)
    q.observe(start + timedelta(seconds=1), 20000, 3)
    q.observe(start + timedelta(seconds=2), 20000, 5)
    q.observe(start + timedelta(minutes=11), 20000, 115)
    assert q.estimate(start + timedelta(minutes=11)) is not None
    q.observe(start + timedelta(minutes=12), 20000, -5)
    assert q.estimate(start + timedelta(minutes=11)) is not None
