"""
数据看板视图
"""
from rest_framework.decorators import api_view
from rest_framework.response import Response

from core.data_generator import SensorDataGenerator


@api_view(['GET'])
def overview(request):
    """获取看板概览数据"""
    # 生成实时数据
    realtime_data = SensorDataGenerator.generate_multi_sensors_realtime(count=5)

    # 计算统计数据
    sensors = realtime_data['sensors']
    avg_temp = sum(s['temperature'] for s in sensors) / len(sensors)
    avg_do = sum(s['dissolved_oxygen'] for s in sensors) / len(sensors)

    # 生成告警
    alerts = []
    for _ in range(3):
        alerts.append(SensorDataGenerator.generate_alert())

    return Response({
        'code': 200,
        'message': 'success',
        'data': {
            'timestamp': realtime_data['timestamp'],
            'summary': {
                'total_devices': 10,
                'online_devices': 9,
                'offline_devices': 1,
                'alert_count': 3,
                'avg_temperature': round(avg_temp, 1),
                'avg_dissolved_oxygen': round(avg_do, 1)
            },
            'sensors': sensors,
            'alerts': alerts
        }
    })
