# Preferences and the personal dashboard

Each user chooses what they follow and how their home is laid out. The same endpoints serve the website and
the mobile app. All of them need a signed-in user and return the standard response shape (`docs/api.md`).

Code: `core/preferences/` (`models.py`, `sources.py` reads the other services, `dashboard.py` builds the
answers, `api/` holds the endpoints).

## What is stored

- `UserPreference`, one per user: section order and visibility, the comparison period (`quarter` or `year`),
  movers settings, language. A user with no row gets the defaults.
- `Follow`, one row per followed item: `kind` (`organization`, `policy_area`, `kpi`, `indicator`), the item's id
  in its own service, and for a KPI the organization whose results to show.

Scores are not stored. DPMES keeps every period, and scores only change when a period is reported, so they are
read on demand and cached for six hours (indicator values for one hour).

## Ids

`id` is always the item's id in its own service: DPMES for organizations, policy areas and KPIs, the
time-series service for indicators. `follow_id` is the user's follow record, used to unfollow and reorder.

## Endpoints

| Method and path | Does |
|---|---|
| `GET /api/preferences/` | The user's settings; `sections` is always the full ordered list |
| `PUT /api/preferences/` | Change settings. Send only the fields to change |
| `GET /api/preferences/follows/?kind=` | What the user follows, in their order |
| `POST /api/preferences/follows/` | Follow: `{"kind": "organization", "id": "312"}`. A KPI may add `organization_id` |
| `DELETE /api/preferences/follows/<follow_id>/` | Unfollow |
| `PUT /api/preferences/follows/order/` | Reorder: `{"kind": "organization", "follow_ids": [4, 2]}` |
| `GET /api/preferences/options/?kind=&search=&organization=` | Items that can be followed, each with `followed` |
| `GET /api/preferences/dashboard/` | The whole personal home in one call |
| `GET /api/preferences/movers/?kind=&period=&direction=&scope=&limit=&organization=` | Biggest rises and falls |

Following checks the item in its own service and copies its name; an unknown id answers 404 `ITEM_NOT_FOUND`.
A user may follow up to 30 items of one kind (`FOLLOW_LIMIT_REACHED`). Indicators have no full list: `options`
returns them only for a `search` of two or more characters.

## Periods

Every score is shown with its change since the previous period.

- `quarter`: the newest quarter in which any organization has a score, against the quarter before it.
- `year`: the last complete Ethiopian year against the year before.

An item is compared only when it has data in both periods. An organization or policy area that scores exactly
0 counts as not reported (DPMES gives 0 when nothing is reported). A KPI counts as reported when it has a
result, even a result of 0.

## The dashboard response

```json
{
  "sections": [{"key": "my_organizations", "visible": true}],
  "has_follows": true,
  "period": {"type": "quarter", "current": {"year": 2019, "quarter": 1, "label": "2019 Q1"},
             "previous": {"year": 2018, "quarter": 4, "label": "2018 Q4"}},
  "organizations": [{"id": "312", "name": "…", "score": 86.69, "previous_score": 69.66, "change": 17.03,
                     "rank": 17, "ranked_total": 29, "band": {"name": "On Track", "color": "#6FC327"},
                     "follow_id": 3, "is_default": false}],
  "policy_areas": [],
  "kpis": [{"id": "6402", "organization_id": "312", "target": 91.0, "performance": 91.3, "score": 100.0,
            "change": 5.0, "direction": "increasing", "history": [{"period": "2018 Q1", "score": 100.0}]}],
  "indicators": [{"id": "7104", "latest": {"period": "2018", "value": 7.7}, "change_percent": -16.3,
                  "direction": "increasing", "series": []}],
  "movers": {"kpis": {"rising": [], "declining": []}, "categories": {"rising": [], "declining": []}},
  "needs_attention": [{"kind": "kpi", "id": "…", "reason": "low_score"}],
  "errors": {}
}
```

- With nothing followed, `organizations` holds the user's own organization (`is_default: true`).
- `direction` says whether a higher value is better (`increasing`) or a lower one (`decreasing`).
- `needs_attention` lists followed items in the two lowest score bands (`low_score`) or with nothing reported
  (`no_data`).
- If a service cannot be read, its sections are named in `errors` and the rest is still returned.
- Hidden `movers`, `needs_attention` and `pinned_indicators` sections are not built.

## Movers

`kind` is `kpi` (default), `category`, `organization` or `policy_area`. KPIs and categories are taken from the
organizations the user follows (their own if none, at most five), or from `organization`. A category's score
is the average of its KPIs that have data in both periods. `scope=following` limits organizations, policy
areas and KPIs to the ones followed. The other parameters default to the user's saved settings.
