from rest_framework import serializers
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token


class UserSerializer(serializers.ModelSerializer):
    """用户序列化器"""

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']
        read_only_fields = ['id']


class LoginSerializer(serializers.Serializer):
    """登录序列化器"""
    username = serializers.CharField(required=True, error_messages={'required': '用户名不能为空'})
    password = serializers.CharField(required=True, error_messages={'required': '密码不能为空'}, style={'input_type': 'password'})


class LoginResponseSerializer(serializers.Serializer):
    """登录响应序列化器"""
    token = serializers.CharField()
    user = UserSerializer()


class RegisterSerializer(serializers.ModelSerializer):
    """注册序列化器"""
    password = serializers.CharField(required=True, min_length=6, error_messages={
        'required': '密码不能为空',
        'min_length': '密码长度不能少于6位'
    }, style={'input_type': 'password'})
    password_confirm = serializers.CharField(required=True, error_messages={'required': '请确认密码'}, style={'input_type': 'password'})

    class Meta:
        model = User
        fields = ['username', 'password', 'password_confirm', 'email', 'first_name', 'last_name']
        extra_kwargs = {
            'username': {'error_messages': {'required': '用户名不能为空'}},
        }

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({'password_confirm': '两次输入的密码不一致'})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        user = User.objects.create_user(**validated_data)
        user.set_password(password)
        user.save()
        # 为用户创建 token
        Token.objects.get_or_create(user=user)
        return user
