"""The personal dashboard: what a user follows, how it scored, and what moved.

Every score is compared between two periods (see sources.periods). A section
that cannot be read is reported under `errors` and the rest is still returned.
"""

from concurrent.futures import ThreadPoolExecutor
from statistics import fmean

from preferences import sources
from preferences.models import Follow, UserPreference

# KPI movers read two KPI lists per organization, so cap how many are compared.
MOVER_ORGANIZATIONS = 5
# The lowest score bands, e.g. "Requires Intervention" and "Weak Performance".
ATTENTION_BANDS = 2
FETCH_THREADS = 8


def preference_for(user):
    """The user's saved preferences, or unsaved defaults."""
    return UserPreference.objects.filter(user=user).first() or UserPreference(user=user)


def default_organization_id(user):
    ministry = getattr(user, "ministry", None)
    return str(ministry.dpmes2_id) if ministry and ministry.dpmes2_id else None


def followed_ids(follows, kind):
    return [follow.external_id for follow in follows if follow.kind == kind]


def organization_ids(user, follows):
    """Organizations to show: the ones followed, else the user's own."""
    ids = followed_ids(follows, Follow.ORGANIZATION)
    if ids:
        return ids
    default = default_organization_id(user)
    return [default] if default else []


# --- Comparing two periods ---------------------------------------------------


def _comparable(row):
    return row["has_data"] if "has_data" in row else sources.has_score(row)


def compare(current_rows, previous_rows):
    """`current_rows` with previous_score and change (None when either period has no data)."""
    previous = {row["id"]: row for row in previous_rows}
    for row in current_rows:
        before = previous.get(row["id"])
        both = _comparable(row) and before is not None and _comparable(before)
        row["previous_score"] = before["score"] if before is not None and _comparable(before) else None
        row["change"] = round(row["score"] - before["score"], 2) if both else None
    return current_rows


def rank(rows):
    """Add rank (1 = highest score) among the rows that have data."""
    ordered = sorted((row for row in rows if _comparable(row)), key=lambda row: row["score"], reverse=True)
    for position, row in enumerate(ordered, start=1):
        row["rank"] = position
    for row in rows:
        row.setdefault("rank", None)
        row["ranked_total"] = len(ordered)
    return rows


def split(rows, direction, limit):
    """The biggest rises and falls among rows that changed."""
    changed = [row for row in rows if row.get("change")]
    rising = sorted((row for row in changed if row["change"] > 0), key=lambda row: row["change"], reverse=True)
    declining = sorted((row for row in changed if row["change"] < 0), key=lambda row: row["change"])
    return {
        "rising": rising[:limit] if direction != UserPreference.DECLINING else [],
        "declining": declining[:limit] if direction != UserPreference.RISING else [],
    }


def add_bands(rows, bands):
    for row in rows:
        band = sources.band_for(row["score"], bands) if _comparable(row) else None
        row["band"] = {"name": band["name"], "name_am": band["name_am"], "color": band["color"]} if band else None
    return rows


# --- Rows per kind ------------------------------------------------------------


def organization_rows(current, previous):
    return rank(compare(sources.organizations(current), sources.organizations(previous)))


def policy_area_rows(current, previous):
    return rank(compare(sources.policy_areas(current), sources.policy_areas(previous)))


def kpi_rows(organization_id, current, previous, names):
    rows = compare(
        sources.organization_kpis(organization_id, current),
        sources.organization_kpis(organization_id, previous),
    )
    for row in rows:
        row["organization"] = names.get(str(organization_id), "")
    return rows


def category_rows(kpis):
    """KPIs grouped by their category within an organization.

    A category's score is the average over the KPIs that have data in both
    periods, so the two averages are over the same KPIs.
    """
    groups = {}
    for row in kpis:
        if row["change"] is not None and row["category"]:
            groups.setdefault((row["organization_id"], row["category"]), []).append(row)
    rows = []
    for (organization_id, category), members in groups.items():
        score = fmean(row["score"] for row in members)
        before = fmean(row["previous_score"] for row in members)
        rows.append({
            "id": f"{organization_id}:{category}",
            "name": category,
            "organization_id": organization_id,
            "organization": members[0]["organization"],
            "kpi_count": len(members),
            "score": round(score, 2),
            "previous_score": round(before, 2),
            "change": round(score - before, 2),
        })
    return rows


def organization_names(period):
    return {row["id"]: row["name"] for row in sources.organizations(period)}


# --- Movers -------------------------------------------------------------------

MOVER_KINDS = ("kpi", "category", "organization", "policy_area")


def movers(user, follows, *, kind, period, direction, scope, limit, organization=None):
    current, previous = sources.periods(period)
    following = scope == UserPreference.FOLLOWING

    if kind == "organization":
        rows = organization_rows(current, previous)
        if following:
            wanted = set(organization_ids(user, follows))
            rows = [row for row in rows if row["id"] in wanted]
    elif kind == "policy_area":
        rows = policy_area_rows(current, previous)
        if following:
            wanted = set(followed_ids(follows, Follow.POLICY_AREA))
            rows = [row for row in rows if row["id"] in wanted]
    else:
        organizations = [str(organization)] if organization else organization_ids(user, follows)[:MOVER_ORGANIZATIONS]
        names = organization_names(current)
        rows = [row for org in organizations for row in kpi_rows(org, current, previous, names)]
        if kind == "category":
            rows = category_rows(rows)
        elif following:
            wanted = {(f.external_id, f.organization_id) for f in follows if f.kind == Follow.KPI}
            rows = [row for row in rows if (row["id"], row["organization_id"]) in wanted]

    return {"kind": kind, "period": sources.describe_periods(period, current, previous), **split(rows, direction, limit)}


# --- The dashboard ------------------------------------------------------------


def _pinned_kpis(follows, current, previous, names):
    pins = [follow for follow in follows if follow.kind == Follow.KPI]
    if not pins:
        return []
    by_organization = {}
    for organization_id in {pin.organization_id for pin in pins}:
        rows = kpi_rows(organization_id, current, previous, names)
        by_organization[organization_id] = {row["id"]: row for row in rows}

    with ThreadPoolExecutor(max_workers=FETCH_THREADS) as pool:
        details = list(pool.map(lambda pin: _safe(sources.kpi, pin.external_id, pin.organization_id), pins))

    result = []
    for pin, detail in zip(pins, details):
        row = by_organization[pin.organization_id].get(pin.external_id) or {
            # Not reported for this period: show the name the user followed it under.
            "id": pin.external_id, "organization_id": pin.organization_id, "name": pin.name, "name_am": pin.name_am,
            "code": pin.code, "category": "", "unit": "", "direction": "", "target": None, "performance": None,
            "score": None, "color": "", "has_data": False, "previous_score": None, "change": None,
            "organization": names.get(pin.organization_id, ""),
        }
        result.append({**row, "follow_id": pin.id, "history": (detail or {}).get("history", [])})
    return result


def _safe(call, *args):
    """A pinned item's detail, or None when its service cannot be read: one
    failing pin must not empty the section."""
    try:
        return call(*args)
    except sources.SourceError:
        return None


def _pinned_indicators(follows):
    pins = [follow for follow in follows if follow.kind == Follow.INDICATOR]
    if not pins:
        return []
    with ThreadPoolExecutor(max_workers=FETCH_THREADS) as pool:
        details = list(pool.map(lambda pin: _safe(sources.indicator, pin.external_id), pins))

    result = []
    for pin, detail in zip(pins, details):
        series = (detail or {}).get("series") or []
        latest = series[-1] if series else None
        before = series[-2] if len(series) > 1 else None
        change = round(latest["value"] - before["value"], 4) if latest and before else None
        percent = round(change / abs(before["value"]) * 100, 2) if change is not None and before["value"] else None
        result.append({
            "follow_id": pin.id,
            "id": pin.external_id,
            "name": (detail or {}).get("name") or pin.name,
            "name_am": (detail or {}).get("name_am") or pin.name_am,
            "code": (detail or {}).get("code") or pin.code,
            "unit": (detail or {}).get("unit", ""),
            "direction": (detail or {}).get("direction", ""),
            "frequency": (detail or {}).get("frequency", ""),
            "latest": latest,
            "previous": before,
            "change": change,
            "change_percent": percent,
            "series": series,
            "has_data": latest is not None,
        })
    return result


def _needs_attention(groups, bands):
    """Followed items in the lowest score bands, or with nothing reported."""
    low = {band["name"] for band in bands[:ATTENTION_BANDS]}
    items = []
    for kind, rows in groups:
        for row in rows:
            if not _comparable(row):
                reason = "no_data"
            elif row.get("band") and row["band"]["name"] in low:
                reason = "low_score"
            else:
                continue
            items.append({
                "kind": kind, "id": row["id"], "organization_id": row.get("organization_id", ""),
                "name": row["name"], "name_am": row.get("name_am", ""),
                "score": row["score"] if _comparable(row) else None, "band": row.get("band"), "reason": reason,
            })
    return sorted(items, key=lambda item: (item["score"] is not None, item["score"] or 0))


def build(user):
    preference = preference_for(user)
    follows = list(Follow.objects.filter(user=user))
    data = {
        "sections": preference.ordered_sections(),
        "has_follows": bool(follows),
        "period": None,
        "organizations": [], "policy_areas": [], "kpis": [], "indicators": [],
        "movers": None, "needs_attention": [],
        "errors": {},
    }

    def section(key, build_section):
        try:
            data[key] = build_section()
        except sources.SourceError as exc:
            data["errors"][key] = {"code": exc.code, "message": str(exc)}

    if preference.shows("pinned_indicators"):
        section("indicators", lambda: _pinned_indicators(follows))

    try:
        current, previous = sources.periods(preference.period)
        bands = sources.score_bands()
        names = organization_names(current)
    except sources.SourceError as exc:
        # Nothing scored can be shown without the period; indicators above still are.
        error = {"code": exc.code, "message": str(exc)}
        data["errors"].update({key: error for key in ("organizations", "policy_areas", "kpis", "movers")})
        return data
    data["period"] = sources.describe_periods(preference.period, current, previous)

    def my_organizations():
        wanted = organization_ids(user, follows)
        follow_ids = {f.external_id: f.id for f in follows if f.kind == Follow.ORGANIZATION}
        rows = {row["id"]: row for row in add_bands(organization_rows(current, previous), bands)}
        return [
            {**rows[identifier], "follow_id": follow_ids.get(identifier), "is_default": identifier not in follow_ids}
            for identifier in wanted if identifier in rows
        ]

    def my_policy_areas():
        follow_ids = {f.external_id: f.id for f in follows if f.kind == Follow.POLICY_AREA}
        if not follow_ids:
            return []
        rows = {row["id"]: row for row in add_bands(policy_area_rows(current, previous), bands)}
        return [{**rows[identifier], "follow_id": follow_id} for identifier, follow_id in follow_ids.items()
                if identifier in rows]

    section("organizations", my_organizations)
    section("policy_areas", my_policy_areas)
    section("kpis", lambda: add_bands(_pinned_kpis(follows, current, previous, names), bands))

    if preference.shows("movers"):
        def my_movers():
            options = {"period": preference.period, "direction": preference.movers_direction,
                       "limit": preference.movers_limit}
            kpis = movers(user, follows, kind="kpi", scope=preference.movers_scope, **options)
            categories = movers(user, follows, kind="category", scope=UserPreference.ALL, **options)
            return {
                "kpis": {"rising": kpis["rising"], "declining": kpis["declining"]},
                "categories": {"rising": categories["rising"], "declining": categories["declining"]},
            }
        section("movers", my_movers)

    if preference.shows("needs_attention"):
        data["needs_attention"] = _needs_attention(
            [("organization", data["organizations"]), ("policy_area", data["policy_areas"]), ("kpi", data["kpis"])],
            bands,
        )
    return data


# --- Choosing what to follow ---------------------------------------------------


def _matches(row, search):
    text = " ".join(str(row.get(key) or "") for key in ("name", "name_am", "code", "category")).lower()
    return all(word in text for word in search.lower().split())


def options(user, follows, kind, search="", organization=None):
    """Items of `kind` the user can follow, each marked if already followed."""
    year = {"year": sources.current_year() - 1}
    if kind == Follow.ORGANIZATION:
        rows = sources.organizations(year)
    elif kind == Follow.POLICY_AREA:
        rows = sources.policy_areas(year)
    elif kind == Follow.KPI:
        organization = organization or default_organization_id(user)
        rows = sources.organization_kpis(organization, year) if organization else []
    else:
        # The time-series service has no full list; it answers searches only.
        rows = sources.search_indicators(search) if len(search.strip()) >= 2 else []
        search = ""

    followed = {(f.external_id, f.organization_id) for f in follows if f.kind == kind}
    result = []
    for row in rows:
        if search.strip() and not _matches(row, search):
            continue
        organization_id = row.get("organization_id", "")
        result.append({
            "kind": kind, "id": row["id"], "organization_id": organization_id,
            "name": row["name"], "name_am": row.get("name_am", ""), "code": row.get("code", ""),
            "icon": row.get("icon", ""), "category": row.get("category", ""),
            "followed": (row["id"], organization_id) in followed,
        })
    return result


def resolve(user, kind, external_id, organization_id=""):
    """The item's names from its own service, or None when it does not exist."""
    external_id = str(external_id)
    if kind in (Follow.ORGANIZATION, Follow.POLICY_AREA):
        year = {"year": sources.current_year() - 1}
        rows = sources.organizations(year) if kind == Follow.ORGANIZATION else sources.policy_areas(year)
        row = next((row for row in rows if row["id"] == external_id), None)
        return {**row, "organization_id": ""} if row else None
    if kind == Follow.KPI:
        organization_id = str(organization_id or default_organization_id(user) or "")
        if not organization_id:
            return None
        return sources.kpi(external_id, organization_id)
    row = sources.indicator(external_id)
    return {**row, "organization_id": ""} if row else None
