from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from Notification.models import DeviceToken, Notification, NotificationCategory
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


@api_view(['POST', 'DELETE'])
@permission_classes([IsAuthenticated])
def devices(request):
    """Register (POST) or remove (DELETE) an FCM device token for the
    authenticated user. Used for targeted pushes such as chat messages."""
    token = request.data.get('token')
    if not token:
        return Response(
            {
                "result": "FAILURE",
                "message": "token is required",
                "data": None
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    if request.method == 'POST':
        platform = request.data.get('platform', 'android')
        if platform not in dict(DeviceToken.PLATFORM_CHOICES):
            platform = 'android'
        DeviceToken.objects.update_or_create(
            token=token,
            defaults={"user": request.user, "platform": platform}
        )
        return Response(
            {
                "result": "SUCCESS",
                "message": "Device registered",
                "data": None
            },
            status=status.HTTP_200_OK
        )

    DeviceToken.objects.filter(token=token, user=request.user).delete()
    return Response(
        {
            "result": "SUCCESS",
            "message": "Device removed",
            "data": None
        },
        status=status.HTTP_200_OK
    )
