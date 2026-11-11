"""Turn an SDG indicator's disaggregated data into a few readable series.

An indicator's data is a list of series, each a set of disaggregations
(Region=Afar, Sex=FEMALE, …) with values by Gregorian year. The headline view
keeps the national totals (Region=NATIONAL, Sex=BOTH SEX, …) and lets the other
dimensions (Poverty Type, Type of Malnutrition, …) show as separate series. A
breakdown asks for one dimension in full instead ("by region").
"""

# Enough for every region and city administration.
MAX_SERIES = 14

# Values that mean "all of this dimension".
TOTALS = {"national", "both sex", "both sexes", "total", "all", "all age", "all ages", "all area", "all areas"}

BREAKDOWNS = {
    "region": "Region",
    "sex": "Sex",
    "age": "Age",
    "location": "Geographical Location",
    "education": "Educational Level",
    "wealth": "Wealth Quintile",
}

UNITS = {"percent": "%", "percentage": "%"}


def is_total(value):
    return str(value or "").strip().lower() in TOTALS


def unit_label(unit):
    unit = str(unit or "").strip()
    return UNITS.get(unit.lower(), unit)


# Region abbreviations stay as written.
ACRONYMS = {"SNNP", "SNNPR", "SWEP"}


def _label(value):
    """"URBAN" -> "Urban"; abbreviations and names already in mixed case are kept."""
    value = str(value or "").strip()
    return value.title() if value.isupper() and value not in ACRONYMS else value


def _number(value):
    try:
        number = float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    return int(number) if number.is_integer() else number


def _points(raw):
    points = []
    for entry in (raw.get("data") or {}).values():
        value, year = _number(entry.get("value")), entry.get("year")
        if value is not None and str(year).isdigit():
            points.append({"year": int(year), "value": value, "unit": unit_label(entry.get("unit"))})
    return sorted(points, key=lambda p: p["year"])


DIMENSION_LABELS = {"Geographical Location": "Area", "Educational Level": "Level"}


def select(series, breakdown=None):
    """Series to show, as [{"name", "unit", "points": [{"year", "value"}]}], plus notes.

    Each series carries "dimension": what its name is a value of ("Region"), or
    "Series" when names combine several dimensions.
    """
    rows = [{d.get("type"): d.get("value") for d in s.get("disaggregations") or []} for s in series or []]
    dims = list(dict.fromkeys(dim for row in rows for dim in row))
    with_total = {dim for dim in dims if any(is_total(row.get(dim)) for row in rows)}
    wanted = BREAKDOWNS.get(breakdown or "")
    notes = []
    if wanted and wanted not in dims:
        notes.append(f"This indicator has no breakdown by {breakdown}; the totals are shown.")
        wanted = None

    # With a breakdown, other dimensions that have no total (Poverty Type) keep
    # their first value, so the breakdown is not crowded out.
    fixed = {}
    if wanted:
        for dim in dims:
            values = list(dict.fromkeys(row.get(dim) for row in rows if row.get(dim)))
            if dim != wanted and dim not in with_total and len(values) > 1:
                fixed[dim] = values[0]
                notes.append(f"Showing {dim}: {_label(values[0])}.")

    kept = [
        (raw, row) for raw, row in zip(series or [], rows)
        if all(dim == wanted or dim not in with_total or is_total(row.get(dim)) for dim in dims)
        and all(row.get(dim) == value for dim, value in fixed.items())
    ]
    if wanted:
        # The breakdown's own total (NATIONAL, BOTH SEX) goes last.
        kept.sort(key=lambda pair: is_total(pair[1].get(wanted)))
    varying = [dim for dim in dims if len({row.get(dim) for _, row in kept}) > 1]

    result = []
    for raw, row in kept:
        points = _points(raw)
        if not points:
            continue
        name = " · ".join(_label(row[dim]) for dim in varying if row.get(dim)) or "Total"
        dimension = DIMENSION_LABELS.get(varying[0], varying[0]) if len(varying) == 1 else "Series"
        result.append({"name": name, "dimension": dimension, "unit": points[-1]["unit"],
                       "points": [{"year": p["year"], "value": p["value"]} for p in points]})
    if len(result) > MAX_SERIES:
        notes.append(f"Showing {MAX_SERIES} of {len(result)} series.")
        result = result[:MAX_SERIES]
    return result, notes


def headline(series):
    """The single series that best stands for the indicator nationally, or None."""
    shown, _ = select(series)
    if not shown:
        return None
    return next((s for s in shown if s["name"] == "Total"), shown[0])
