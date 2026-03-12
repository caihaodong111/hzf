# 数据库表概览

基于 `python backend/manage.py inspectdb` 输出整理。字段类型为数据库层类型的 Django 映射。

## 业务数据

### alerts
- 告警表：告警类型/级别、消息、指标值、处理状态、来源与站点信息。
- 关键字段：`alert_type`、`alert_level`、`message`、`value`、`resolved`、`resolved_at`、`data_source`、`station_id`、`station_name`、`created_at`。

### sensor_data
- 实时原始传感器数据（带采集时间）。
- 关键字段：`station_id`、`station_name`、`recorded_at`、`data_source`、`temperature`、`ph`、`dissolved_oxygen`、`conductivity`、`turbidity`、`salinity`、`water_quality`、`permanganate`、`ammonia_nitrogen`、`total_phosphorus`、`total_nitrogen`、`chlorophyll_a`、`algae_density`。

### sensor_data_latest
- 实时最新快照表（每个站点+来源仅保留一条最新记录）。
- 关键字段：`station_id`、`station_name`、`recorded_at`、`updated_at`、`data_source`、`location`、`province`、`river_basin`、`city` + 与 `sensor_data` 类似的水质指标字段。
- 约束：`station_id` 唯一。
- 索引：`station_id`、`recorded_at`、`province`、`city`、`river_basin`。
- 写入方式：`sync_realtime_data` 管理命令或 `POST /api/v1/sensors/data/sync_realtime/` 手动触发。

### station_locations
- 站点/断面经纬度缓存表：避免同一 `station_name` 反复调用高德地理编码，并支撑前端地图标点。
- 关键字段：`station_id`（优先匹配，允许为空）、`station_name`、`province`、`city`、`longitude`、`latitude`、`source`、`updated_at`。
- 写入方式：`sync_realtime_data` 入库时自动补齐（命中缓存优先，缺失时调用高德并回写）；也可通过 `python manage.py geocode_station_locations` 批量补齐。

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
