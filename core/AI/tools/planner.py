import json

from langchain_core.prompts import PromptTemplate

from AI.parsing import classify_intent, extract_performance_type, extract_year_quarter

from .helpers import normalize_quarter, normalize_year
from .runtime import MCPToolPlan, RUNTIME_TOOLS

TOOL_SELECTION_PROMPT = PromptTemplate(
    input_variables=["question", "tool_catalog"],
    template="""
You are an MCP tool router for the Ethiopia DPMES assistant.

Select exactly one tool from the catalog below based on the user's question.
Return ONLY raw JSON in this format:
{{
  "tool": "tool_name",
  "arguments": {{
    "year": "YYYY or null",
    "quarter": "3month|6month|9month|12month|null",
    "performance_type": "on_track|in_progress|weak_performance|no_data|null"
  }}
}}

Tool catalog:
{tool_catalog}

Rules:
- If the user is asking about GDP, inflation, export, unemployment, or trends over time, choose the time-series tool.
- If the user is asking about a ministry or agency score, choose the ministry score tool.
- If the user is asking for weak, strong, missing, on-track, or performance-grouped KPIs for a ministry, choose the ministry performance tool.
- If the user is asking about a policy area or sector score, choose the policy area tool.
- If the user is asking about strategic goals or national goals, choose the goal tool.
- If none clearly match, choose the general context tool.
- Prefer null for missing arguments.

Question:
{question}
""",
)


def _extract_json_block(text: str) -> str:
    text = (text or "").strip()
    text = text.replace("```json", "").replace("```", "").strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text


def _tool_catalog_text() -> str:
    return "\n".join(f"- {tool.name}: {tool.description}" for tool in RUNTIME_TOOLS.values())


def _fallback_plan(question: str, docs=None) -> MCPToolPlan:
    tool_name = classify_intent(None, question, docs=docs)
    period = extract_year_quarter(None, question)
    performance_type = extract_performance_type(None, question)
    return MCPToolPlan(
        tool_name=tool_name if tool_name in RUNTIME_TOOLS else "get_general_context",
        arguments={
            "year": period.get("year"),
            "quarter": period.get("quarter"),
            "performance_type": performance_type,
        },
    )


def resolve_mcp_tool_plan(llm, question: str, docs=None) -> MCPToolPlan:
    if llm is None:
        return _fallback_plan(question, docs=docs)

    try:
        raw = llm.invoke(
            TOOL_SELECTION_PROMPT.format(question=question, tool_catalog=_tool_catalog_text())
        )
        content = getattr(raw, "content", "")
        data = json.loads(_extract_json_block(content))
        tool_name = str(data.get("tool") or "").strip()
        if tool_name not in RUNTIME_TOOLS:
            return _fallback_plan(question, docs=docs)
        arguments = data.get("arguments") or {}
        return MCPToolPlan(
            tool_name=tool_name,
            arguments={
                "year": normalize_year(arguments.get("year")),
                "quarter": normalize_quarter(arguments.get("quarter")),
                "performance_type": arguments.get("performance_type"),
            },
        )
    except Exception:
        return _fallback_plan(question, docs=docs)


def execute_mcp_tool_plan(plan: MCPToolPlan, llm, question: str, docs):
    tool = RUNTIME_TOOLS.get(plan.tool_name) or RUNTIME_TOOLS.get("get_general_context")
    if tool is None:
        return "No relevant context available."
    return tool.handler(question=question, docs=docs, arguments=plan.arguments or {}, llm=llm)
