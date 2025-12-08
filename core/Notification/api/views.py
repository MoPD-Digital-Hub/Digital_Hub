from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from Notification.models import Notification, NotificationCategory
from .serializers import NotificationSerializer, NotificationCategorySerializer

@api_view(['GET'])
def categories(request):
    categories = NotificationCategory.objects.all()
    serializer = NotificationCategorySerializer(categories, many=True)
    return Response(
        {
            "result": "SUCCESS",
            "message": "Category successfully fetched",
            "data": serializer.data
        },
        status=status.HTTP_200_OK
    )
    

@api_view(['GET'])
def notifications(request):
    category = request.query_params.get('category')

    if category:
        notifications = Notification.objects.filter(category__id=category).order_by('-created_at')
    else:
        notifications = Notification.objects.all().order_by('-created_at')
        
    serializer = NotificationSerializer(notifications, many=True)
    return Response(
        {
            "result": "SUCCESS",
            "message": "Notifications successfully fetched",
            "data": serializer.data
        },
        status=status.HTTP_200_OK
    )
