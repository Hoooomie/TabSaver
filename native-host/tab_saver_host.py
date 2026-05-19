#!/usr/bin/env python3
"""
TabSaver - Native Messaging Host
Chrome扩展通过stdin/stdout与本脚本通信，将标签页数据持久化到本地JSON文件。

通信协议：
- 输入：4字节(小端uint32)消息长度 + JSON消息体
- 输出：4字节(小端uint32)响应长度 + JSON响应体

消息格式：
{
    "action": "sync" | "heartbeat" | "ping" | "track_flush" | "track_report",
    "timestamp": "2026-05-17T10:40:26+08:00",
    "tabCount": 5,
    "tabs": [{"url": "...", "title": "...", "favIconUrl": "..."}]
}

TabTracker 追踪功能：
- track_flush: 接收活跃段数据，按日期写入 activity_YYYY-MM-DD.json
- track_report: 根据日期范围聚合活动数据，返回报告JSON

配置参数 (config.json):
- mode: "auto" | "manual"，默认 "auto"
- max_sessions: 最大保存会话数，默认100
- threshold: 至少打开多少个标签页时才保存，默认1

手动保存机制：
1. Native Host 每次收到 sync 都将标签页写入 latest_tabs.json
2. 桌面端手动保存时直接读取 latest_tabs.json，写入 sessions.json
3. 无需信号文件和心跳轮询，零延迟
"""

import sys
import json
import struct
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import defaultdict

# 数据存储路径
DATA_DIR = Path(os.environ.get('APPDATA', Path.home() / 'AppData' / 'Roaming')) / 'TabSaver' / 'data'
SESSIONS_FILE = DATA_DIR / 'sessions.json'
CONFIG_FILE = DATA_DIR / 'config.json'
LATEST_TABS_FILE = DATA_DIR / 'latest_tabs.json'
ACTIVITY_DIR = DATA_DIR / 'activity'

# 默认配置
DEFAULT_CONFIG = {
    "mode": "auto",
    "max_sessions": 100,
    "threshold": 1
}

# 当前活跃会话ID（Chrome打开期间持续更新同一个会话）
current_session_id = None
last_save_time = None


def load_config():
    """加载配置文件，如果不存在则使用默认值"""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
                config = dict(DEFAULT_CONFIG)
                config.update({k: v for k, v in cfg.items() if k in DEFAULT_CONFIG})
                return config
        except (json.JSONDecodeError, IOError):
            pass
    return dict(DEFAULT_CONFIG)


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
    temp_file = SESSIONS_FILE.with_suffix('.tmp')
    with open(temp_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    try:
        temp_file.replace(SESSIONS_FILE)
    except OSError:
        if SESSIONS_FILE.exists():
            SESSIONS_FILE.unlink()
        temp_file.rename(SESSIONS_FILE)


def write_latest_tabs(message):
    """
    将最新标签页数据写入 latest_tabs.json，供桌面端读取。
    无论什么模式，每次收到 sync 都写入，确保桌面端能获取当前标签页。
    """
    ensure_data_dir()
    data = {
        "timestamp": message.get('timestamp', datetime.now().isoformat()),
        "tabCount": message.get('tabCount', 0),
        "tabs": message.get('tabs', [])
    }
    temp_file = LATEST_TABS_FILE.with_suffix('.tmp')
    with open(temp_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    try:
        temp_file.replace(LATEST_TABS_FILE)
    except OSError:
        if LATEST_TABS_FILE.exists():
            LATEST_TABS_FILE.unlink()
        temp_file.rename(LATEST_TABS_FILE)


def generate_session_id(timestamp_str=None):
    """
    根据当前时间生成唯一会话ID，包含毫秒精度。
    格式：YYYYMMDD_HHMMSS_mmm（mmm为毫秒）
    """
    now = datetime.now()
    if timestamp_str:
        try:
            dt = datetime.fromisoformat(timestamp_str)
            if dt.tzinfo is not None:
                dt = dt.astimezone()
            now = dt
        except (ValueError, TypeError):
            pass
    return now.strftime('%Y%m%d_%H%M%S_') + f'{now.microsecond // 1000:03d}'


def is_duplicate_session(tabs, existing_sessions, exclude_session_id=None):
    """
    检查当前标签页集合是否与已有会话重复。
    比较逻辑：将所有URL组成集合，如果与某个已有会话的URL集合完全一致，则视为重复。
    """
    current_urls = frozenset(tab.get('url', '') for tab in tabs)
    if not current_urls:
        return False

    for session in existing_sessions:
        if exclude_session_id and session.get('id') == exclude_session_id:
            continue
        session_urls = frozenset(tab.get('url', '') for tab in session.get('tabs', []))
        if current_urls == session_urls:
            return True

    return False


def update_or_create_session(message, force=False):
    """
    更新当前活跃会话或创建新会话。

    force=True 时跳过去重检查和threshold检查，总是创建新会话。
    """
    global current_session_id, last_save_time

    config = load_config()
    max_sessions = config.get('max_sessions', DEFAULT_CONFIG['max_sessions'])
    threshold = config.get('threshold', DEFAULT_CONFIG['threshold'])

    data = load_sessions()
    tabs = message.get('tabs', [])
    timestamp = message.get('timestamp', datetime.now().isoformat())
    tab_count = message.get('tabCount', len(tabs))

    # 检查threshold（手动强制保存时跳过）
    if not force and tab_count < threshold:
        return current_session_id or "skipped_threshold"

    if force:
        # ===== 手动强制保存：总是创建新会话，不更新现有会话 =====
        session_id = generate_session_id(timestamp)
        session = {
            "id": session_id,
            "timestamp": timestamp,
            "tabCount": tab_count,
            "tabs": tabs
        }
        data['sessions'].append(session)
        # 保存后重置，确保后续自动同步不会覆盖此会话
        current_session_id = None
        last_save_time = None
    else:
        # ===== 自动保存：可能更新现有会话 =====
        session_id = generate_session_id(timestamp)
        now = datetime.now()
        should_create_new = True

        if current_session_id and last_save_time:
            elapsed = (now - last_save_time).total_seconds()
            if elapsed < 300:  # 5分钟内视为同一会话
                should_create_new = False
                session_id = current_session_id

        if should_create_new:
            # 去重检查
            if is_duplicate_session(tabs, data['sessions']):
                return current_session_id or "skipped_duplicate"

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
                if is_duplicate_session(tabs, data['sessions']):
                    return current_session_id or "skipped_duplicate"

                session = {
                    "id": session_id,
                    "timestamp": timestamp,
                    "tabCount": tab_count,
                    "tabs": tabs
                }
                data['sessions'].append(session)
                current_session_id = session_id

        last_save_time = now

    # 最多保留max_sessions个会话
    if len(data['sessions']) > max_sessions:
        data['sessions'] = data['sessions'][-max_sessions:]

    save_sessions(data)
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


def handle_sync(message):
    """处理 sync 动作：无论模式，都写入latest_tabs.json；仅自动模式才保存到sessions.json"""
    config = load_config()
    mode = config.get('mode', DEFAULT_CONFIG['mode'])

    # 无论什么模式，都将标签页写入 latest_tabs.json 供桌面端读取
    write_latest_tabs(message)

    if mode == "auto":
        # 自动模式 → 保存到 sessions.json
        session_id = update_or_create_session(message)
        return {
            "status": "ok",
            "sessionId": session_id,
            "savedTabs": message.get('tabCount', 0),
            "mode": mode
        }
    else:
        # 手动模式 → 不自动保存，仅缓存
        return {
            "status": "ok",
            "sessionId": None,
            "savedTabs": 0,
            "mode": "manual",
            "message": "Manual mode: tabs cached but not saved"
        }


def handle_heartbeat():
    """处理 heartbeat 动作：返回当前状态（保留用于扩展状态检查）"""
    config = load_config()
    return {
        "status": "ok",
        "mode": config.get('mode', DEFAULT_CONFIG['mode'])
    }


# ========== TabTracker 活动追踪功能 ==========

def _get_local_tz():
    """获取本地时区偏移（北京时间 UTC+8）"""
    return timezone(timedelta(hours=8))


def _timestamp_to_date(ts_ms):
    """将毫秒时间戳转换为本地日期字符串 YYYY-MM-DD"""
    tz = _get_local_tz()
    dt = datetime.fromtimestamp(ts_ms / 1000, tz=tz)
    return dt.strftime('%Y-%m-%d')


def _compute_daily_summary(segments):
    """从段数据计算每日摘要"""
    total_active_ms = sum(s.get('duration', 0) for s in segments)
    domain_ms = defaultdict(int)
    hourly_buckets = [0] * 24
    category_ms = defaultdict(int)

    tz = _get_local_tz()

    for seg in segments:
        domain = seg.get('domain', 'unknown')
        duration = seg.get('duration', 0)
        category = seg.get('category', 'Other')

        # 域名统计
        domain_ms[domain] += duration

        # 按小时统计
        start_dt = datetime.fromtimestamp(seg.get('startTime', 0) / 1000, tz=tz)
        # 将段的时长分配到各小时（简单方案：全部分配到开始小时）
        hour = start_dt.hour
        hourly_buckets[hour] += duration

        # 分类统计
        category_ms[category] += duration

    # 排序 top 域名
    top_domains = sorted(domain_ms.items(), key=lambda x: x[1], reverse=True)[:20]
    top_categories = sorted(category_ms.items(), key=lambda x: x[1], reverse=True)

    return {
        "totalActiveMs": total_active_ms,
        "segmentCount": len(segments),
        "topDomains": [{"domain": d, "ms": ms} for d, ms in top_domains],
        "topCategories": [{"category": c, "ms": ms} for c, ms in top_categories],
        "hourlyBuckets": hourly_buckets
    }


def _load_activity_file(date_str):
    """加载指定日期的活动文件"""
    activity_file = ACTIVITY_DIR / f'activity_{date_str}.json'
    if activity_file.exists():
        try:
            with open(activity_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if 'segments' in data and isinstance(data['segments'], list):
                    return data
        except (json.JSONDecodeError, IOError):
            pass
    return None


def _save_activity_file(date_str, data):
    """保存指定日期的活动文件（原子写入）"""
    ACTIVITY_DIR.mkdir(parents=True, exist_ok=True)
    activity_file = ACTIVITY_DIR / f'activity_{date_str}.json'
    temp_file = activity_file.with_suffix('.tmp')

    with open(temp_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    try:
        temp_file.replace(activity_file)
    except OSError:
        if activity_file.exists():
            activity_file.unlink()
        temp_file.rename(activity_file)


def handle_track_flush(message):
    """处理 track_flush 动作：接收活跃段数据，按日期追加到每日JSON文件"""
    segments = message.get('segments', [])
    if not segments:
        return {"status": "ok", "flushedCount": 0}

    # 按日期分组
    date_groups = defaultdict(list)
    for seg in segments:
        date_str = _timestamp_to_date(seg.get('startTime', 0))
        date_groups[date_str].append(seg)

    total_flushed = 0

    for date_str, new_segments in date_groups.items():
        # 加载现有数据
        existing = _load_activity_file(date_str)
        if existing:
            # 合并段：用startTime去重
            existing_starts = {s.get('startTime') for s in existing.get('segments', [])}
            merged_segments = existing.get('segments', [])
            added = 0
            for seg in new_segments:
                if seg.get('startTime') not in existing_starts:
                    merged_segments.append(seg)
                    added += 1

            if added > 0:
                # 按startTime排序
                merged_segments.sort(key=lambda s: s.get('startTime', 0))
                existing['segments'] = merged_segments
                # 重算摘要
                existing['summary'] = _compute_daily_summary(merged_segments)
                _save_activity_file(date_str, existing)
                total_flushed += added
        else:
            # 新建每日文件
            new_segments.sort(key=lambda s: s.get('startTime', 0))
            data = {
                "date": date_str,
                "segments": new_segments,
                "summary": _compute_daily_summary(new_segments)
            }
            _save_activity_file(date_str, data)
            total_flushed += len(new_segments)

    return {"status": "ok", "flushedCount": total_flushed}


def handle_track_report(message):
    """处理 track_report 动作：根据日期范围聚合活动数据，返回报告JSON"""
    start_date = message.get('startDate', '')
    end_date = message.get('endDate', '')
    report_id = message.get('_reportId', '')

    if not start_date or not end_date:
        return {
            "status": "error",
            "message": "Missing startDate or endDate",
            "_reportId": report_id
        }

    # 读取日期范围内的所有活动文件
    all_segments = []
    daily_summaries = {}
    all_domain_ms = defaultdict(int)
    all_category_ms = defaultdict(int)
    all_hourly = [0] * 24

    try:
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')

        current = start_dt
        one_day = timedelta(days=1)
        while current <= end_dt:
            date_str = current.strftime('%Y-%m-%d')
            data = _load_activity_file(date_str)
            if data:
                segs = data.get('segments', [])
                all_segments.extend(segs)
                daily_summaries[date_str] = data.get('summary', {})

                # 聚合域名和分类
                summary = data.get('summary', {})
                for d in summary.get('topDomains', []):
                    all_domain_ms[d['domain']] += d['ms']
                for c in summary.get('topCategories', []):
                    all_category_ms[c['category']] += c['ms']

                # 聚合小时
                for i, ms in enumerate(summary.get('hourlyBuckets', [0] * 24)):
                    all_hourly[i] += ms

            current += one_day
    except ValueError:
        return {
            "status": "error",
            "message": "Invalid date format, expected YYYY-MM-DD",
            "_reportId": report_id
        }

    # 计算总活跃时长
    total_active_ms = sum(s.get('duration', 0) for s in all_segments)

    # 计算专注分数：综合"持续度"和"切换频率"两个维度
    # 维度1 - 持续度：按段时长加权计分（指数曲线，1min≈30, 2min≈60, 5min=100）
    # 维度2 - 稳定度：1 - (切换次数/总活跃分钟)，切换越少分越高
    import math
    continuity_score = 0
    for seg in all_segments:
        dur_min = seg.get('duration', 0) / 60000
        continuity_score += (1 - math.exp(-dur_min / 1.5)) * seg.get('duration', 0)
    avg_continuity = (continuity_score / total_active_ms * 100) if total_active_ms > 0 else 0

    total_active_min = total_active_ms / 60000
    switch_penalty = min(1, (len(all_segments) - 1) / total_active_min) if total_active_min > 0 else 1
    stability_score = (1 - switch_penalty) * 100

    focus_score = round(avg_continuity * 0.6 + stability_score * 0.4) if total_active_ms > 0 else 0

    # 排序
    top_domains = sorted(all_domain_ms.items(), key=lambda x: x[1], reverse=True)[:10]
    top_categories = sorted(all_category_ms.items(), key=lambda x: x[1], reverse=True)

    # 最活跃小时
    most_active_hour = all_hourly.index(max(all_hourly)) if any(all_hourly) else -1

    return {
        "status": "ok",
        "_reportId": report_id,
        "startDate": start_date,
        "endDate": end_date,
        "totalActiveMs": total_active_ms,
        "segmentCount": len(all_segments),
        "focusScore": focus_score,
        "topDomains": [{"domain": d, "ms": ms} for d, ms in top_domains],
        "topCategories": [{"category": c, "ms": ms} for c, ms in top_categories],
        "hourlyBuckets": all_hourly,
        "mostActiveHour": most_active_hour,
        "dailySummaries": daily_summaries
    }


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
                response = handle_sync(message)
                send_response(response)
            elif action == 'heartbeat':
                response = handle_heartbeat()
                send_response(response)
            elif action == 'track_flush':
                response = handle_track_flush(message)
                send_response(response)
            elif action == 'track_report':
                response = handle_track_report(message)
                send_response(response)
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


if __name__ == '__main__':
    main()
