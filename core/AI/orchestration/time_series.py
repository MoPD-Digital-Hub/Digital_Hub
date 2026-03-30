from AI.gemini.service import ChatGenerationResult, GeminiChatService
from AI.retrieval import MilvusContextRetriever, RetrievalError


class TimeSeriesQueryError(Exception):
    pass


class TimeSeriesQueryService:
    def __init__(self, retriever=None, text_service=None):
        self.retriever = retriever or MilvusContextRetriever()
        self.text_service = text_service or GeminiChatService(retriever=self.retriever)

    def retrieve(self, question: str, preprocessed=None):
        retrieval = self.retriever.retrieve(question, preprocessed=preprocessed)
        has_structured_data = any((chart or {}).get("data") for chart in retrieval.charts or [])
        if not has_structured_data:
            raise TimeSeriesQueryError("No structured time-series data was found.")
        return retrieval

    def answer(self, *, question: str, history_records=None, preprocessed=None) -> ChatGenerationResult:
        retrieval = self.retrieve(question, preprocessed=preprocessed)
        return self.text_service.generate_from_retrieval(
            question=question,
            history_records=history_records or [],
            retrieval=retrieval,
        )
