"""Public status page (Lambda Function URL). Reads DynamoDB, renders plain HTML."""
import json, os
from core import forecast, plan, pm25_to_aqi

COL = {"GO": "#1a7f37", "SHORTEN": "#b7791f", "INDOORS": "#c53030", "UNKNOWN": "#718096"}


def card(sid, rows):
    fc = forecast([(int(r["hour"]), float(r["pm"])) for r in rows], horizon=24)
    p = plan(fc, int(os.environ.get("PE_HOUR_" + sid, 9)))
    now = float(rows[-1]["pm"])
    bars = "".join(f'<i title="{h}:00 {v:.0f}" style="height:{min(v, 400) / 4}px"></i>' for h, v in fc)
    c = COL[p["verdict"]]
    return (f'<section><h2>{sid}</h2><b style="color:{c}">{p["verdict"]}</b>'
            f'<p>PM2.5 now <b>{now:.0f}</b> ug/m3, AQI <b>{pm25_to_aqi(now)}</b></p>'
            f'<p>Safe PE minutes at scheduled time: <b>{p["safe_minutes"]}</b>. '
            f'Cleanest forecast hour: <b>{p["best_hour"]}:00</b></p><div class="bars">{bars}</div>'
            f'<small>Next 24 h forecast (PM2.5). Bars cap at 400.</small></section>')


def page(cards):
    return ("<!doctype html><meta name=viewport content='width=device-width,initial-scale=1'>"
            "<title>SaansAlert</title><style>body{font:16px system-ui;max-width:640px;margin:2rem auto;padding:0 1rem}"
            "section{border:1px solid #ddd;border-radius:10px;padding:1rem;margin:1rem 0}.bars{display:flex;align-items:flex-end;"
            "gap:2px;height:100px}.bars i{flex:1;background:#4a5568;min-height:2px}small{color:#666}</style>"
            "<h1>SaansAlert</h1><p>Can kids play outside today? Updated hourly from live air-quality data.</p>"
            + "".join(cards))


def lambda_handler(event, ctx):
    import boto3
    from boto3.dynamodb.conditions import Key
    table = boto3.resource("dynamodb").Table(os.environ["TABLE"])
    cards = []
    for s in json.loads(os.environ["SCHOOLS"]):
        os.environ["PE_HOUR_" + s["id"]] = str(s["pe_hour"])
        rows = table.query(KeyConditionExpression=Key("school").eq(s["id"]) & Key("ts").gt(0),
                           ScanIndexForward=False, Limit=48)["Items"][::-1]
        cards.append(card(s["id"], rows) if rows else f"<section><h2>{s['id']}</h2>Waiting for first reading.</section>")
    return {"statusCode": 200, "headers": {"Content-Type": "text/html; charset=utf-8"}, "body": page(cards)}
