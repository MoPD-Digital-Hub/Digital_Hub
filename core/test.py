from langchain.tools import tool
from langchain.tools import Tool
import requests
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain.agents import initialize_agent, AgentType


llm = ChatOllama(
    model="llama3.2:latest",
    temperature=0.7,
    stream=True,
)

@tool
def get_policy_area(year: str) -> str:
 """Fetches policy areas using a REST API."""
 url = f"https://dpmes.mopd.gov.et/api/digital-hub/all-policy-area/?year=2017&quarter=3month"
 response = requests.get(url)
 return response.json()["data"]


policy_area_tool = Tool(
    name="get_policy_area",
    func=get_policy_area,
    description="Gets the policy areas."
)

tools = [policy_area_tool]

agent = initialize_agent(
    tools,
    llm,
    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,  # REACT pattern agent
    verbose=True
)

response = agent.run("Which policy areas have the lowest scores, and what are they trying to achieve?")
print(response)