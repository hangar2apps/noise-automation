import sys
from datetime import time as dtime
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from noise_trigger import Detector, RateLimiter, in_window, rms_dbfs  # noqa: E402


def test_rms_dbfs():
    assert abs(rms_dbfs(np.ones(100, dtype=np.float32))) < 1e-6
    assert abs(rms_dbfs(np.full(100, 0.1, dtype=np.float32)) + 20) < 1e-4
    assert rms_dbfs(np.zeros(100, dtype=np.float32)) == -200


def test_window_overnight():
    s, e = dtime(22, 0), dtime(6, 30)
    assert in_window(dtime(23, 0), s, e)
    assert in_window(dtime(2, 0), s, e)
    assert not in_window(dtime(12, 0), s, e)
    assert not in_window(dtime(6, 30), s, e)


def test_window_same_day_and_always():
    assert in_window(dtime(10, 0), dtime(9, 0), dtime(17, 0))
    assert not in_window(dtime(18, 0), dtime(9, 0), dtime(17, 0))
    assert in_window(dtime(3, 0), dtime(0, 0), dtime(0, 0))


def test_detector_ignores_single_click():
    d = Detector(-30, window=5, min_loud=3)
    assert not any(d.update(x) for x in [-10, -60, -60, -60, -60, -10, -60])


def test_detector_fires_on_sustained():
    d = Detector(-30, window=5, min_loud=3)
    assert [d.update(x) for x in [-20, -60, -20, -20]] == [False, False, False, True]
    assert not d.update(-20)  # history cleared after fire


def test_rate_limiter():
    r = RateLimiter(cooldown_s=20, max_per_hour=2)
    assert r.allow(0)
    r.record(0)
    assert not r.allow(10)
    assert r.allow(25)
    r.record(25)
    assert not r.allow(100)  # hourly cap
    assert r.allow(3601)  # first event aged out
