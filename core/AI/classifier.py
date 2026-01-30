from langchain_core.prompts import PromptTemplate
from AI.intents import INTENTS
import json

PROMPT = PromptTemplate(
    input_variables=["question"],
    template="""
You classify user questions ONLY for the DPMES system.

Choose ONE intent:

MINISTRY_SCORE → Use this if the question is about a specific Ministry, Government Body, or Agency (e.g., "MoH", "Ministry of Health", "MoPD"). 
- This includes their performance, scores, rankings, or status for any specific year/quarter.
- If a Ministry name is mentioned, this intent ALWAYS takes priority over TIME_SERIES.

MINISTRY_PERFORMANCE → Use this when the user's goal is to see a FILTERED LIST or CATEGORIZATION of specific indicators/KPIs based on how they are performing.
- Identifying specific successes or failures within a ministry.
- Requests for qualitative status groups (e.g., searching for what is "on track," "lagging," "missing data," or "performing poorly").
- Focuses on the "Why" and "What" (the specific items) rather than the "How much" (the total score).
- Example: "Give me the list of weak KPIs for MoA," or "Which health goals are meeting their targets?"

TIME_SERIES → Use this ONLY for specific economic or social indicators/metrics (e.g., "GDP", "Inflation", "Export value", "Unemployment rate").
- Use this when the user asks for historical trends or values of a specific numeric variable.

POLICY_AREA_SCORE → Use this for thematic sectors rather than institutions (e.g., "How is the Health Sector doing?" vs "How is the Ministry of Health doing?").

GOAL_SCORE → Strategic goal achievement, Ten Year Development Plan goals, or high-level national targets.

UNKNOWN → Greetings, general chat, or topics unrelated to DPMES data.

Question:
{question}

Return ONLY the intent name.
"""
)

def classify_intent(llm, question: str) -> str:
    result = llm.invoke(PROMPT.format(question=question))
    intent = result.content.strip().upper()
    return intent if intent in INTENTS else INTENTS["UNKNOWN"]

DPMES_EXTRACTION_YEAR_QUARTER_PROMPT = PromptTemplate(
    input_variables=["question"],
    template="""
Analyze the following user question about the DPMES system. 
Extract the Year, Quarter and the Reporting Period.

Normalize the "period" according to these rules:
- "3 month", "1st quarter", "Q1" -> "3month"
- "6 month", "half year", "2nd quarter", "Q2" -> "6month"
- "9 month", "3rd quarter", "Q3" -> "9month"
- "Annual", "Full year", "12 month", "4th quarter", "Q4" -> "12month"

Question: {question}

Return ONLY raw JSON:
{{
  "year": "YYYY or null",
  "quarter": "period or null"
}}
"""
)

def extract_year_quarter(llm, question: str) -> dict:
    """
    Parses the question to extract normalized year and quarter.
    Returns a dictionary, e.g., {"year": "2017", "quarter": "9month"}
    """
    result = llm.invoke(DPMES_EXTRACTION_YEAR_QUARTER_PROMPT.format(question=question))
    clean_content = result.content.strip().replace("```json", "").replace("```", "")
    
    try:
        data = json.loads(clean_content)
        return {
            "year": str(data.get("year")) if data.get("year") else None,
            "quarter": data.get("quarter", "12month")
        }
    except (json.JSONDecodeError, ValueError):
        return {"year": None, "quarter": "12month"}

DPMES_PERFORMANCE_STATUS_EXTRACTOR = PromptTemplate(
    input_variables=["question"],
    template="""
Analyze the user's question and map their performance-related language to exactly ONE of the system keys.

### System Keys:
- "on_track": (good, success, achieved, excellent, best, meeting targets)
- "in_progress": (average, satisfactory, moving, developing, mid-range)
- "weak_performance": (bad, poor, critical, failing, behind, low scores)
- "no_data": (missing, not reported, unknown, blank, unsubmitted)

### Important Rules:
- Ignore the year or quarter (e.g., "2018", "Q1"). Only extract the performance status.
- If the user is asking for general performance without a specific status (e.g., "How is MoH?"), return null.
- Return ONLY the key name. No explanation.

Question: {question}
Return (on_track/in_progress/weak_performance/no_data/null):"""
)

def extract_performance_type(llm, question: str):
    result = llm.invoke(DPMES_PERFORMANCE_STATUS_EXTRACTOR.format(question=question))
    content = result.content.strip().lower()
    
    valid_keys = ['on_track', 'in_progress', 'weak_performance', 'no_data']

    for key in valid_keys:
        if key in content:
            return key
            
    return None 