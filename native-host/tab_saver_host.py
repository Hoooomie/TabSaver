#!/usr/bin/env python3
"""
TabSaver - Native Messaging Host
Chrome扩展通过stdin/stdout与本脚本通信，将标签页数据持久化到本地JSON文件。

通信协议：
- 输入：4字节(小端uint32)消息长度 + JSON消息体
- 输出：4字节(小端uint32)响应长度 + JSON响应体

消息格式：
{
    "action": "sync",
    "timestamp": "2026-05-17T10:40:26+08:00",
    "tabCount": 5,
    "tabs": [{"url": "...", "title": "...", "favIconUrl": "..."}]
}
"""

import sys
import json
import struct
import os
from datetime import datetime
from pathlib import Path

# 数据存储路径
DATA_DIR = Path(os.environ.get('APPDATA', Path.home() / 'AppData' / 'Roaming')) / 'TabSaver' / 'data'
SESSIONS_FILE = DATA_DIR / 'sessions.json'

# 当前活跃会话ID（Chrome打开期间持续更新同一个会话）
current_session_id = None
last_save_time = None


def ensure_data_dir():
    """确保数据目录存在"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_sessions():
    """从JSON文件加载会话数据"""
    if SESSIONS_FILE.exists():
        try:
            with open(SESSIONS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if 'sessions' in data and isinstance(data['sessions'], list):
                    return data
        except (json.JSONDecodeError, IOError):
            pass
    return {"sessions": []}


def save_sessions(data):
    """保存会话数据到JSON文件"""
    ensure_data_dir()
    # 原子写入：先写临时文件再重命名
    temp_file = SESSIONS_FILE.with_suffix('.tmp')
    with open(temp_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    # Windows上rename可能失败，直接覆盖
    try:
        temp_file.replace(SESSIONS_FILE)
    except OSError:
        # fallback
        if SESSIONS_FILE.exists():
            SESSIONS_FILE.unlink()
        temp_file.rename(SESSIONS_FILE)


def generate_session_id(timestamp_str):
    """根据时间戳生成会话ID"""
    try:
        dt = datetime.fromisoformat(timestamp_str)
    except (ValueError, TypeError):
        dt = datetime.now()
    return dt.strftime('%Y%m%d_%H%M%S')


def update_or_create_session(message):
    """更新当前活跃会话或创建新会话"""
    global current_session_id, last_save_time

    data = load_sessions()
    tabs = message.get('tabs', [])
    timestamp = message.get('timestamp', datetime.now().isoformat())
    tab_count = message.get('tabCount', len(tabs))

    session_id = generate_session_id(timestamp)

    # 如果距离上次保存不到5分钟，视为同一个会话（更新而非新建）
    now = datetime.now()
    should_create_new = True

    if current_session_id and last_save_time:
        elapsed = (now - last_save_time).total_seconds()
        if elapsed < 300:  # 5分钟内视为同一会话
            should_create_new = False
            session_id = current_session_id

    if should_create_new:
        # 创建新会话
        session = {
            "id": session_id,
            "timestamp": timestamp,
            "tabCount": tab_count,
            "tabs": tabs
        }
        data['sessions'].append(session)
        current_session_id = session_id
    else:
        # 更新现有会话
        found = False
        for session in data['sessions']:
            if session['id'] == current_session_id:
                session['timestamp'] = timestamp
                session['tabCount'] = tab_count
                session['tabs'] = tabs
                found = True
                break

        if not found:
            # 当前会话ID未找到，创建新的
            session = {
                "id": session_id,
                "timestamp": timestamp,
                "tabCount": tab_count,
                "tabs": tabs
            }
            data['sessions'].append(session)
            current_session_id = session_id

    # 最多保留100个会话
    if len(data['sessions']) > 100:
        data['sessions'] = data['sessions'][-100:]

    save_sessions(data)
    last_save_time = now

    return session_id


def read_message():
    """从stdin读取Chrome消息（4字节长度 + JSON）"""
    raw_length = sys.stdin.buffer.read(4)
    if len(raw_length) == 0:
        return None
    if len(raw_length) < 4:
        return None
    message_length = struct.unpack('=I', raw_length)[0]
    if message_length == 0:
        return None
    message_data = sys.stdin.buffer.read(message_length)
    if len(message_data) < message_length:
        return None
    return json.loads(message_data.decode('utf-8'))


def send_response(response):
    """向stdout发送响应（4字节长度 + JSON）"""
    response_data = json.dumps(response).encode('utf-8')
    sys.stdout.buffer.write(struct.pack('=I', len(response_data)))
    sys.stdout.buffer.write(response_data)
    sys.stdout.buffer.flush()


def main():
    """主循环：持续读取Chrome消息"""
    ensure_data_dir()

    while True:
        try:
            message = read_message()
            if message is None:
                # stdin关闭，Chrome已退出
                break

            action = message.get('action', '')

            if action == 'sync':
                session_id = update_or_create_session(message)
                send_response({
                    "status": "ok",
                    "sessionId": session_id,
                    "savedTabs": message.get('tabCount', 0)
                })
            elif action == 'ping':
                send_response({"status": "pong"})
            else:
                send_response({"status": "unknown_action", "action": action})

        except Exception as e:
            try:
                send_response({"status": "error", "message": str(e)})
            except Exception:
                break
            break

    # Chrome关闭后的最终处理：当前会话已经保存，无需额外操作
    # 但确保当前会话标记为"已完成"（下次Chrome打开会创建新会话）


if __name__ == '__main__':
    main()
