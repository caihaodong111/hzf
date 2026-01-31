-- 智慧渔业水质监控系统 - 数据库初始化脚本

-- 创建数据库（如果不存在）
CREATE DATABASE IF NOT EXISTS aquaculture DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE aquaculture;

-- 设备表
CREATE TABLE IF NOT EXISTS devices (
    id INT AUTO_INCREMENT PRIMARY KEY,
    device_id VARCHAR(50) UNIQUE NOT NULL COMMENT '设备唯一标识',
    device_name VARCHAR(100) NOT NULL COMMENT '设备名称',
    device_type VARCHAR(20) NOT NULL COMMENT '设备类型: sensor-传感器, controller-控制器',
    location VARCHAR(200) COMMENT '设备位置',
    status VARCHAR(20) DEFAULT 'online' COMMENT '设备状态: online-在线, offline-离线, error-故障',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_device_type (device_type),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='设备表';

-- 传感器数据表
CREATE TABLE IF NOT EXISTS sensor_data (
    id INT AUTO_INCREMENT PRIMARY KEY,
    device_id VARCHAR(50) NOT NULL COMMENT '设备ID',
    temperature DECIMAL(4,1) COMMENT '水温(℃)',
    salinity DECIMAL(4,1) COMMENT '盐度(‰)',
    dissolved_oxygen DECIMAL(4,1) COMMENT '溶解氧(mg/L)',
    ph DECIMAL(3,1) COMMENT 'pH值',
    recorded_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '记录时间',
    INDEX idx_device_time (device_id, recorded_at),
    INDEX idx_recorded_at (recorded_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='传感器数据表';

-- 告警记录表
CREATE TABLE IF NOT EXISTS alerts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    device_id VARCHAR(50) NOT NULL COMMENT '设备ID',
    alert_type VARCHAR(50) NOT NULL COMMENT '告警类型',
    alert_level VARCHAR(20) NOT NULL COMMENT '告警级别: info-信息, warning-警告, critical-严重',
    message TEXT NOT NULL COMMENT '告警消息',
    value DECIMAL(10,2) COMMENT '触发值',
    resolved BOOLEAN DEFAULT FALSE COMMENT '是否已解决',
    resolved_at DATETIME NULL COMMENT '解决时间',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_device_resolved (device_id, resolved),
    INDEX idx_alert_level (alert_level),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='告警记录表';

-- 用户表（用于登录）
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL COMMENT '用户名',
    password VARCHAR(255) NOT NULL COMMENT '密码（加密）',
    email VARCHAR(100) COMMENT '邮箱',
    role VARCHAR(20) DEFAULT 'user' COMMENT '角色: admin-管理员, user-普通用户',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否激活',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    last_login DATETIME NULL COMMENT '最后登录时间',
    INDEX idx_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户表';

-- 插入初始设备数据
INSERT INTO devices (device_id, device_name, device_type, location, status) VALUES
('sensor_001', '1号池温度传感器', 'sensor', '1号养殖池', 'online'),
('sensor_002', '1号池综合传感器', 'sensor', '1号养殖池', 'online'),
('sensor_003', '2号池综合传感器', 'sensor', '2号养殖池', 'online'),
('sensor_004', '3号池综合传感器', 'sensor', '3号养殖池', 'online'),
('sensor_005', '4号池综合传感器', 'sensor', '4号养殖池', 'online'),
('controller_001', '1号池增氧机', 'controller', '1号养殖池', 'online'),
('controller_002', '2号池增氧机', 'controller', '2号养殖池', 'online'),
('controller_003', '3号池增氧机', 'controller', '3号养殖池', 'online'),
('controller_004', '4号池增氧机', 'controller', '4号养殖池', 'online');

-- 插入初始用户（密码: admin123，使用Django的PBKDF2加密）
-- 注意：这是示例密码哈希，实际使用时需要通过Django创建
INSERT INTO users (username, password, email, role) VALUES
('admin', 'pbkdf2_sha256$260000$abcdefghijklmnopqrstuvwxABCDEFGHIJKLMNOPQRSTUVWX$hash_placeholder', 'admin@example.com', 'admin'),
('demo', 'pbkdf2_sha256$260000$abcdefghijklmnopqrstuvwxABCDEFGHIJKLMNOPQRSTUVWX$hash_placeholder', 'demo@example.com', 'user');

-- 插入示例告警数据
INSERT INTO alerts (device_id, alert_type, alert_level, message, value, resolved) VALUES
('sensor_003', 'dissolved_oxygen', 'warning', '溶解氧偏低：4.8 mg/L', 4.8, FALSE),
('sensor_005', 'temperature', 'critical', '水温过高：33.5℃', 33.5, FALSE),
('sensor_002', 'ph', 'warning', 'pH值偏高：8.6', 8.6, TRUE);

-- 完成
SELECT 'Database initialized successfully!' AS status;
