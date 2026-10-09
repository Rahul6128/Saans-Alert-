import sys, os; sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from core import *

def test_aqi_breakpoints():
    assert pm25_to_aqi(30) == 50 and pm25_to_aqi(90) == 200 and pm25_to_aqi(600) == 500

def test_idw_exact_and_between():
    st = [(28.60, 77.20, 100), (28.70, 77.20, 200)]
    assert idw(st, 28.60, 77.20) == 100
    assert 100 < idw(st, 28.65, 77.20) < 200

def test_forecast_persistence_fades_to_diurnal():
    hist = [(h % 24, 300 if h % 24 in (8, 9) else 100) for h in range(24)]
    fc = dict(forecast(hist + [(0, 100)]))
    assert fc[8] > fc[2]          # learned the morning peak
    h = [(i % 24, 400) for i in range(5)]
    assert forecast(h)[0][1] > 300  # short history -> persistence

def test_plan_moves_pe_to_cleaner_hour():
    fc = [(h, 250 if h < 11 else 60) for h in range(8, 20)]
    p = plan(fc, 9)
    assert p["verdict"] == "INDOORS" and p["best_hour"] >= 11

def test_verdict_levels():
    assert verdict(30, 45)[0] == "GO"
    assert verdict(60, 45)[0] == "SHORTEN"
    assert verdict(300, 45)[0] == "INDOORS"

if __name__ == "__main__":  # run without pytest: python tests/test_core.py
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f(); print("ok", n)
