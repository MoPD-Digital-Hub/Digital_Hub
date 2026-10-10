# DPMES Overview API — Flutter Integration Guide

The two overview endpoints that feed the mobile home screen: national performance, headline counts, the score distribution, and the full scored list of public bodies or policy areas.

## 1. Why this changed

These endpoints used to proxy DPMES's `/api/digital-hub/dashboard/ministries/` and `/api/digital-hub/dashboard/policy-area/`. DPMES removed that API (it now returns 404) in favour of the indicator-framework API at <https://dpmes.mopd.gov.et/api/docs/>. Nobody kept a record of the old response, so **this is a new response shape** and the app's parser needs updating.

The list objects inside `items` are unchanged: they are exactly what `/api/mobile/ministries/` and `/api/mobile/policy-areas/` return, so the models the app already uses for those lists can parse them.

## 2. Endpoints

| Method | Endpoint | `items` contains |
|---|---|---|
| GET | `/api/mobile/overview-ministries/` | Public bodies (same objects as `/api/mobile/ministries/`) |
| GET | `/api/mobile/overview-policy-area/` | Policy areas (same objects as `/api/mobile/policy-areas/`) |

Both use the existing JWT auth: `Authorization: Bearer <access_token>`.

### Query parameters

All optional. Years, quarters and months are **Ethiopian calendar**.

| Param | Example | Notes |
|---|---|---|
| `year` | `2018` | Defaults to the **last completed** Ethiopian year, the same period `/api/mobile/default-time/` returns. The current year is mostly unreported for much of its length. |
| `quarter` | `6month` or `2` | Either the existing `3month`/`6month`/`9month`/`12month` labels or `1`–`4`. Omit for the annual score. |
| `month` | `3` | `1`–`12`, for a monthly score. |
| `plan` | `1` | Plan id. Defaults to the active national plan. |

## 3. Response

Standard envelope, identical for both endpoints:

```json
{
  "result": "SUCCESS",
  "message": "",
  "data": {
    // GET /api/mobile/overview-policy-area/?year=2018&quarter=6month (real response, items elided)
    "period": { "year": 2018, "quarter": 2, "month": null, "plan": null },
    "plan": {
      "id": 1, "code": "PLN-009",
      "name": "10 Year National Development Plan",
      "name_eth": "የአሥር ዓመት ብሔራዊ የልማት ዕቅድ",
      "start_year": "2026-09-11", "end_year": "2029-09-05"
    },
    "national": {
      "id": 1, "code": "FDRE",
      "name": "Federal Democratic Republic of Ethiopia",
      "name_eth": "የኢትዮጵያ ፌዴራላዊ ዲሞክራሲያዊ ሪፐብሊክ",
      "icon": "https://dpmes.mopd.gov.et/media/org_struct/icon/Flag_of_Ethiopia.svg.png",
      "avg_score": 90.31, "scorecard_color": "#6FC327"
    },
    "counts": {
      "organizations": 35, "strategic_goals": 142,
      "key_result_areas": 0, "key_performance_indicators": 3179
    },
    "score_ranges": [
      { "name": "No Data", "name_eth": "No Data", "color": "#4a5568", "start": -10.0, "end": -1.0, "count": 0 },
      { "name": "Requires Intervention", "name_eth": "Requires Intervention", "color": "#FF0000", "start": 0.0, "end": 49.99, "count": 1 },
      { "name": "Weak Performance", "name_eth": "Weak Performance", "color": "#FF7259", "start": 50.0, "end": 64.99, "count": 0 },
      { "name": "In Progress", "name_eth": "In Progress", "color": "#FFBF00", "start": 65.0, "end": 84.99, "count": 4 },
      { "name": "On Track", "name_eth": "On Track", "color": "#6FC327", "start": 85.0, "end": 94.99, "count": 14 },
      { "name": "Achieved", "name_eth": "Achieved", "color": "#046726", "start": 95.0, "end": 100.0, "count": 4 }
    ],
    "summary": {
      "total": 23, "scored": 23, "average": 86.4,
      "highest": { "id": 63, "name": "CULTURE, SPORT, AND CREATIVE ARTS", "code": "PA-017", "avg_score": 99.93, "scorecard_color": "#046726" },
      "lowest":  { "id": 65, "name": "EFFECTIVE GOVERNMENT ADMINISTRATION AND PUBLIC SERVICES", "code": "PA-019", "avg_score": 0.0, "scorecard_color": "#FF0000" }
    },
    "items": [ /* same objects as the list endpoint */ ]
  }
}
```

### Field notes

- **`period`** is the period actually scored, after defaults are applied. Every value is an integer or `null`. `quarter` is always `1`–`4` here, even if you sent `6month`.
- **`national`** is the organization the server's DPMES API key belongs to — FDRE for the national key — with its overall score for the period.
- **`counts`** come straight from DPMES and describe the active plan, not the selected period. `key_result_areas` currently reports `0` from DPMES even though KRAs exist; treat it as unreliable until DPMES fixes it.
- **`score_ranges`** are DPMES's bands, in DPMES's order, each with the number of `items` falling in it. The counts always add up to `summary.total`. Use the band `color`s rather than hard-coding them; DPMES can change them.
- **`summary.highest` / `lowest`** are `null` when nothing has a score.
- **`items`**: for public bodies, the score is in `ministry_score_card`; for policy areas, in `policy_area_score_card`. Both carry `avg_score` and `scorecard_color`. `count_indicator` on public bodies is always `null`, because DPMES no longer provides it — hide the label rather than showing 0.

## 4. Errors

| Status | When | Body |
|---|---|---|
| 401 | Missing or expired JWT | DRF's standard `detail` body |
| 502 | DPMES unreachable, rejected the API key, or returned an error | `{ "result": "FAILURE", "message": "<reason>", "data": null }` |

A 502 whose message mentions `DPMES2_API_KEY` means the server is misconfigured, not the app.
