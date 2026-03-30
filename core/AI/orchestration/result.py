from dataclasses import dataclass, field
from typing import Any


@dataclass
class OrchestrationResult:
    intent: str
    success: bool
    message: str
    language: str
    secondary_intents: list[str] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)
    tool_state: dict[str, Any] = field(default_factory=dict)
    errors: dict[str, Any] = field(default_factory=dict)
    usage: dict[str, Any] | None = None
    sources: list[dict[str, Any]] = field(default_factory=list)
    charts: list[dict[str, Any]] = field(default_factory=list)
    context_found: bool = False
    response_type: str = ""
