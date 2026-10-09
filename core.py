"""SaansAlert core: spatial estimate -> short-term forecast -> exposure-dose planning.
Pure Python, no AWS imports, so it is unit-testable and runs anywhere."""
import math

# CPCB PM2.5 sub-index breakpoints (ug/m3 -> AQI)
_BP = [(0, 30, 0, 50), (30, 60, 50, 100), (60, 90, 100, 200),
       (90, 120, 200, 300), (120, 250, 300, 400), (250, 500, 400, 500)]
# Approx. child inhalation rates (m3/h). Assumption: swap in values from a cited handbook.
RATE = {"rest": 0.5, "light": 1.0, "heavy": 2.2}
# Reference budget = 45 min of heavy activity at 37.5 ug/m3 (WHO 2021 interim target 3, 24h).
# This cut-off is a tunable heuristic, not a medical standard.
REF_DOSE = 37.5 * RATE["heavy"] * 45 / 60


def pm25_to_aqi(pm):
    for lo, hi, a_lo, a_hi in _BP:
        if pm <= hi:
            return round(a_lo + (pm - lo) * (a_hi - a_lo) / (hi - lo))
    return 500


def _km(la1, lo1, la2, lo2):
    p = math.pi / 180
    a = math.sin((la2 - la1) * p / 2) ** 2 + math.cos(la1 * p) * math.cos(la2 * p) * math.sin((lo2 - lo1) * p / 2) ** 2
    return 12742 * math.asin(math.sqrt(a))


def idw(stations, lat, lon, power=2.0, k=4):
    """Inverse-distance-weighted PM2.5 at a school from the k nearest stations.
    stations: [(lat, lon, pm25)]"""
    near = sorted((_km(s[0], s[1], lat, lon), s[2]) for s in stations)[:k]
    if not near:
        raise ValueError("no stations")
    if near[0][0] < 0.05:
        return near[0][1]
    w = [1 / d ** power for d, _ in near]
    return sum(wi * v for wi, (_, v) in zip(w, near)) / sum(w)


def forecast(history, horizon=12, tau=6.0):
    """history: [(hour_of_day, pm)] oldest->newest. Blend persistence (fades with
    time constant tau) into a diurnal-profile estimate built from the last 24 points."""
    last_h, last = history[-1]
    recent = history[-24:]
    level = sum(v for _, v in recent) / len(recent)
    by_hour = {}
    for h, v in recent:
        by_hour.setdefault(h, []).append(v)
    ratio = {h: sum(v) / len(v) / level for h, v in by_hour.items()} if len(recent) >= 24 and level > 0 else {}
    out = []
    for k in range(1, horizon + 1):
        h = (last_h + k) % 24
        w = math.exp(-k / tau)
        out.append((h, w * last + (1 - w) * level * ratio.get(h, 1.0)))
    return out


def allowed_minutes(pm, activity):
    return REF_DOSE * 60 / (max(pm, 1e-6) * RATE[activity])


def verdict(pm, minutes, activity="heavy"):
    ok = allowed_minutes(pm, activity)
    if ok >= minutes:
        return "GO", minutes
    if ok >= 15:
        return "SHORTEN", int(ok // 5 * 5)
    return "INDOORS", 0


def plan(fc, req_hour, minutes=45, activity="heavy", open_h=8, close_h=15):
    """fc: output of forecast(). Compare the scheduled outdoor slot to the cleanest slot today."""
    by_h = dict(fc)
    cand = [h for h in by_h if open_h <= h <= close_h - minutes / 60]
    best = min(cand, key=by_h.get) if cand else None
    pm = by_h.get(req_hour)
    v, m = verdict(pm, minutes, activity) if pm is not None else ("UNKNOWN", 0)
    return {"scheduled_hour": req_hour, "scheduled_pm25": pm, "verdict": v, "safe_minutes": m,
            "best_hour": best, "best_pm25": by_h.get(best),
            "aqi_scheduled": pm25_to_aqi(pm) if pm is not None else None}
