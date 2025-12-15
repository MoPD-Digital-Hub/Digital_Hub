from celery import shared_task
from AI.utils import run_chain_stream
from asgiref.sync import async_to_sync, sync_to_async
from AI.models import QuestionHistory, ChatInstance
from AI.ai_instance import retriever, llm
import asyncio
import re
import requests
from langchain_core.messages import AIMessage, HumanMessage
from AI.utils import build_prompt, run_chain_stream
from rest_framework.response import Response
import anyio


def get_chat_history(instance):
    """
    Fetch previous Q&A pairs for conversation context.
    """
    history = QuestionHistory.objects.filter(instance=instance, response__isnull=False).order_by('created_at')
    conversation = []
    for record in history:
        conversation.append(HumanMessage(content=record.question))
        conversation.append(AIMessage(content=record.response))
    return conversation

def extract_year_from_question(question):
    """
    Extract a 4-digit year from the question string.
    Returns the year as int, or None if not found.
    """
    match = re.search(r"\b(19|20)\d{2}\b", question)
    if match:
        return int(match.group())
    return None

def fetch_time_series_value(indicator_code, year):
    url = "https://time-series.mopd.gov.et/api/mobile/annual_value/"
    params = {"code": indicator_code, "year": year}
    response = requests.get(url, params=params)
    if response.status_code == 200:
        return response.json()
    return None

async def _handle_question(question, instance_id, chat_id, question_instance_id):
    instance = await sync_to_async(ChatInstance.objects.get)(id=instance_id)
    question_instance = await sync_to_async(QuestionHistory.objects.get)(id=question_instance_id)

    year_requested = extract_year_from_question(question)

    # 1️⃣ Retrieve indicator info from Chroma
    docs = retriever.get_relevant_documents(question)

    if not docs:
        full_context = "No relevant indicator found."
    else:
        indicator_doc = docs[0] 
        metadata = indicator_doc.metadata
        indicator_code = metadata.get("code", "")
        unit = metadata.get("Unit", "")
        name = metadata.get("Indicator", "")
        topic = metadata.get("Topic", "")
        category = metadata.get("Category", "")
        source = metadata.get("Source", "")
        kpi_type = metadata.get("KPI Type", "")
        parent = metadata.get("Parent", "")
        version = metadata.get("Version", "")

        response = fetch_time_series_value(indicator_code, year_requested)

        historical_info = ""

        if "time_series" in response:
            ts = response["time_series"]

            # --- Annual Data ---
            annual = ts.get("annual", [])
            if annual:
                historical_info += "<h4>Annual Data</h4>\n"
                for item in annual:
                    historical_info += f"<p>{item['year']}: {item['value']} {unit}</p>\n"

            # --- Quarterly Data ---
            quarter = ts.get("quarter", [])
            if quarter:
                historical_info += "<h4>Quarterly Data</h4>\n"
                for item in quarter:
                    historical_info += f"<p>{item['year']} {item['quarter']}: {item['value']} {unit}</p>\n"

            # --- Monthly Data ---
            month = ts.get("month", [])
            if month:
                historical_info += "<h4>Monthly Data</h4>\n"
                for item in month:
                    historical_info += f"<p>{item['year']} {item['month']}: {item['value']} {unit}</p>\n"

            if historical_info.strip() == "":
                historical_info = "<p>No historical data available</p>"
                
        elif "value" in response:
            # single year
            historical_info = f"<p>{year_requested}: {response['value']} {unit}</p>\n"
        else:
            historical_info = "<p>Data not available</p>"

        # Step 4: build metadata string
        metadata_info = f"""
        Indicator Metadata:
        Name: {name}
        Code: {indicator_code}
        Topic: {topic}
        Category: {category}
        Unit: {unit}
        Source: {source}
        KPI Type: {kpi_type}
        Parent: {parent}
        Version: {version}
        """

        # Step 5: combine everything
        formatted_context = "\n\n".join([d.page_content for d in docs])
        full_context = formatted_context + "\n\n" + metadata_info + "\n\n" + historical_info

    conversation_list = await sync_to_async(get_chat_history)(instance)

    prompt = build_prompt(full_context, question)

    full_response = ""

    import httpx 
    async with httpx.AsyncClient() as client:
        async for chunk in run_chain_stream(prompt=prompt, llm=llm, conversation_list=conversation_list, context=full_context, question=question):
            full_response += chunk
            await client.post(
                "http://localhost:9000/stream_chunk",
                json={"chat_id": chat_id, "chunk": chunk}
            )

    
    question_instance.response = full_response
    await sync_to_async(question_instance.save)()

    return Response({
        "result": "SUCCESS",
        "message": "Answer generated successfully!",
        "data": full_response
    }, status=200)


# @shared_task
# def handle_question_task(question, instance_id, chat_id, question_instance_id):
#     instance = ChatInstance.objects.get(id=instance_id)
#     question_instance = QuestionHistory.objects.get(id=question_instance_id)

#     asyncio.run(_handle_question(question, instance, chat_id, question_instance))


@shared_task
def handle_question_task(question, instance_id, chat_id, question_instance_id):
    anyio.run(_handle_question, question, instance_id, chat_id, question_instance_id)

# @shared_task
# def handle_question_task(prompt, conversation_list, full_context, question, chat_id, question_instance_id):

#     async def async_worker():
#         full_response = ""

#         async with httpx.AsyncClient() as client:
#             async for chunk in run_chain_stream(
#                 prompt=prompt,
#                 llm=llm,
#                 conversation_list=conversation_list,
#                 context=full_context,
#                 question=question
#             ):
#                 full_response += chunk

#                 await client.post(
#                     "http://localhost:9000/stream_chunk",
#                     json={"chat_id": chat_id, "chunk": chunk}
#                 )

#         qi = await sync_to_async(QuestionHistory.objects.get)(id=question_instance_id)
#         qi.response = full_response
#         await sync_to_async(qi.save)()

#     asyncio.run(async_worker())
