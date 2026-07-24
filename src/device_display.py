"""
设备显示模块 — .film 文件管理、版本控制、manifest 生成

跨端契约：
- POST /api/devices/{device_id}/display       → upload_film()
- GET  /api/devices/{device_id}/display/manifest → get_manifest()
- GET  /api/devices/{device_id}/display/{version}.film → download_film()
- GET  /api/devices/{device_id}/sync-status    → get_sync_status()
"""

import os
import hashlib
import sqlite3
from datetime import datetime
from pathlib import Path

from .logger import get_logger
logger = get_logger('device_display')

# .film 文件存储路径
FILM_STORAGE = os.path.join(os.path.dirname(__file__), '..', 'data', 'devices')

# FrameFilm Pro 规格
FILM_SIZE_PRO = 209120  # 528×792 六色
FILM_HEADER_SIZE = 32


def get_connection():
    """获取数据库连接"""
    from .database import get_connection as _get_conn
    return _get_conn()


def init_device_tables():
    """初始化设备相关表"""
    conn = get_connection()
    cursor = conn.cursor()

    # 设备表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL UNIQUE,
            device_name TEXT DEFAULT '',
            device_token TEXT,
            wifi_enabled INTEGER DEFAULT 0,
            last_seen TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 设备显示版本表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS device_display (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL,
            version INTEGER NOT NULL,
            file_path TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            sha256 TEXT NOT NULL,
            uploaded_by TEXT DEFAULT 'android',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(device_id, version)
        )
    ''')

    # 设备同步状态表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS device_sync_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            version INTEGER,
            detail TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 索引
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_display_device_version
        ON device_display(device_id, version DESC)
    ''')

    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_sync_log_device
        ON device_sync_log(device_id, created_at DESC)
    ''')

    conn.commit()
    conn.close()
    logger.info("Device display tables initialized")


def _ensure_device_dir(device_id: str) -> str:
    """确保设备目录存在"""
    device_dir = os.path.join(FILM_STORAGE, device_id)
    os.makedirs(device_dir, exist_ok=True)
    return device_dir


def _calc_sha256(file_path: str) -> str:
    """计算文件 SHA-256"""
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return sha256.hexdigest()


def _validate_film_header(data: bytes) -> tuple:
    """
    验证 .film 文件头
    返回: (is_valid, error_message)
    """
    if len(data) < FILM_HEADER_SIZE:
        return False, f"文件过小: {len(data)} < {FILM_HEADER_SIZE}"

    # 检查像素数据长度（偏移 0-3，小端 uint32）
    pixel_len = int.from_bytes(data[0:4], 'little')

    # FrameFilm Pro: 像素数据 209088 字节 + 文件头 32 字节 = 209120
    if len(data) != FILM_SIZE_PRO:
        return False, f"文件长度错误: {len(data)} != {FILM_SIZE_PRO} (Pro规格)"

    if pixel_len != FILM_SIZE_PRO - FILM_HEADER_SIZE:
        return False, f"像素数据长度错误: {pixel_len} != {FILM_SIZE_PRO - FILM_HEADER_SIZE}"

    return True, ""


def upload_film(device_id: str, film_data: bytes, uploaded_by: str = 'android') -> dict:
    """
    上传 .film 文件

    Args:
        device_id: 设备 ID
        film_data: .film 文件二进制数据
        uploaded_by: 上传来源 ('android' / 'manual')

    Returns:
        {"success": True, "version": 17, ...} 或 {"success": False, "error": "..."}
    """
    # 验证文件大小
    if len(film_data) != FILM_SIZE_PRO:
        return {
            "success": False,
            "error": f"文件大小错误: {len(film_data)} != {FILM_SIZE_PRO}"
        }

    # 验证文件头
    is_valid, error_msg = _validate_film_header(film_data)
    if not is_valid:
        return {"success": False, "error": f"文件头验证失败: {error_msg}"}

    # 计算 SHA-256
    sha256 = hashlib.sha256(film_data).hexdigest()

    conn = get_connection()
    cursor = conn.cursor()

    try:
        # 确保设备存在
        cursor.execute(
            'INSERT OR IGNORE INTO devices (device_id, last_seen) VALUES (?, ?)',
            (device_id, datetime.now().isoformat())
        )
        cursor.execute(
            'UPDATE devices SET last_seen = ? WHERE device_id = ?',
            (datetime.now().isoformat(), device_id)
        )

        # 获取当前最大版本号
        cursor.execute(
            'SELECT MAX(version) FROM device_display WHERE device_id = ?',
            (device_id,)
        )
        row = cursor.fetchone()
        current_version = row[0] if row[0] else 0
        new_version = current_version + 1

        # 保存文件
        device_dir = _ensure_device_dir(device_id)
        file_name = f"{new_version}.film"
        file_path = os.path.join(device_dir, file_name)

        with open(file_path, 'wb') as f:
            f.write(film_data)

        # 记录版本
        cursor.execute('''
            INSERT INTO device_display (device_id, version, file_path, file_size, sha256, uploaded_by)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (device_id, new_version, file_path, len(film_data), sha256, uploaded_by))

        # 记录同步日志
        cursor.execute('''
            INSERT INTO device_sync_log (device_id, event_type, version, detail)
            VALUES (?, ?, ?, ?)
        ''', (device_id, 'upload', new_version, f"uploaded by {uploaded_by}, sha256={sha256[:16]}..."))

        conn.commit()

        logger.info(f"Film uploaded: device={device_id}, version={new_version}, sha256={sha256[:16]}...")

        return {
            "success": True,
            "version": new_version,
            "size": len(film_data),
            "sha256": sha256,
            "device_id": device_id
        }

    except Exception as e:
        conn.rollback()
        logger.error(f"Upload failed: {e}")
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def get_manifest(device_id: str) -> dict:
    """
    获取设备 manifest（ESP32 调用）

    Returns:
        {"version": 17, "film_url": "...", "size": 209120, "sha256": "...", "force": false}
        或 None（无版本）
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('''
            SELECT version, file_size, sha256
            FROM device_display
            WHERE device_id = ?
            ORDER BY version DESC
            LIMIT 1
        ''', (device_id,))

        row = cursor.fetchone()
        if not row:
            return None

        version, file_size, sha256 = row

        # 记录查询日志
        cursor.execute('''
            INSERT INTO device_sync_log (device_id, event_type, version, detail)
            VALUES (?, ?, ?, ?)
        ''', (device_id, 'manifest_query', version, f"manifest requested"))

        conn.commit()

        # 构建 manifest
        base_url = os.environ.get('SFM_BASE_URL', 'http://localhost:5000')
        manifest = {
            "version": version,
            "film_url": f"{base_url}/api/devices/{device_id}/display/{version}.film",
            "size": file_size,
            "sha256": sha256,
            "force": False
        }

        logger.info(f"Manifest: device={device_id}, version={version}")
        return manifest

    finally:
        conn.close()


def download_film(device_id: str, version: int) -> tuple:
    """
    下载 .film 文件

    Returns:
        (file_path, file_size, sha256) 或 None
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('''
            SELECT file_path, file_size, sha256
            FROM device_display
            WHERE device_id = ? AND version = ?
        ''', (device_id, version))

        row = cursor.fetchone()
        if not row:
            return None

        file_path, file_size, sha256 = row

        if not os.path.exists(file_path):
            logger.error(f"Film file missing: {file_path}")
            return None

        # 记录下载日志
        cursor.execute('''
            INSERT INTO device_sync_log (device_id, event_type, version, detail)
            VALUES (?, ?, ?, ?)
        ''', (device_id, 'download', version, f"film downloaded"))

        conn.commit()

        logger.info(f"Film download: device={device_id}, version={version}")
        return (file_path, file_size, sha256)

    finally:
        conn.close()


def get_sync_status(device_id: str) -> dict:
    """
    获取设备同步状态

    Returns:
        {
            "device_id": "xxx",
            "latest_version": 17,
            "latest_upload_time": "2026-07-23T10:00:00",
            "latest_sha256": "...",
            "last_manifest_query": "2026-07-23T10:05:00",
            "recent_events": [...]
        }
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # 获取最新版本
        cursor.execute('''
            SELECT version, sha256, created_at
            FROM device_display
            WHERE device_id = ?
            ORDER BY version DESC
            LIMIT 1
        ''', (device_id,))

        latest = cursor.fetchone()
        if not latest:
            return {
                "device_id": device_id,
                "latest_version": 0,
                "latest_upload_time": None,
                "latest_sha256": None,
                "last_manifest_query": None,
                "recent_events": []
            }

        latest_version, latest_sha256, latest_time = latest

        # 获取最近 manifest 查询时间
        cursor.execute('''
            SELECT created_at
            FROM device_sync_log
            WHERE device_id = ? AND event_type = 'manifest_query'
            ORDER BY created_at DESC
            LIMIT 1
        ''', (device_id,))

        manifest_row = cursor.fetchone()
        last_manifest_query = manifest_row[0] if manifest_row else None

        # 获取最近事件
        cursor.execute('''
            SELECT event_type, version, detail, created_at
            FROM device_sync_log
            WHERE device_id = ?
            ORDER BY created_at DESC
            LIMIT 20
        ''', (device_id,))

        events = []
        for row in cursor.fetchall():
            events.append({
                "event": row[0],
                "version": row[1],
                "detail": row[2],
                "time": row[3]
            })

        return {
            "device_id": device_id,
            "latest_version": latest_version,
            "latest_upload_time": latest_time,
            "latest_sha256": latest_sha256,
            "last_manifest_query": last_manifest_query,
            "recent_events": events
        }

    finally:
        conn.close()


def list_devices() -> list:
    """列出所有设备"""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('''
            SELECT d.device_id, d.device_name, d.last_seen,
                   MAX(dd.version) as latest_version
            FROM devices d
            LEFT JOIN device_display dd ON d.device_id = dd.device_id
            GROUP BY d.device_id
            ORDER BY d.last_seen DESC
        ''')

        devices = []
        for row in cursor.fetchall():
            devices.append({
                "device_id": row[0],
                "device_name": row[1],
                "last_seen": row[2],
                "latest_version": row[3] or 0
            })

        return devices

    finally:
        conn.close()


# 初始化时创建表
init_device_tables()
