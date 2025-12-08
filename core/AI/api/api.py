from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes

from AI.ai_instance import retriever, llm
from AI.utils import build_prompt, run_chain, format_docs
from AI.models import QuestionHistory, ChatInstance
from .serializer import ChatInstanceSerializer, QuestionHistorySerializer
from langchain_core.messages import AIMessage, HumanMessage


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

            context_docs = retriever.invoke(question)
            formatted_context = format_docs(context_docs)

            conversation_list = get_chat_history(instance)

            prompt = build_prompt(formatted_context, question)
            ai_response = run_chain(prompt, llm, conversation_list, formatted_context, question)

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
