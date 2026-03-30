from dataclasses import dataclass

from AI.retrieval import MilvusContextRetriever


@dataclass
class ScorecardQueryResult:
    answer: str
    language: str
    scorecard: dict | None
    sources: list
    context_found: bool
    found: bool


class ScorecardQueryService:
    def __init__(self, retriever=None):
        self.retriever = retriever or MilvusContextRetriever()

    def answer(self, *, question: str, history_records=None, language: str = "English", preprocessed=None) -> ScorecardQueryResult:
        retrieval = self.retriever.retrieve(question, preprocessed=preprocessed)
        scorecard = self._extract_scorecard(retrieval.sources)
        if not scorecard:
            message = (
                "<p>No DPMES performance scorecard data found for this public body.</p>"
                if language != "Amharic"
                else "<p>ለዚህ የህዝብ ተቋም የDPMES የአፈጻጸም ስኮርካርድ መረጃ አልተገኘም።</p>"
            )
            return ScorecardQueryResult(
                answer=message,
                language=language,
                scorecard=None,
                sources=[],
                context_found=False,
                found=False,
            )

        message = self._build_summary(scorecard, language)
        return ScorecardQueryResult(
            answer=message,
            language=language,
            scorecard=scorecard,
            sources=[source for source in (retrieval.sources or []) if source.get("public_body_score")],
            context_found=True,
            found=True,
        )

    def _extract_scorecard(self, sources) -> dict | None:
        for source in sources or []:
            if isinstance(source, dict) and isinstance(source.get("public_body_score"), dict):
                return dict(source["public_body_score"])
        return None

    def _build_summary(self, scorecard: dict, language: str) -> str:
        title = str(scorecard.get("responsible_ministry_eng") or "Public body").strip()
        score_card = scorecard.get("ministry_score_card") or {}
        score = str(score_card.get("score") or "--").strip()
        policy_areas = [item for item in (scorecard.get("policy_areas") or []) if isinstance(item, dict)]
        best = self._best_policy_area(policy_areas)

        if language == "Amharic":
            if best:
                return (
                    f"<p><strong>{title}</strong> አጠቃላይ ውጤቱ <strong>{score}</strong> ነው። "
                    f"ከፖሊሲ ዘርፎች ውስጥ <strong>{best.get('policy_area_eng') or 'N/A'}</strong> "
                    f"<strong>{best.get('score') or '--'}</strong> በማግኘት የተሻለ አፈጻጸም አሳይቷል።</p>"
                )
            return f"<p><strong>{title}</strong> አጠቃላይ ውጤቱ <strong>{score}</strong> ነው።</p>"

        if best:
            return (
                f"<p><strong>{title}</strong> has an overall score of <strong>{score}</strong>. "
                f"The strongest reported policy area is <strong>{best.get('policy_area_eng') or 'N/A'}</strong> "
                f"with a score of <strong>{best.get('score') or '--'}</strong>.</p>"
            )
        return f"<p><strong>{title}</strong> has an overall score of <strong>{score}</strong>.</p>"

    def _best_policy_area(self, policy_areas):
        ranked = []
        for item in policy_areas:
            score_value = self._score_to_number(item.get("score"))
            ranked.append((score_value, item))
        ranked.sort(key=lambda entry: entry[0], reverse=True)
        return ranked[0][1] if ranked else None

    def _score_to_number(self, value) -> float:
        text = str(value or "").strip().replace("%", "")
        try:
            return float(text)
        except (TypeError, ValueError):
            return -1.0
