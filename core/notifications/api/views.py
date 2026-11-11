from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from notifications.models import DeviceToken, Notification, NotificationCategory
from project.responses import failure, success

from .serializers import NotificationCategorySerializer, NotificationSerializer


@api_view(['GET'])
def categories(request):
    categories = NotificationCategory.objects.all()
    serializer = NotificationCategorySerializer(categories, many=True)
    return success(request, serializer.data, message="Category successfully fetched")
    

@api_view(['GET'])
def notifications(request):
    category = request.query_params.get('category')

    if category:
        notifications = Notification.objects.filter(category__id=category).order_by('-created_at')
    else:
        notifications = Notification.objects.all().order_by('-created_at')
        
    serializer = NotificationSerializer(notifications, many=True)
    return success(request, serializer.data, message="Notifications successfully fetched")


@api_view(['POST', 'DELETE'])
@permission_classes([IsAuthenticated])
def devices(request):
    """Register (POST) or remove (DELETE) an FCM device token for the
    authenticated user. Used for targeted pushes such as chat messages."""
    token = request.data.get('token')
    if not token:
        return failure(request, "token is required", status.HTTP_400_BAD_REQUEST)

    if request.method == 'POST':
        platform = request.data.get('platform', 'android')
        if platform not in dict(DeviceToken.PLATFORM_CHOICES):
            platform = 'android'
        DeviceToken.objects.update_or_create(
            token=token,
            defaults={"user": request.user, "platform": platform}
        )
        return success(request, None, message="Device registered")

    DeviceToken.objects.filter(token=token, user=request.user).delete()
    return success(request, None, message="Device removed")
