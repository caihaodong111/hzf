-- 智慧渔业水质监控系统 - 数据库初始化脚本

-- 创建数据库（如果不存在）
CREATE DATABASE IF NOT EXISTS aquaculture DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE aquaculture;

-- 传感器数据表
CREATE TABLE IF NOT EXISTS sensor_data (
    id INT AUTO_INCREMENT PRIMARY KEY,
    station_id VARCHAR(50) NOT NULL COMMENT '站点ID',
    temperature DECIMAL(4,1) COMMENT '水温(℃)',
    salinity DECIMAL(4,1) COMMENT '盐度(‰)',
    dissolved_oxygen DECIMAL(4,1) COMMENT '溶解氧(mg/L)',
    ph DECIMAL(3,1) COMMENT 'pH值',
    recorded_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '记录时间',
    INDEX idx_station_time (station_id, recorded_at),
    INDEX idx_recorded_at (recorded_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='传感器数据表';

-- 告警记录表
CREATE TABLE IF NOT EXISTS alerts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    station_id VARCHAR(50) NOT NULL COMMENT '站点ID',
    alert_type VARCHAR(50) NOT NULL COMMENT '告警类型',
    alert_level VARCHAR(20) NOT NULL COMMENT '告警级别: info-信息, warning-警告, critical-严重',
    message TEXT NOT NULL COMMENT '告警消息',
    value DECIMAL(10,2) COMMENT '触发值',
    resolved BOOLEAN DEFAULT FALSE COMMENT '是否已解决',
    resolved_at DATETIME NULL COMMENT '解决时间',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_station_resolved (station_id, resolved),
    INDEX idx_alert_level (alert_level),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='告警记录表';


-- 插入示例告警数据
INSERT INTO alerts (station_id, alert_type, alert_level, message, value, resolved) VALUES
('station_003', 'dissolved_oxygen', 'warning', '溶解氧偏低：4.8 mg/L', 4.8, FALSE),
('station_005', 'temperature', 'critical', '水温过高：33.5℃', 33.5, FALSE),
('station_002', 'ph', 'warning', 'pH值偏高：8.6', 8.6, TRUE);

-- 完成
SELECT 'Database initialized successfully!' AS status;
