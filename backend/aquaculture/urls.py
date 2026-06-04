"""
URL configuration for aquaculture project.
"""
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from apps.sensors.views import device_ingest_gateway

# API文档配置 (暂时禁用drf_yasg)
# from rest_framework import permissions
# from drf_yasg.views import get_schema_view
# from drf_yasg import openapi
#
# schema_view = get_schema_view(
#     openapi.Info(
#         title="智慧渔业水质监控系统 API",
#         default_version='v1',
#         description="提供水质监测数据查询、设备管理、预警系统等接口",
#         terms_of_service="https://www.example.com/terms/",
#         contact=openapi.Contact(email="admin@example.com"),
#         license=openapi.License(name="MIT License"),
#     ),
#     public=True,
#     permission_classes=[permissions.AllowAny],
# )

urlpatterns = [
    path('sensor', device_ingest_gateway, name='sensor-gateway'),
    path('sensor/', device_ingest_gateway, name='sensor-gateway-slash'),
    # API v1
    path('api/v1/sensors/', include('apps.sensors.urls')),
    path('api/v1/alerts/', include('apps.alerts.urls')),
    path('api/v1/dashboard/', include('apps.dashboard.urls')),

    # API文档 (暂时禁用)
    # path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    # path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]

# 开发环境下提供静态文件服务
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
