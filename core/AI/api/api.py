from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from AI.models import QuestionHistory, ChatInstance
from .serializer import ChatInstanceSerializer, QuestionHistorySerializer
from langchain_core.messages import AIMessage, HumanMessage



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


