from django.urls import path
from django.views.decorators.csrf import csrf_exempt
from . import views

app_name = 'users'

urlpatterns = [
    # 登录/登出 - 豁免 CSRF
    path('login/', csrf_exempt(views.login_view), name='login'),
    path('logout/', csrf_exempt(views.logout_view), name='logout'),

    # 用户信息
    path('profile/', views.user_profile, name='profile'),

    # 注册 - 豁免 CSRF
    path('register/', csrf_exempt(views.register_view), name='register'),
]
