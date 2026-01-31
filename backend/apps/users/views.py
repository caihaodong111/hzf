from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django.contrib.auth import logout
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token

from .serializers import (
    LoginResponseSerializer,
    UserSerializer,
    RegisterSerializer
)


@api_view(['POST'])
@permission_classes([AllowAny])
@authentication_classes([])  # 禁用所有认证，避免CSRF问题
def login_view(request):
    """
    用户登录 - 简化版，只需要账号密码
    POST /api/v1/users/login/
    {
        "username": "admin",
        "password": "password123"
    }
    """
    username = request.data.get('username')
    password = request.data.get('password')

    # 简单验证
    if not username or not password:
        return Response({
            'success': False,
            'message': '请提供用户名和密码',
            'data': None
        }, status=status.HTTP_400_BAD_REQUEST)

    # 直接使用数据库验证用户
    try:
        user = User.objects.get(username=username)
        # 验证密码
        if user.check_password(password):
            # 获取或创建 token
            token, created = Token.objects.get_or_create(user=user)

            # 序列化响应
            response_data = {
                'token': token.key,
                'user': UserSerializer(user).data
            }
            response_serializer = LoginResponseSerializer(response_data)

            return Response({
                'success': True,
                'message': '登录成功',
                'data': response_serializer.data
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'success': False,
                'message': '用户名或密码错误',
                'data': None
            }, status=status.HTTP_401_UNAUTHORIZED)
    except User.DoesNotExist:
        return Response({
            'success': False,
            'message': '用户名或密码错误',
            'data': None
        }, status=status.HTTP_401_UNAUTHORIZED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """
    用户登出
    POST /api/v1/users/logout/
    Authorization: Token <token>
    """
    try:
        # 删除 token
        request.user.auth_token.delete()
        # 登出 session
        logout(request)

        return Response({
            'success': True,
            'message': '登出成功',
            'data': None
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({
            'success': False,
            'message': f'登出失败: {str(e)}',
            'data': None
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_profile(request):
    """
    获取当前用户信息
    GET /api/v1/users/profile/
    Authorization: Token <token>
    """
    serializer = UserSerializer(request.user)
    return Response({
        'success': True,
        'message': '获取用户信息成功',
        'data': serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])
@authentication_classes([])
def register_view(request):
    """
    用户注册
    POST /api/v1/users/register/
    {
        "username": "newuser",
        "password": "password123",
        "password_confirm": "password123",
        "email": "user@example.com"
    }
    """
    serializer = RegisterSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        # 获取创建的 token
        token = Token.objects.get(user=user)

        response_data = {
            'token': token.key,
            'user': UserSerializer(user).data
        }
        response_serializer = LoginResponseSerializer(response_data)

        return Response({
            'success': True,
            'message': '注册成功',
            'data': response_serializer.data
        }, status=status.HTTP_201_CREATED)

    return Response({
        'success': False,
        'message': '注册失败',
        'data': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)
