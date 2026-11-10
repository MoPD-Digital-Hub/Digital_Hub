"""Ethiopian-calendar periods for DPMES and time-series lookups."""

from integrations.dpmes import client as dpmes_client

# Ethiopian months as the time-series API names them, with English spellings.
ETHIOPIAN_MONTHS = {
    "መስከረም": "Meskerem", "ጥቅምት": "Tikimt", "ህዳር": "Hidar", "ኅዳር": "Hidar",
    "ታህሳስ": "Tahsas", "ታኅሣሥ": "Tahsas", "ጥር": "Tir", "የካቲት": "Yekatit",
    "መጋቢት": "Megabit", "ሚያዝያ": "Miyazya", "ግንቦት": "Ginbot", "ሰኔ": "Sene",
    "ሐምሌ": "Hamle", "ሃምሌ": "Hamle", "ነሐሴ": "Nehase", "ነሃሴ": "Nehase",
    "ጳጉሜ": "Pagume", "ጳጉሜን": "Pagume",
}


def current_year():
    return dpmes_client.current_ethiopian_year()


def to_ethiopian_year(year):
    """Ethiopian year for a year from a question, and whether it was converted.

    DPMES and the time-series data use the Ethiopian calendar. A year beyond the
    current Ethiopian one can only be Gregorian, so convert it: Gregorian Y is
    mostly Ethiopian Y-8 (the Ethiopian year starts in September).
    """
    if not year:
        return None, False
    year = int(year)
    current = current_year()
    if year > current:
        return year - 8, True
    return year, False


def dpmes_period(year=None, quarter=None):
    """DPMES period plus notes for the answer. Defaults to the last completed
    year, like the dashboard, because the current year is mostly unreported."""
    notes = []
    ethiopian, converted = to_ethiopian_year(year)
    if converted:
        notes.append(f"{year} was read as a Gregorian year and looked up as {ethiopian} EC.")
    if ethiopian is None:
        ethiopian = current_year() - 1
        notes.append(f"No year was given, so the last completed year, {ethiopian} EC, is used.")
    period = {"year": ethiopian}
    if quarter and int(quarter) in (1, 2, 3, 4):
        period["quarter"] = int(quarter)
    return period, notes


def period_label(period):
    quarter = period.get("quarter")
    return f"{period['year']} EC" + (f" Q{quarter}" if quarter else " (annual)")


def month_label(month):
    return ETHIOPIAN_MONTHS.get(str(month).strip(), str(month).strip())
