from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from Videos.models import Video , VideoComment , VideoLike , VideoCommentLike
from .serializer import VideoSerializer , VideoCommentSerializer , VideoLikeSerializer
from rest_framework.permissions import AllowAny


@api_view(['GET'])
@permission_classes([AllowAny])
@permission_classes([IsAuthenticated])
def video_api(request):
    """
    Fetch all videos.
    """
    if request.method == 'GET':
        videos = Video.objects.all()
        serializer = VideoSerializer(videos, many=True, context={'request': request})
        return Response({"result" : "SUCCESS", "message" : "Videos fetched successfully!", "data" : serializer.data}, status=status.HTTP_200_OK)
       
    
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def comments_api(request, video_id):
    """
    Fetch all comments for a specific video.
    """
    if request.method == 'GET':
        videos = VideoComment.objects.filter(video__id=video_id, replay__isnull=True)
        serializer = VideoCommentSerializer(videos, many=True, context={'request': request})
        return Response({"result": "SUCCESS", "message": "Comments fetched successfully!", "data": serializer.data},status=status.HTTP_200_OK)
    
    elif request.method == 'POST':
        user = request.user  # Get the logged-in user
        try:
            video = Video.objects.get(id=video_id)  # Fetch the video object
        except Video.DoesNotExist:
            return Response({"result": "ERROR", "message": "Video not found!"}, status=status.HTTP_404_NOT_FOUND)

        # Merge user and video into request data
        data = request.data.copy()
        data['user'] = user.id  # Assign user ID
        data['video'] = video_id  # Assign video ID
        serializer = VideoCommentSerializer(data=data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(
                {"result": "SUCCESS", "message": "Comment added successfully!", "data": serializer.data},status=status.HTTP_201_CREATED)
        return Response(
            {"result": "ERROR", "message": "Invalid data!", "errors": serializer.errors},status=status.HTTP_400_BAD_REQUEST)
    


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def toggle_like(request, video_id):
    """
    Like / Unlike a video.
    """
    user = request.user

    try:
        video = Video.objects.get(id=video_id)  # Fix video lookup
    except Video.DoesNotExist:
        return Response(
            {"result": "ERROR", "message": "Video not found!"}, 
            status=status.HTTP_404_NOT_FOUND
        )

    # Check if the user has already liked the video
    like, created = VideoLike.objects.get_or_create(video=video, user=user)

    if created:
        video.add_like()  
        return Response(
            {"result": "SUCCESS", "message": "Like added successfully!"}, 
            status=status.HTTP_201_CREATED
        )
    else:
        like.delete()
        video.remove_like()  # Unlike the video
        return Response(
            {"result": "SUCCESS", "message": "Like removed successfully!"}, 
            status=status.HTTP_200_OK
        )


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def toogle_like_comment(request, comment_id):
    """
    Like / Unlike a comment.
    """
    user = request.user

    try:
        comment = VideoComment.objects.get(id=comment_id)  # Fix video lookup
    except VideoComment.DoesNotExist:
        return Response(
            {"result": "ERROR", "message": "Video not found!"}, 
            status=status.HTTP_404_NOT_FOUND
        )

    # Check if the user has already liked the video
    like, created = VideoCommentLike.objects.get_or_create(comment=comment, user=user)

    if created:
        comment.add_like()  
        return Response(
            {"result": "SUCCESS", "message": "Like added successfully!"}, 
            status=status.HTTP_201_CREATED
        )
    else:
        like.delete()
        comment.remove_like()  # Unlike the video
        return Response(
            {"result": "SUCCESS", "message": "Like removed successfully!"}, 
            status=status.HTTP_200_OK
        )
