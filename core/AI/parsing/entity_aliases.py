import re

ORG_HINT_TERMS = {
    "ministry",
    "minister",
    "agency",
    "bureau",
    "commission",
    "authority",
    "office",
    "government body",
    "public body",
    "institution",
    "institutions",
}

POLICY_HINT_TERMS = {
    "policy area",
    "sector",
    "thematic area",
    "policy score",
}

GOAL_HINT_TERMS = {
    "goal",
    "goals",
    "strategic goal",
    "strategic goals",
    "target",
    "targets",
    "national target",
}

TIME_SERIES_HINT_TERMS = {
    "time series",
    "trend",
    "historical",
    "history",
    "over time",
    "annual",
    "quarterly",
    "monthly",
}

ALIAS_STOPWORDS = {
    "of",
    "and",
    "the",
    "for",
    "in",
    "on",
    "to",
    "by",
    "from",
    "with",
}


def normalize_text(value) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def normalize_token(value) -> str:
    return re.sub(r"[^a-z0-9]+", "", normalize_text(value))


def tokenize_question(question: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", normalize_text(question))
        if len(token) > 1 and token not in ALIAS_STOPWORDS
    }


def _name_aliases(name: str) -> set[str]:
    normalized_name = normalize_text(name)
    if not normalized_name:
        return set()

    aliases = {normalized_name, normalize_token(normalized_name)}
    words = [word for word in re.findall(r"[a-z0-9]+", normalized_name) if word not in ALIAS_STOPWORDS]
    if words:
        aliases.update(words)
        aliases.add("".join(word[0] for word in words))

    if len(words) >= 2 and words[0] == "ministry":
        tail = [word for word in words[1:] if word not in {"ministry"}]
        if tail:
            aliases.add(f"mo{''.join(word[0] for word in tail)}")

    return {alias for alias in aliases if alias}


def metadata_entity_aliases(metadata: dict | None) -> set[str]:
    meta = metadata or {}
    return _metadata_aliases_for_keys(
        meta,
        (
            "responsible_ministry_code",
            "responsible_ministry_code_normalized",
            "responsible_ministry_eng",
            "responsible_ministry_eng_normalized",
        ),
    )


def metadata_policy_area_aliases(metadata: dict | None) -> set[str]:
    meta = metadata or {}
    return _metadata_aliases_for_keys(
        meta,
        (
            "policy_area_eng",
            "policy_area_eng_normalized",
            "policy_area_name",
            "policy_area_name_normalized",
            "sector_name",
            "sector_name_normalized",
            "category_name",
            "category_name_normalized",
        ),
    )


def metadata_goal_aliases(metadata: dict | None) -> set[str]:
    meta = metadata or {}
    return _metadata_aliases_for_keys(
        meta,
        (
            "goal_name",
            "goal_name_normalized",
            "goal_eng",
            "goal_eng_normalized",
            "strategic_goal",
            "strategic_goal_normalized",
            "target_name",
            "target_name_normalized",
            "goal_code",
            "goal_code_normalized",
        ),
    )


def metadata_time_series_aliases(metadata: dict | None) -> set[str]:
    meta = metadata or {}
    return _metadata_aliases_for_keys(
        meta,
        (
            "indicator_code",
            "indicator_code_normalized",
            "indicator_eng",
            "indicator_eng_normalized",
            "topic_name",
            "topic_name_normalized",
            "category_name",
            "category_name_normalized",
            "source",
            "source_normalized",
        ),
    )


def metadata_all_aliases(metadata: dict | None) -> set[str]:
    meta = metadata or {}
    return (
        metadata_entity_aliases(meta)
        | metadata_policy_area_aliases(meta)
        | metadata_goal_aliases(meta)
        | metadata_time_series_aliases(meta)
    )


def _metadata_aliases_for_keys(meta: dict, keys) -> set[str]:
    aliases = set()
    for key in keys:
        value = meta.get(key)
        if value:
            aliases.update(_name_aliases(str(value)))
    return aliases


def question_entity_aliases(question: str) -> set[str]:
    text = normalize_text(question)
    aliases = set(tokenize_question(text))

    # Keep short acronym-like tokens as dynamic entity candidates (e.g. moh, csa, epa).
    aliases.update(
        token
        for token in re.findall(r"\b[a-z]{2,8}\b", text)
        if token not in ALIAS_STOPWORDS
    )
    return aliases


def has_institution_reference(question: str, docs=None) -> bool:
    text = normalize_text(question)
    if any(term in text for term in ORG_HINT_TERMS):
        return True

    question_aliases = question_entity_aliases(text)
    for doc in docs or []:
        if metadata_entity_aliases(getattr(doc, "metadata", {}) or {}) & question_aliases:
            return True
    return False


def has_policy_area_reference(question: str, docs=None) -> bool:
    text = normalize_text(question)
    if any(term in text for term in POLICY_HINT_TERMS):
        return True

    question_aliases = question_entity_aliases(text)
    for doc in docs or []:
        if metadata_policy_area_aliases(getattr(doc, "metadata", {}) or {}) & question_aliases:
            return True
    return False


def has_goal_reference(question: str, docs=None) -> bool:
    text = normalize_text(question)
    if any(term in text for term in GOAL_HINT_TERMS):
        return True

    question_aliases = question_entity_aliases(text)
    for doc in docs or []:
        if metadata_goal_aliases(getattr(doc, "metadata", {}) or {}) & question_aliases:
            return True
    return False


def has_time_series_reference(question: str, docs=None) -> bool:
    text = normalize_text(question)
    if any(term in text for term in TIME_SERIES_HINT_TERMS):
        return True

    question_aliases = question_entity_aliases(text)
    for doc in docs or []:
        if metadata_time_series_aliases(getattr(doc, "metadata", {}) or {}) & question_aliases:
            return True
    return False
