"""The entity catalog: what questions can be about, and how names resolve to it.

About fifteen hundred rows (indicators, organizations, policy areas, goals, SDG
goals and indicators), so the
vectors live in memory and similarity is one matrix product; no vector database
is needed at this size.
"""

import difflib
import hashlib
import logging
import math
import re
import threading
import time
from dataclasses import dataclass, field

import numpy as np
from asgiref.sync import sync_to_async
from django.db import transaction

from ai.engine import llm
from ai.engine.sources import fetch_dpmes, fetch_sdg, lead_sentence
from ai.models import CatalogEntity
from integrations.sdg import client as sdg_client
from integrations.time_series import client as time_series_client

LOGGER = logging.getLogger(__name__)
EMBED_BATCH = 64
INDEX_TTL_SECONDS = 300


# Words that say how something is measured or asked about, not what it is.
STOPWORDS = {
    "a", "an", "and", "the", "of", "in", "on", "for", "to", "by", "with", "what", "is", "was", "were", "are",
    "how", "much", "many", "did", "does", "do", "rate", "ratio", "level", "value", "values", "total", "number",
    "amount", "percent", "percentage", "ethiopia", "ethiopian", "s", "its", "this", "that", "current",
}


def words(value):
    return [w for w in normalise_text(value).split() if w not in STOPWORDS]


def normalise_text(value):
    value = str(value or "").lower()
    value = re.sub(r"[^\w\s]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


# --- Sync ------------------------------------------------------------------


def _clean(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _second(name, other):
    other = _clean(other)
    return other if other and other != name else ""


def _search_text(kind_label, name, name_am, context, extra=""):
    """What gets embedded. Name first: it is what questions ask about."""
    lines = [name, f"Ethiopia {kind_label}: {name}" + (f" ({name_am})" if name_am else "") + "."]
    if context:
        lines.append(context + ".")
    if extra:
        lines.append(extra)
    return "\n".join(lines)


def _indicator_rows(topics):
    rows = {}

    def walk(items, topic, category, parent):
        for item in items or []:
            name = _clean(item.get("title_ENG"))
            code = _clean(item.get("code"))
            if code and name and code not in rows:
                name_am = _second(name, item.get("title_AMH"))
                unit = _clean(item.get("measurement_units"))
                unit = "" if unit == "None" else unit
                context = f"Topic: {_clean(topic.get('title_ENG'))}; category: {_clean(category.get('name_ENG'))}"
                if parent:
                    context += f"; part of {parent}"
                description = lead_sentence(item.get("description"))
                rows[code] = {
                    "kind": CatalogEntity.INDICATOR,
                    "external_id": code,
                    "code": code,
                    "name": name,
                    "name_am": name_am,
                    "aliases": [code],
                    "context": context[:500],
                    "details": {
                        "unit": unit,
                        "frequency": _clean(item.get("frequency")),
                        "source": _clean(item.get("source")),
                        "topic": _clean(topic.get("title_ENG")),
                        "category": _clean(category.get("name_ENG")),
                        "parent": parent,
                        "description": description,
                    },
                    "search_text": _search_text("indicator", name, name_am, context, description),
                }
            walk(item.get("children"), topic, category, name or parent)

    for topic in topics:
        for category in topic.get("categories") or []:
            if not category.get("is_deleted"):
                walk(category.get("indicators"), topic, category, "")
    return list(rows.values())


# Saved from each sync row; a change to any of them updates the entity.
STORED_FIELDS = ("code", "name", "name_am", "aliases", "context", "details", "search_text")

def _dpmes_rows(organizations, org_cards, areas, area_cards):
    rows = []
    for org in organizations:
        if org.get("id") not in org_cards:
            continue
        name = _clean(org.get("name") or org.get("trans_name"))
        code = _clean(org.get("code"))
        name_am = _second(name, org.get("name_eth"))
        area_names = [_clean(a.get("name")) for a in (org_cards[org["id"]].get("policy_areas") or [])]
        context = "Public body (ministry or agency)" + (f"; policy areas: {'; '.join(area_names[:8])}" if area_names else "")
        # DPMES misspells some names ("Minsitry of Education"); accept the right spelling too.
        aliases = [alias for alias in (code, name.replace("Minsitry", "Ministry")) if alias and alias != name]
        # The Ministry of Planning and Development is now the Ministry of National Strategy.
        if code.upper() in ("MOPD", "MONS") or "planning and development" in name.lower():
            aliases += [a for a in ("Ministry of National Strategy", "MoNS", "Ministry of Planning and Development", "MoPD")
                        if a != name and a not in aliases]
        rows.append({
            "kind": CatalogEntity.ORGANIZATION, "external_id": str(org["id"]), "code": code,
            "name": name, "name_am": name_am, "aliases": aliases,
            "context": context[:500], "details": {},
            "search_text": _search_text("public body", name, name_am, context),
        })

    seen_goals = set()
    for area in areas:
        name = _clean(area.get("name") or area.get("trans_name"))
        code = _clean(area.get("code"))
        name_am = _second(name, area.get("name_eth"))
        goals = (area_cards.get(area.get("id")) or {}).get("goals") or []
        goal_names = [_clean(g.get("name")) for g in goals]
        context = "National policy area" + (f"; goals: {'; '.join(goal_names[:10])}" if goal_names else "")
        rows.append({
            "kind": CatalogEntity.POLICY_AREA, "external_id": str(area["id"]), "code": code,
            "name": name, "name_am": name_am, "aliases": [code] if code else [],
            "context": context[:500], "details": {},
            "search_text": _search_text("policy area", name, name_am, context),
        })
        for goal in goals:
            if goal.get("id") in seen_goals:
                continue
            seen_goals.add(goal.get("id"))
            goal_name = _clean(goal.get("name") or goal.get("trans_name"))
            goal_code = _clean(goal.get("code"))
            goal_am = _second(goal_name, goal.get("name_eth"))
            goal_context = f"Strategic goal under the policy area {name}"
            rows.append({
                "kind": CatalogEntity.GOAL, "external_id": str(goal["id"]), "code": goal_code,
                "name": goal_name, "name_am": goal_am, "aliases": [goal_code] if goal_code else [],
                "context": goal_context[:500], "details": {"policy_area_id": area["id"], "policy_area": name},
                "search_text": _search_text("strategic goal", goal_name, goal_am, goal_context),
            })
    return rows


def _sdg_rows(goals):
    """SDG goals and indicators. Indicators without data stay in the catalog: their
    proxy or additional indicators (1.1.1P1 for 1.1.1) answer for them."""
    rows, indicators = [], {}
    for feed in goals:
        goal = feed.get("goal") or {}
        goal_id = _clean(goal.get("id"))
        if not goal_id:
            continue
        goal_name = _clean(goal.get("goal"))
        goal_context = f"Sustainable Development Goal {goal_id}: {_clean(goal.get('description'))}"
        rows.append({
            "kind": CatalogEntity.SDG_GOAL, "external_id": goal_id, "code": f"SDG {goal_id}",
            "name": goal_name, "name_am": "",
            "aliases": [f"SDG {goal_id}", f"SDG{goal_id}", f"Goal {goal_id}", f"SDG goal {goal_id}"],
            "context": goal_context[:500],
            "details": {"description": _clean(goal.get("description"))},
            "search_text": _search_text("Sustainable Development Goal", goal_name, "", goal_context),
        })
        targets = {_clean(t.get("id")): _clean(t.get("description")) for t in feed.get("targets") or []}
        for item in feed.get("indicators") or []:
            code = _clean(item.get("id"))
            name = _clean(item.get("description"))
            if not code or not name:
                continue
            target = _clean(item.get("target"))
            kind_note = {"Proxy": "proxy for", "Additional": "additional indicator for", "Split": "part of"}.get(
                item.get("type"), "")
            parent = _clean(item.get("parentIndicator"))
            context = f"SDG {goal_id} {goal_name}; target {target}: {targets.get(target, '')}"
            if parent and kind_note:
                context += f"; {kind_note} indicator {parent}"
            # The platform lists a few indicators twice (11.b.2); keep the copy with data.
            if code in indicators and (indicators[code]["details"]["has_data"] or not item.get("data")):
                continue
            indicators[code] = {
                "kind": CatalogEntity.SDG_INDICATOR, "external_id": code, "code": code,
                "name": name, "name_am": "", "aliases": [code, f"SDG {code}", f"indicator {code}"],
                "context": context[:500],
                "details": {
                    "goal": goal_id, "goal_name": goal_name, "target": target, "type": _clean(item.get("type")),
                    "parent": parent, "has_data": bool(item.get("data")),
                    "sources": [_clean(s) for s in item.get("sources") or [] if _clean(s)],
                    "providers": [_clean(s) for s in item.get("providers") or [] if _clean(s)],
                    "definition": lead_sentence(item.get("definition")),
                },
                "search_text": _search_text("SDG indicator", name, "", context, lead_sentence(item.get("definition"))),
            }
    return rows + list(indicators.values())


def sync(*, include_dpmes=True, include_sdg=True, period=None, log=LOGGER.info):
    """Upsert the catalog from the live APIs and embed rows whose text changed.

    Rows no longer present upstream are deactivated, not deleted, so traces that
    point at them stay readable. Returns counts by outcome.
    """
    from integrations.dpmes import client as dpmes_client

    log("Fetching time-series topics…")
    rows = _indicator_rows(time_series_client.fetch_topics())
    log(f"  {len(rows)} indicators")
    if include_dpmes:
        period = period or {"year": dpmes_client.current_ethiopian_year() - 1}
        log(f"Fetching DPMES for {period}…")
        dpmes = _dpmes_rows(*fetch_dpmes(period))
        rows += dpmes
        log(f"  {len(dpmes)} organizations, policy areas and goals")
    if include_sdg:
        log("Fetching the national SDG platform…")
        try:
            sdg = _sdg_rows(fetch_sdg())
        except sdg_client.SDGError as exc:
            # Keep the SDG rows already in the catalog rather than failing the whole sync.
            log(f"  skipped: {exc}")
            include_sdg = False
        else:
            rows += sdg
            log(f"  {len(sdg)} SDG goals and indicators")

    model_name = llm.embedding_model()
    existing = {(e.kind, e.external_id): e for e in CatalogEntity.objects.all()}
    to_embed, seen = [], set()
    counts = {"created": 0, "updated": 0, "unchanged": 0, "deactivated": 0}

    with transaction.atomic():
        for row in rows:
            key = (row["kind"], row["external_id"])
            seen.add(key)
            text_hash = hashlib.sha256(f"{model_name}\n{row['search_text']}".encode()).hexdigest()
            entity = existing.get(key)
            if entity is None:
                entity = CatalogEntity(kind=row["kind"], external_id=row["external_id"])
                counts["created"] += 1
            elif (entity.text_hash == text_hash and entity.is_active and entity.embedding
                    and all(getattr(entity, name) == row[name] for name in STORED_FIELDS)):
                counts["unchanged"] += 1
                continue
            else:
                counts["updated"] += 1
            for name in STORED_FIELDS:
                setattr(entity, name, row[name])
            entity.is_active = True
            if entity.text_hash != text_hash or not entity.embedding:
                entity.text_hash = text_hash
                to_embed.append(entity)
            entity.save()

        include_kinds = {CatalogEntity.INDICATOR} | (
            {CatalogEntity.ORGANIZATION, CatalogEntity.POLICY_AREA, CatalogEntity.GOAL} if include_dpmes else set()
        ) | ({CatalogEntity.SDG_GOAL, CatalogEntity.SDG_INDICATOR} if include_sdg else set())
        for key, entity in existing.items():
            if key not in seen and entity.is_active and entity.kind in include_kinds:
                entity.is_active = False
                entity.save(update_fields=["is_active", "updated_at"])
                counts["deactivated"] += 1

    log(f"Embedding {len(to_embed)} new or changed rows…")
    for start in range(0, len(to_embed), EMBED_BATCH):
        batch = to_embed[start:start + EMBED_BATCH]
        vectors = llm.embed_documents([entity.search_text for entity in batch])
        for entity, vector in zip(batch, vectors):
            entity.embedding = vector.astype("<f4").tobytes()
            entity.embedding_model = model_name
            entity.save(update_fields=["embedding", "embedding_model", "updated_at"])
        log(f"  embedded {min(start + EMBED_BATCH, len(to_embed))}/{len(to_embed)}")

    CatalogIndex.invalidate()
    counts["embedded"] = len(to_embed)
    return counts


# --- Index and resolution ---------------------------------------------------


@dataclass
class Match:
    entity_id: int
    kind: str
    external_id: str
    code: str
    name: str
    score: float
    method: str
    details: dict = field(default_factory=dict)

    def as_dict(self):
        return {
            "id": self.entity_id, "kind": self.kind, "external_id": self.external_id, "code": self.code,
            "name": self.name, "score": round(self.score, 3), "method": self.method,
        }


class CatalogIndex:
    """In-memory view of active entities, rebuilt when stale."""

    _lock = threading.Lock()
    _instance = None
    _loaded_at = 0.0

    def __init__(self, entities):
        self.by_kind = {}
        for kind in dict(CatalogEntity.KIND_CHOICES):
            rows = [e for e in entities if e.kind == kind and e.embedding]
            vectors = np.stack([np.frombuffer(bytes(e.embedding), dtype="<f4") for e in rows]) if rows else None
            exact = {}
            for e in rows:
                for key in [e.code, e.name, e.name_am, *(e.aliases or [])]:
                    if key:
                        exact.setdefault(normalise_text(key), e)
            # Codes are matched exactly above; their fragments ("exp", "02") would
            # only dilute word matching, so names and non-code aliases only.
            name_words = [
                {w for w in words(" ".join([e.name, *[a for a in (e.aliases or []) if a != e.code]])) if not any(c.isdigit() for c in w)}
                for e in rows
            ]
            context_words = [set(words(e.context)) for e in rows]
            # Rare words ("coffee") identify an entity; common ones ("export") barely do.
            document_frequency = {}
            for name_set, context_set in zip(name_words, context_words):
                for word in name_set | context_set:
                    document_frequency[word] = document_frequency.get(word, 0) + 1
            idf = {w: math.log((len(rows) + 1) / (df + 0.5)) for w, df in document_frequency.items()}
            self.by_kind[kind] = {
                "rows": rows,
                "vectors": vectors,
                "exact": exact,
                "name_words": name_words,
                "context_words": context_words,
                "idf": idf,
                "vocabulary": sorted(idf),
            }

    @classmethod
    def get(cls):
        with cls._lock:
            if cls._instance is None or time.time() - cls._loaded_at > INDEX_TTL_SECONDS:
                cls._instance = cls(list(CatalogEntity.objects.filter(is_active=True)))
                cls._loaded_at = time.time()
            return cls._instance

    @classmethod
    def invalidate(cls):
        with cls._lock:
            cls._instance = None

    def size(self, kind=None):
        kinds = [kind] if kind else list(self.by_kind)
        return sum(len(self.by_kind[k]["rows"]) for k in kinds)


def _match(entity, score, method):
    return Match(entity.id, entity.kind, entity.external_id, entity.code, entity.name, float(score), method, entity.details or {})


def _query_words(text, bucket):
    """Query words, with misspellings snapped to the closest catalog word."""
    result = []
    for word in words(text):
        if word not in bucket["idf"]:
            close = difflib.get_close_matches(word, bucket["vocabulary"], n=1, cutoff=0.85)
            word = close[0] if close else word
        result.append(word)
    return result


def _lexical(query_words, bucket, i):
    """Rarity-weighted word overlap between the query and entity i.

    Recall: how much of the query the entity covers (name words count fully,
    context words half). Precision: how much of the entity's name the query
    covers, so "GDP Growth" beats "Crop Contribution to GDP Growth".
    """
    idf, name, context = bucket["idf"], bucket["name_words"][i], bucket["context_words"][i]
    weight = lambda w: idf.get(w, math.log(len(bucket["rows"]) + 1))
    query = set(query_words)
    if not query:
        return 0.0
    recall = sum(weight(w) * (1.0 if w in name else 0.5 if w in context else 0.0) for w in query)
    recall /= sum(weight(w) for w in query)
    name_total = sum(weight(w) for w in name)
    precision = sum(weight(w) for w in name if w in query) / name_total if name_total else 0.0
    return 0.7 * recall + 0.3 * precision


async def resolve(text, kind, *, limit=3):
    """Best catalog matches for `text` among entities of `kind`, best first.

    Exact code/name/alias matches win outright. Otherwise rank by embedding
    similarity blended with lexical similarity, which keeps "GDP Growth" ahead
    of "Crop Contribution to GDP Growth" for the query "GDP growth".
    """
    # Loading the index queries the database, which Django forbids on the event loop.
    index = await sync_to_async(CatalogIndex.get)()
    bucket = index.by_kind.get(kind)
    if not text or not bucket or not bucket["rows"]:
        return []

    query = normalise_text(text)
    exact = bucket["exact"].get(query)
    if exact is not None:
        return [_match(exact, 1.0, "exact")]

    vector = await llm.embed_query(text)
    semantic = bucket["vectors"] @ vector
    query_words = _query_words(text, bucket)
    # Score every entity lexically too: a strong word match the embedding ranks
    # low ("national unemployment") must still be able to win.
    lexical = np.array([_lexical(query_words, bucket, i) for i in range(len(bucket["rows"]))])
    blended = 0.55 * semantic + 0.45 * lexical
    scored = [(float(blended[i]), i) for i in np.argsort(-blended)[:limit]]
    return [_match(bucket["rows"][i], score, "semantic") for score, i in scored]
