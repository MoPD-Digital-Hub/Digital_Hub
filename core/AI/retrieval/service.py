import logging
from dataclasses import dataclass
from typing import Any

from langchain_milvus import Milvus
from pymilvus import MilvusClient

from AI.gemini.language import detect_language
from AI.query_preprocessing import QueryPreprocessor

from .config import get_retrieval_settings
from .embeddings import get_embeddings
from .ministry_score import (
    MinistryScoreAPIError,
    fetch_public_body_score,
    format_public_body_score_context,
    parse_requested_period,
    resolve_public_body_id,
)
from .query_normalizer import normalize_retrieval_query
from .resolver import query_tokens, resolve_indicator_query
from .time_series import TimeSeriesAPIError, build_time_series_chart, fetch_indicator_time_series, format_time_series_context

LOGGER = logging.getLogger("AI.retrieval")

_vector_store_cache = None


class RetrievalError(Exception):
    pass


@dataclass
class RetrievalResult:
    context: str
    sources: list[dict[str, Any]]
    charts: list[dict[str, Any]]
    query_text: str


class MilvusContextRetriever:
    def __init__(self, settings=None):
        self.settings = settings or get_retrieval_settings()
        self.preprocessor = QueryPreprocessor()

    def retrieve(self, question: str, preprocessed=None) -> RetrievalResult:
        search_query = str(question or "").strip()
        if not search_query:
            return RetrievalResult(context="", sources=[], charts=[], query_text=search_query)

        prepared = preprocessed or self.preprocessor.preprocess(search_query)
        query_candidates = self._query_candidates(search_query, prepared)
        docs = []
        for candidate in query_candidates:
            docs.extend(self._retrieve_docs(candidate))
        docs = self._deduplicate_docs(docs)
        docs = self._rerank_docs(docs, " ".join(query_candidates))
        context, charts = self._format_context(docs, search_query)
        sources = [self._source_metadata(doc) for doc in docs]
        return RetrievalResult(context=context, sources=sources, charts=charts, query_text=query_candidates[0] if query_candidates else search_query)

    def health(self) -> dict:
        try:
            client = MilvusClient(uri=self.settings.milvus_uri, timeout=self.settings.retrieval_timeout_seconds)
            ok = client.has_collection(collection_name=self.settings.collection_name)
            return {"ok": bool(ok), "collection": self.settings.collection_name, "uri": self.settings.milvus_uri}
        except Exception as exc:
            return {"ok": False, "error": str(exc), "collection": self.settings.collection_name, "uri": self.settings.milvus_uri}

    def _retrieve_docs(self, search_query: str):
        vector_store = self._get_vector_store()
        try:
            return vector_store.max_marginal_relevance_search(
                search_query,
                k=self.settings.retrieval_k,
                fetch_k=self.settings.retrieval_fetch_k,
                lambda_mult=0.3,
            )
        except Exception as exc:
            LOGGER.warning("MMR search failed, falling back to similarity search: %s", str(exc))
            try:
                return vector_store.similarity_search(search_query, k=self.settings.retrieval_k)
            except Exception as fallback_exc:
                raise RetrievalError(str(fallback_exc)) from fallback_exc

    def _query_candidates(self, question: str, preprocessed) -> list[str]:
        candidates = []
        variants = [preprocessed.best_query, preprocessed.corrected, preprocessed.normalized] + list(preprocessed.variants or []) + [question]
        for variant in variants:
            normalized_query = normalize_retrieval_query(str(variant or "").strip())
            resolved_query = resolve_indicator_query(normalized_query)
            if resolved_query and resolved_query not in candidates:
                candidates.append(resolved_query)
            if len(candidates) >= 4:
                break
        return candidates

    def _get_vector_store(self):
        global _vector_store_cache
        if _vector_store_cache is not None:
            return _vector_store_cache

        try:
            _vector_store_cache = Milvus(
                embedding_function=get_embeddings(),
                connection_args={"uri": self.settings.milvus_uri, "alias": "default"},
                collection_name=self.settings.collection_name,
                text_field="text",
                vector_field="vector",
                primary_field="pk",
                enable_dynamic_field=True,
                auto_id=False,
            )
        except Exception as exc:
            raise RetrievalError(str(exc)) from exc
        return _vector_store_cache

    def _deduplicate_docs(self, docs):
        deduped = []
        seen = set()
        for doc in docs or []:
            meta = getattr(doc, "metadata", {}) or {}
            key = (
                meta.get("pk") or meta.get("indicator_code") or meta.get("source_id"),
                getattr(doc, "page_content", ""),
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(doc)
        return deduped

    def _rerank_docs(self, docs, resolved_query: str):
        tokens = query_tokens(resolved_query)
        if not tokens:
            return docs

        scored = []
        for index, doc in enumerate(docs or []):
            meta = getattr(doc, "metadata", {}) or {}
            metadata_text = " ".join(
                str(meta.get(key) or "")
                for key in (
                    "indicator_eng",
                    "indicator_code",
                    "topic_name",
                    "category_name",
                    "responsible_ministry_eng",
                    "source",
                    "year",
                    "quarter",
                )
            )
            content_text = str(getattr(doc, "page_content", "") or "")
            metadata_tokens = query_tokens(metadata_text)
            content_tokens = query_tokens(content_text)
            overlap_meta = len(tokens & metadata_tokens)
            overlap_content = len(tokens & content_tokens)
            indicator_bonus = 5 if meta.get("indicator_code") else 0
            score = overlap_meta * 4 + overlap_content + indicator_bonus - index
            scored.append((score, index, doc))

        scored.sort(key=lambda item: (item[0], -item[1]), reverse=True)
        return [item[2] for item in scored]

    def _format_context(self, docs, question: str = ""):
        blocks = []
        enriched_codes = set()
        enriched_public_bodies = set()
        charts = []
        requested_year, requested_quarter = parse_requested_period(question)
        for index, doc in enumerate(docs or [], start=1):
            text = str(getattr(doc, "page_content", "") or "").strip()
            if not text:
                continue
            meta = getattr(doc, "metadata", {}) or {}
            source_lines = []
            for key in (
                "indicator_eng",
                "indicator_code",
                "topic_name",
                "category_name",
                "responsible_ministry_eng",
                "source",
                "year",
                "quarter",
            ):
                value = meta.get(key)
                if value not in (None, ""):
                    source_lines.append(f"{key}: {value}")
            time_series_context, chart = self._time_series_context(meta, enriched_codes)
            if time_series_context:
                source_lines.append("time_series_api:")
                source_lines.append(time_series_context)
            public_body_context = self._public_body_score_context(
                meta,
                requested_year=requested_year,
                requested_quarter=requested_quarter,
                enriched_public_bodies=enriched_public_bodies,
            )
            if public_body_context:
                source_lines.append("public_body_score_api:")
                source_lines.append(public_body_context)
            if chart:
                charts.append(chart)
            block = f"Source {index}\n" + "\n".join(source_lines) + f"\ntext: {text}"
            blocks.append(block.strip())
        return "\n\n".join(blocks), charts

    def _time_series_context(self, metadata, enriched_codes: set[str]):
        indicator_code = str((metadata or {}).get("indicator_code") or "").strip()
        if not indicator_code:
            return "", {}
        if indicator_code in enriched_codes:
            return "", {}
        if len(enriched_codes) >= self.settings.time_series_indicator_limit:
            return "", {}

        try:
            payload = fetch_indicator_time_series(indicator_code)
        except TimeSeriesAPIError:
            return "", {}

        formatted = format_time_series_context(payload)
        chart = build_time_series_chart(payload, metadata)
        if formatted:
            enriched_codes.add(indicator_code)
        return formatted, chart

    def _public_body_score_context(self, metadata, *, requested_year, requested_quarter, enriched_public_bodies: set):
        if len(enriched_public_bodies) >= self.settings.public_body_score_limit:
            return ""

        try:
            public_body_id = resolve_public_body_id(metadata, settings=self.settings)
        except MinistryScoreAPIError:
            return ""
        if not public_body_id or public_body_id in enriched_public_bodies:
            return ""

        try:
            payload = fetch_public_body_score(
                public_body_id,
                year=requested_year,
                quarter=requested_quarter,
                settings=self.settings,
            )
        except MinistryScoreAPIError:
            return ""

        formatted = format_public_body_score_context(payload)
        if formatted:
            metadata["_public_body_score"] = payload
            enriched_public_bodies.add(public_body_id)
        return formatted

    def _source_metadata(self, doc):
        meta = getattr(doc, "metadata", {}) or {}
        return {
            "indicator": meta.get("indicator_eng"),
            "indicator_code": meta.get("indicator_code"),
            "topic": meta.get("topic_name"),
            "category": meta.get("category_name"),
            "ministry": meta.get("responsible_ministry_eng"),
            "ministry_id": meta.get("ministry_id") or meta.get("responsible_ministry_id") or meta.get("public_body_id"),
            "source": meta.get("source"),
            "year": meta.get("year"),
            "quarter": meta.get("quarter"),
            "public_body_score": meta.get("_public_body_score"),
        }
