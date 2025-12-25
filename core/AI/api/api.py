from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from AI.ai_instance import retriever, llm
from AI.utils import build_prompt, run_chain, format_docs, run_chain_stream
from AI.models import QuestionHistory, ChatInstance
from .serializer import ChatInstanceSerializer, QuestionHistorySerializer
from langchain_core.messages import AIMessage, HumanMessage
import requests
import re
from asgiref.sync import async_to_sync, sync_to_async
from AI.tasks.task import handle_question_task
import threading
import json
import asyncio

def fetch_time_series_value(indicator_code, year):
    url = "https://time-series.mopd.gov.et/api/mobile/annual_value/"
    params = {"code": indicator_code, "year": year}
    response = requests.get(url, params=params)
    if response.status_code == 200:
        return response.json()
    return None



def extract_year_from_question(question):
    """
    Extract a 4-digit year from the question string.
    Returns the year as int, or None if not found.
    """
    match = re.search(r"\b(19|20)\d{2}\b", question)
    if match:
        return int(match.group())
    return None



def get_chat_history(instance):
    """
    Fetch previous Q&A pairs for conversation context.
    """
    history = QuestionHistory.objects.filter(instance=instance, response__isnull=False).order_by('created_at')
    conversation = []
    for record in history[:3]:
        conversation.append(HumanMessage(content=record.question))
        conversation.append(AIMessage(content=record.response))
    return conversation


@api_view(['POST', 'GET'])
@permission_classes([IsAuthenticated])
def get_answer(request, chat_id):
    try:
        instance = ChatInstance.objects.get(id=chat_id)
    except ChatInstance.DoesNotExist:
        return Response({"result": "FAILURE", "data": None, "message": "Instance doesn't exist!"}, status=status.HTTP_400_BAD_REQUEST)

    if request.method == 'POST':
        serializer = QuestionHistorySerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(instance=instance)
            question = serializer.data['question']
            question_id = serializer.data['id']
            question_instance = QuestionHistory.objects.get(id=question_id)

            # Update title if empty
            if not instance.title:
                first_question = QuestionHistory.objects.filter(instance=instance).first()
                if first_question:
                    instance.title = first_question.question
                    instance.save()

            # Remove instances with no title
            ChatInstance.objects.filter(title=None).delete()

            year_requested = extract_year_from_question(question)

            # 1️⃣ Retrieve indicator info from Chroma
            docs = retriever.invoke(question)

            if not docs:
                full_context = "No relevant indicator found."
            else:
                all_indicators_context = []

                for indicator_doc in docs:
                    metadata = indicator_doc.metadata

                    indicator_code = metadata.get("code", "")
                    unit = metadata.get("unit", "")
                    name = metadata.get("name", "")
                    topic = metadata.get("topic", "")
                    category = metadata.get("category", "")
                    source = metadata.get("source", "")
                    kpi_type = metadata.get("kpi_type", "")
                    parent = metadata.get("parent", "")
                    version = metadata.get("version", "")

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

                        if not historical_info.strip():
                            historical_info = "<p>No historical data available</p>"

                    elif "value" in response:
                        historical_info = f"<p>{year_requested}: {response['value']} {unit}</p>"
                    else:
                        historical_info = "<p>Data not available</p>"

                    metadata_info = f"""
                    <h3>Indicator Metadata</h3>
                    <p><b>Name:</b> {name}</p>
                    <p><b>Code:</b> {indicator_code}</p>
                    <p><b>Topic:</b> {topic}</p>
                    <p><b>Category:</b> {category}</p>
                    <p><b>Unit:</b> {unit}</p>
                    <p><b>Source:</b> {source}</p>
                    <p><b>KPI Type:</b> {kpi_type}</p>
                    <p><b>Parent:</b> {parent}</p>
                    <p><b>Version:</b> {version}</p>
                    """

                    indicator_context = (
                        indicator_doc.page_content
                        + "\n\n"
                        + metadata_info
                        + "\n\n"
                        + historical_info
                    )

                    all_indicators_context.append(indicator_context)

                # ✅ Combine all indicators into one context
                full_context = "\n<hr/>\n".join(all_indicators_context)


            print(full_context)
            conversation_list = get_chat_history(instance)

            prompt = build_prompt(full_context, question)
            ai_response = run_chain(
                prompt=prompt,
                llm=llm,
                conversation_list=conversation_list,
                context=full_context,
                question=question
            )

            question_instance.response = ai_response.content
            question_instance.save()
            question_serializer = QuestionHistorySerializer(question_instance)

            return Response({
                "result": "SUCCESS",
                "message": "Answer generated successfully!",
                "data": question_serializer.data
            }, status=status.HTTP_200_OK)

        return Response({"result": "FAILURE", "data": None, "message": "No Question Provided!"}, status=status.HTTP_400_BAD_REQUEST)

    # Handle GET or other methods:
    return Response({"result": "FAILURE", "message": "GET method not implemented"}, status=status.HTTP_405_METHOD_NOT_ALLOWED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_chat_list(request, chat_instance_id):
    try:
        chat_instance = ChatInstance.objects.get(id=chat_instance_id)
    except ChatInstance.DoesNotExist:
        return Response({"result": "FAILURE", "data": None, "message": "Instance doesn't exist!"}, status=status.HTTP_400_BAD_REQUEST)

    histories = QuestionHistory.objects.filter(instance=chat_instance)
    histories_serializer = QuestionHistorySerializer(histories, many=True)
    return Response({"result": "SUCCESS", "message": "SUCCESS", "data": histories_serializer.data}, status=status.HTTP_200_OK)


@api_view(['POST', 'GET'])
@permission_classes([IsAuthenticated])
def chat(request):
    if request.method == 'GET':
        chat_instances = ChatInstance.objects.filter(user=request.user, is_deleted=False)
        serializer = ChatInstanceSerializer(chat_instances, many=True)
        return Response({"result": "SUCCESS", "message": "SUCCESS", "data": serializer.data}, status=status.HTTP_200_OK)

    elif request.method == 'POST':
        instance = ChatInstance(user=request.user)
        instance.save()
        serializer = ChatInstanceSerializer(instance)
        return Response({"result": "SUCCESS", "message": "SUCCESS", "data": serializer.data}, status=status.HTTP_200_OK)

    return Response({"result": "FAILURE", "data": None, "message": "Page not found!"}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_chat_instance(request, chat_instance_id):
    try:
        chat_instance = ChatInstance.objects.get(user=request.user, id=chat_instance_id)
    except ChatInstance.DoesNotExist:
        return Response({"result": "FAILURE", "data": None, "message": "Instance doesn't exist!"}, status=status.HTTP_400_BAD_REQUEST)

    chat_instance.is_deleted = True
    chat_instance.save()
    return Response({"result": "SUCCESS", "message": "Instance deleted successfully!", "data": None}, status=status.HTTP_200_OK)



@api_view(['POST'])
def get_answer_socket(request, chat_id):

    try:
        instance = ChatInstance.objects.get(id=chat_id)
    except ChatInstance.DoesNotExist:
        return Response({"result": "FAILURE", "data": None, "message": "Instance doesn't exist!"}, status=400)
    
    serializer = QuestionHistorySerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"result": "FAILURE", "data": None, "message": "No Question Provided!"}, status=400)

    # Save question
    serializer.save(instance=instance)
    question = serializer.data['question']
    question_id = serializer.data['id']
    question_instance = QuestionHistory.objects.get(id=question_id)

    if not instance.title:
        first_question = QuestionHistory.objects.filter(instance=instance).first()
        if first_question:
            instance.title = first_question.question
            instance.save()
    ChatInstance.objects.filter(title=None).delete()

    handle_question_task.delay(
        question,
        instance.id,
        chat_id,
        question_instance.id
    )

    return Response({
        "result": "PROCESSING",
        "message": "Answer is being generated in the background!",
        "chat_id": chat_id
    }, status=202)

