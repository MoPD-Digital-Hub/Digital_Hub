import re

DEFAULT_QUARTER = "12month"
VALID_QUARTERS = {"3month", "6month", "9month", "12month"}
VALID_PERFORMANCE_KEYS = {"on_track", "in_progress", "weak_performance", "no_data"}
YEAR_PATTERN = re.compile(r"\b(19|20)\d{2}\b")
