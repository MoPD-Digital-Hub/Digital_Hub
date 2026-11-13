"""Figures worked out in code from the fetched data, for the writer to quote.

The writer may not do arithmetic: verify.py checks every number it writes against
the facts. So the change since the previous period, the peak, the low, the average,
totals and shares are calculated here and attached to each result as "stats".

Amounts carry no sign; the direction is given beside them ({"direction": "down",
"by": 1.2}), so the text can say "fell by 1.2" and the number still matches. A
calculated figure is never more precise than the data it comes from.
"""

import math
import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

MAX_DECIMALS = 2
# Per-series stats are given for at most this many series (Total, or male and female);
# a longer breakdown (11 regions) gets the comparison across its series instead.
MAX_DETAILED_SERIES = 3
YEAR = re.compile(r"(?<!\d)(\d{4})(?!\d)")
# One period to the next, a real series does not move by this many times: the values
# are on two scales (millions then billions), and nothing calculated from them is true.
MAX_JUMP = 20
MAX_MISSING_YEARS = 8
# How far back a series is also compared, by how often it is reported.
EARLIER = {"annual": ((5, "5 years earlier"), (10, "10 years earlier")),
           "quarterly": ((1, "same quarter a year earlier"),),
           "monthly": ((1, "same month a year earlier"),)}


def _number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _decimals(values):
    """The decimal places the data uses, at most MAX_DECIMALS."""
    places = 0
    for value in values:
        try:
            exponent = Decimal(str(value)).normalize().as_tuple().exponent
        except InvalidOperation:
            continue
        if isinstance(exponent, int) and exponent < 0:
            places = max(places, -exponent)
    return min(places, MAX_DECIMALS)


def _tidy(number, places):
    """Rounded half up, as a reader would (20.95 -> 21.0), free of float noise (20.949999...)."""
    exact = Decimal(str(round(number, places + 6))).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
    return int(exact) if exact == exact.to_integral_value() else float(exact)


def is_rate(unit):
    """A percentage: its change is in percentage points, not "percent of a percent"."""
    unit = str(unit or "").lower()
    return "%" in unit or "percent" in unit or "per cent" in unit


def change(old, new, places=MAX_DECIMALS, unit=None):
    """How a value moved from `old` to `new`: direction and amount.

    A rate or a score moves by an amount in `unit` ("percentage points", "points");
    a quantity (no unit given) also gets its percent change.
    """
    amount = _tidy(new - old, places)
    moved = {"direction": "up" if amount > 0 else "down" if amount < 0 else "unchanged", "by": abs(amount)}
    if unit:
        moved["unit"] = unit
    elif old > 0:
        # A relative change only means something from a positive base.
        moved["percent"] = _tidy(abs((new - old) / old * 100), 1)
    return moved


def same_scale(values):
    """False when consecutive values differ by more than MAX_JUMP times (mixed units in the source)."""
    return not any(a > 0 and b > 0 and max(a, b) / min(a, b) > MAX_JUMP for a, b in zip(values, values[1:]))


def _earlier_period(period, years):
    """ "2018" -> "2013"; "Hidar 2018" -> "Hidar 2017"; "2018 Q3" -> "2017 Q3"."""
    found = YEAR.search(period)
    return None if not found else period[:found.start()] + str(int(found.group(1)) - years) + period[found.end():]


def _run(values):
    """How many periods in a row the series has moved the same way, up to the latest."""
    steps = [b - a for a, b in zip(values, values[1:])]
    if not steps or steps[-1] == 0:
        return None
    rising, count = steps[-1] > 0, 0
    for step in reversed(steps):
        if step == 0 or (step > 0) != rising:
            break
        count += 1
    return {"direction": "up" if rising else "down", "periods": count} if count >= 2 else None


def series(points, unit=None, frequency="annual", requested=None):
    """Stats of one series: points are [{"period", "value"}], oldest first.

    `requested` is the period a question asked about, compared with the one before it.
    None when there are fewer than two values to compare.
    """
    known = [(str(p.get("period")), _number(p.get("value"))) for p in points or []]
    known = [(period, value) for period, value in known if value is not None]
    if len(known) < 2:
        return None
    values = [value for _, value in known]
    if not same_scale(values):
        return None
    places, rate = _decimals(values), is_rate(unit)

    def point(item):
        return {"period": item[0], "value": _tidy(item[1], 6)}

    def moved(old, new):
        return change(old[1], new[1], places, "percentage points" if rate else None)

    latest, previous, first = known[-1], known[-2], known[0]
    # On a tie the most recent period is named.
    newest_first = known[::-1]
    stats = {
        "periods": len(known),
        "latest": point(latest),
        "previous": point(previous),
        "change_from_previous": moved(previous, latest),
        "highest": point(max(newest_first, key=lambda item: item[1])),
        "lowest": point(min(newest_first, key=lambda item: item[1])),
        "average": _tidy(sum(values) / len(values), max(places, 1)),
    }
    if len(known) > 2:
        stats["first"] = point(first)
        stats["change_since_first"] = moved(first, latest)
    if frequency == "annual" and all(period.isdigit() for period, _ in known):
        # 10 values over 12 years are not "a 10-year average": name the years without data.
        have = {int(period) for period, _ in known}
        missing = [str(year) for year in range(min(have), max(have) + 1) if year not in have]
        if missing:
            stats["years_without_data"] = missing[:MAX_MISSING_YEARS]
    run = _run(values)
    if run:
        stats["moving_the_same_way_for"] = run

    by_period = dict(known)
    compared = []
    for years, label in EARLIER.get(frequency, ()):
        period = _earlier_period(latest[0], years)
        if period in by_period and period != previous[0]:
            compared.append({"earlier": label, "period": period, "value": _tidy(by_period[period], 6),
                             "change": moved((period, by_period[period]), latest)})
    if compared:
        stats["compared_with"] = compared

    if frequency == "annual" and not rate and first[1] > 0 and latest[1] > 0 and first[0].isdigit() and latest[0].isdigit():
        span = int(latest[0]) - int(first[0])
        if span >= 2:
            yearly = _tidy(((latest[1] / first[1]) ** (1 / span) - 1) * 100, 1)
            # Named for its direction, so the sentence reads "grew by 13.5 percent a year on average".
            if yearly:
                stats["average_yearly_growth_percent" if yearly > 0 else "average_yearly_decline_percent"] = abs(yearly)

    if requested is not None and str(requested) in by_period:
        index = [period for period, _ in known].index(str(requested))
        asked = {**point(known[index])}
        if index > 0:
            asked["previous"] = point(known[index - 1])
            asked["change_from_previous"] = moved(known[index - 1], known[index])
        stats["requested"] = asked
    return stats


def across(items, unit=None):
    """Stats across named values ([{"name", "value"}]): a ranking, a breakdown, a scorecard's parts."""
    known = [(item.get("name"), _number(item.get("value"))) for item in items or []]
    known = [(name, value) for name, value in known if value is not None]
    if len(known) < 2:
        return None
    values = [value for _, value in known]
    places = _decimals(values)
    highest, lowest = max(known, key=lambda item: item[1]), min(known, key=lambda item: item[1])
    gap = {"gap_between_highest_and_lowest": _tidy(highest[1] - lowest[1], places)}
    if is_rate(unit):
        gap["gap_unit"] = "percentage points"
    return {
        "count": len(known),
        "highest": {"name": highest[0], "value": _tidy(highest[1], 6)},
        "lowest": {"name": lowest[0], "value": _tidy(lowest[1], 6)},
        "average": _tidy(sum(values) / len(values), max(places, 1)),
        **gap,
    }


def shares(counts):
    """A total and each part's share of it, from {"name": count} (KPIs by performance band)."""
    known = {name: _number(count) for name, count in (counts or {}).items()}
    known = {name: count for name, count in known.items() if count is not None and count >= 0}
    total = sum(known.values())
    if len(known) < 2 or total <= 0:
        return None
    return {"total": _tidy(total, 0),
            "share_percent": {name: _tidy(count / total * 100, 1) for name, count in known.items()}}


def many_series(all_series, unit=None, requested=None, breakdown=False):
    """Stats for an SDG indicator's series ([{"name", "points": [{"year", "value"}]}]).

    A few series (Total; male and female) each get their own stats. A breakdown
    (regions, sex) is also compared across its series, at the latest year most of
    them report; series that are different measures are not compared.
    """
    stats = {}
    if len(all_series) <= MAX_DETAILED_SERIES:
        for one in all_series:
            points = [{"period": str(p.get("year")), "value": p.get("value")} for p in one.get("points") or []]
            found = series(points, unit, "annual", requested)
            if found:
                stats.setdefault("by_series", {})[str(one.get("name"))] = found
    if breakdown and len(all_series) > 1:
        parts = [one for one in all_series if one.get("name") and str(one["name"]).lower() != "total"]
        by_year = {}
        for one in parts:
            for p in one.get("points") or []:
                if _number(p.get("value")) is not None:
                    by_year.setdefault(p.get("year"), []).append({"name": one["name"], "value": p["value"]})
        # The latest year most of the series report: one region with a newer survey is not a comparison.
        shared = [year for year, items in by_year.items() if len(items) >= max(2, (len(parts) + 1) // 2)]
        if shared:
            year = max(shared)
            found = across(by_year[year], unit)
            if found:
                stats["across_series"] = {"year": year, **found}
    return stats or None
