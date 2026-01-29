from langchain_core.prompts import PromptTemplate
from AI.intents import INTENTS

PROMPT = PromptTemplate(
    input_variables=["question"],
    template="""
You classify user questions ONLY for the DPMES system.

Choose ONE intent:

TIME_SERIES → questions about specific indicator values, historical data, or yearly/quarterly performance.
MINISTRY_SCORE → overall ministry performance, rankings, or IF the user ONLY mentions a ministry name/acronym (e.g., "MoPD", "Ministry of Health").
POLICY_AREA_SCORE → performance or status of specific thematic policy areas (e.g., "Macroeconomy", "Social Development").
GOAL_SCORE → strategic goal achievement, Ten Year Development Plan goals, or scores.
UNKNOWN → greetings, general chat, or topics unrelated to DPMES data.

Question:
{question}

Return ONLY the intent name.
"""
)

def classify_intent(llm, question: str) -> str:
    result = llm.invoke(PROMPT.format(question=question))
    intent = result.content.strip().upper()
    return intent if intent in INTENTS else INTENTS["UNKNOWN"]
