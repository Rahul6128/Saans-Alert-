"""Hourly Lambda: stations -> per-school estimate -> forecast -> plan -> alert only on change."""
import json, os, time, urllib.request
from datetime import datetime, timezone, timedelta
import boto3
from boto3.dynamodb.conditions import Key
from core import idw, forecast, plan, pm25_to_aqi

IST = timezone(timedelta(hours=5, minutes=30))
table = boto3.resource("dynamodb").Table(os.environ["TABLE"])
sns = boto3.client("sns")


def fetch_stations():
    """Latest PM2.5 per station from OpenAQ v3. NOTE: written from the API docs, not yet
    tested against the live service -- verify field names with a real key first."""
    req = urllib.request.Request(
        "https://api.openaq.org/v3/parameters/2/latest?limit=1000&" + os.environ["BBOX_QS"],
        headers={"X-API-Key": os.environ["OPENAQ_KEY"]})
    rows = json.load(urllib.request.urlopen(req, timeout=10))["results"]
    return [(r["coordinates"]["latitude"], r["coordinates"]["longitude"], r["value"])
            for r in rows if 0 <= r["value"] < 1000]  # drop sensor glitches


def message(sid, pm, p):
    head = {"GO": "Outdoor PE is fine", "SHORTEN": "Shorten outdoor PE to %d min" % p["safe_minutes"],
            "INDOORS": "Keep PE indoors"}.get(p["verdict"], "No forecast yet")
    return (f"{sid}: {head} at {p['scheduled_hour']}:00.\nPM2.5 now {pm:.0f} ug/m3 (AQI {pm25_to_aqi(pm)}). "
            f"Cleanest slot in the next 24 h: {p['best_hour']}:00 (about {p['best_pm25']:.0f} ug/m3).")


def lambda_handler(event, ctx):
    stations = fetch_stations()
    now = datetime.now(IST)
    for s in json.loads(os.environ["SCHOOLS"]):  # [{id,lat,lon,pe_hour,pe_minutes}]
        pm = idw(stations, s["lat"], s["lon"])
        table.put_item(Item={"school": s["id"], "ts": int(time.time()), "hour": now.hour, "pm": str(round(pm, 1))})
        rows = table.query(KeyConditionExpression=Key("school").eq(s["id"]) & Key("ts").gt(0), ScanIndexForward=False, Limit=48)["Items"][::-1]
        fc = forecast([(int(r["hour"]), float(r["pm"])) for r in rows])
        p = plan(fc, s["pe_hour"], s.get("pe_minutes", 45))
        prev = table.get_item(Key={"school": s["id"], "ts": 0}).get("Item", {}).get("verdict")
        if p["verdict"] != prev:  # dedupe: alert on change, never repeat
            sns.publish(TopicArn=os.environ["TOPIC"], Subject=f"{s['id']}: {p['verdict']}", Message=message(s["id"], pm, p))
            table.put_item(Item={"school": s["id"], "ts": 0, "verdict": p["verdict"]})
    return {"ok": True}
