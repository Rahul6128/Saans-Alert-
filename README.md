# SaansAlert

Hyperlocal air-quality safety planner for schools. Instead of a bare AQI number, it tells a school
**whether outdoor PE is safe, for how many minutes, and which hour today is cleanest.**

## What makes it different from an AQI app
| Step | What it does |
|---|---|
| Spatial estimate | Inverse-distance weighting turns sparse station data into PM2.5 at each school's coordinates |
| Forecast | Latest reading fades into a daily pattern learned from stored history (next 12 h) |
| Dose planning | Safe minutes per activity (rest / light / heavy) from an inhaled-dose budget |
| Verdict | `GO`, `SHORTEN` (with minutes) or `INDOORS`, plus the cleanest alternative hour |
| Alerting | SNS message only when a school's verdict changes |

## Project layout
```
core.py            pure logic (IDW, forecast, dose, plan)
handler.py         Lambda entry point (fetch, store, alert)
template.yaml      AWS SAM template (Lambda, DynamoDB, SNS, hourly schedule)
tests/test_core.py unit tests
docs/architecture.md  diagram and design notes
```

## Run the tests (no AWS needed)
```
python tests/test_core.py
```

## Deploy
1. Get a free OpenAQ API key.
2. Install AWS SAM CLI and configure AWS credentials.
3. Deploy:
```
sam build
sam deploy --guided
```
Parameters: `OpenAQKey`, `BboxQs` (default covers Delhi NCR), and `Schools`, e.g.
```
[{"id":"school-1","lat":28.7501,"lon":77.1177,"pe_hour":9,"pe_minutes":45}]
```
4. Subscribe your email to the SNS topic from the AWS console.

## Assumptions to be honest about
- Child breathing rates in `RATE` are approximate; replace with a cited source.
- The reference budget (45 min heavy activity at 37.5 ug/m3, a WHO interim target) and the GO/SHORTEN/INDOORS cut-offs are tunable heuristics, not medical standards.
- `fetch_stations` was written from the OpenAQ docs and still needs a test with a live key.

## Roadmap
Status web page, outage-day simulator for demos, Hindi/English message templates, optional LLM phrasing of alerts.
