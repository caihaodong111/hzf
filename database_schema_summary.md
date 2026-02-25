# 数据库表概览

基于 `python backend/manage.py inspectdb` 输出整理。字段类型为数据库层类型的 Django 映射。

## 业务数据

### alerts
- 告警表：告警类型/级别、消息、指标值、处理状态、来源与设备信息。
- 关键字段：`alert_type`、`alert_level`、`message`、`value`、`resolved`、`resolved_at`、`data_source`、`device_id`、`device_name`、`created_at`。

### sensor_data
- 实时原始传感器数据（带采集时间）。
- 关键字段：`device_id`、`device_name`、`recorded_at`、`data_source`、`temperature`、`ph`、`dissolved_oxygen`、`conductivity`、`turbidity`、`salinity`、`water_quality`、`permanganate`、`ammonia_nitrogen`、`total_phosphorus`、`total_nitrogen`、`chlorophyll_a`、`algae_density`。

### sensor_data_snapshot
- 实时数据快照（定时落库，用于看板/历史回放）。
- 关键字段：`device_id`、`device_name`、`snapshot_time`、`data_source`、`location`、`province`、`river_basin`、`city` + 与 `sensor_data` 类似的水质指标字段。
- 约束：`device_id` + `snapshot_time` 唯一。
- 索引：`device_id`、`snapshot_time`、`data_source`、`province`、`city`、`river_basin`、`device_name`、`location`、`water_quality`。

### sensor_data_realtime
- 实时最新数据表（每个设备+数据源仅保留一条最新记录）。
- 关键字段：`device_id`、`data_source`、`recorded_at`、`updated_at`、`device_name`、`location`、`province`、`city`、`river_basin` + 与 `sensor_data` 类似的水质指标字段。
- 约束：`device_id` + `data_source` 唯一。
- 索引：`device_id`+`data_source`、`recorded_at`、`province`、`city`、`river_basin`、`water_quality`。
- 写入方式：`sync_realtime_data` 管理命令或 `POST /api/v1/sensors/data/sync_realtime/` 手动触发。

### dashboard_datasourcepreference
- 数据源偏好设置（自动/手动）。
- 关键字段：`mode`、`updated_at`。

### water_quality_measurements
- 旧版或兼容表：水质测量记录（站点维度）。
- 关键字段：`station_id`、`station_name`、`measured_at`、`ingested_at`、`source`、`quality_grade` + 水质指标字段。

### water_quality_snapshots
- 旧版或兼容表：水质快照（站点维度）。
- 关键字段：`station_id`、`station_name`、`snapshot_at`、`ingested_at`、`source`、`province`、`river_basin`、`city` + 水质指标字段。
- 约束：`station_id` + `snapshot_at` 唯一。

### water_quality_alerts
- 旧版或兼容表：水质告警（站点维度）。
- 关键字段：`alert_type`、`alert_level`、`message`、`value`、`resolved`、`source`、`station_id`、`station_name`、`created_at`。

## Django 系统表

### auth_group / auth_permission / auth_group_permissions
- 权限与用户组的基础表。

### auth_user / auth_user_groups / auth_user_user_permissions
- 用户账号与权限关系表。

### authtoken_token
- DRF Token 认证表，`key` 为主键。

### django_admin_log
- 管理后台操作日志。

### django_content_type
- Django ContentType 元数据。

### django_migrations
- 迁移历史。

### django_session
- 会话存储表。

## Celery Beat 调度相关

### django_celery_beat_clockedschedule / intervalschedule / crontabschedule / solarschedule
- 定时策略表。

### django_celery_beat_periodictask / periodictasks
- 周期任务定义与更新时间戳。
