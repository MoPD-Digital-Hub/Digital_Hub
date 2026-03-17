from dataclasses import dataclass


@dataclass
class AIServiceError(Exception):
    code: str
    message: str
    dependency: str | None = None

    def to_dict(self):
        return {
            "code": self.code,
            "message": self.message,
            "dependency": self.dependency,
        }


ERROR_PROVIDER_DOWN = "PROVIDER_DOWN"
ERROR_RETRIEVAL_EMPTY = "RETRIEVAL_EMPTY"
ERROR_LLM_TIMEOUT = "LLM_TIMEOUT"
ERROR_BAD_PROMPT_OUTPUT = "BAD_PROMPT_OUTPUT"
ERROR_UPSTREAM_FAILURE = "UPSTREAM_FAILURE"
ERROR_QUEUE_UNAVAILABLE = "QUEUE_UNAVAILABLE"
