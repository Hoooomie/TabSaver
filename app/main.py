#!/usr/bin/env python3
"""
TabSaver - Chrome标签页自动保存与恢复工具 (桌面端)

功能：
- 读取Native Host保存的标签页会话数据
- 提供可视化界面浏览和恢复会话
- 一键恢复所有标签页到Chrome
- 支持自动/手动两种保存模式
- 手动模式下：直接读取latest_tabs.json，写入sessions.json
- 可配置最大保存会话数和最少标签页阈值
"""

import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path

# ========== 路径配置 ==========

APPDATA = os.environ.get('APPDATA', str(Path.home() / 'AppData' / 'Roaming'))
DATA_DIR = Path(APPDATA) / 'TabSaver' / 'data'
SESSIONS_FILE = DATA_DIR / 'sessions.json'
CONFIG_FILE = DATA_DIR / 'config.json'
LATEST_TABS_FILE = DATA_DIR / 'latest_tabs.json'

# 默认配置
DEFAULT_CONFIG = {
    "mode": "auto",
    "max_sessions": 100,
    "threshold": 1
}

# Chrome可能的安装路径
CHROME_PATHS = [
    Path(os.environ.get('LOCALAPPDATA', '')) / 'Google' / 'Chrome' / 'Application' / 'chrome.exe',
    Path('C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'),
    Path('C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe'),
]


# ========== 配置管理 ==========

def load_config():
    """加载配置文件"""
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


def save_config(config):
    """保存配置文件"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


# ========== 会话数据管理 ==========

class SessionManager:
    """管理标签页会话数据的读写"""

    def __init__(self, sessions_file=SESSIONS_FILE):
        self.sessions_file = Path(sessions_file)
        self._last_mtime = 0

    def load_sessions(self):
        """加载所有会话"""
        if not self.sessions_file.exists():
            return []
        try:
            with open(self.sessions_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            sessions = data.get('sessions', [])
            sessions.sort(key=lambda s: s.get('timestamp', ''), reverse=True)
            return sessions
        except (json.JSONDecodeError, IOError):
            return []

    def _load_sessions_data(self):
        """加载完整会话数据（包含sessions列表的字典）"""
        if not self.sessions_file.exists():
            return {"sessions": []}
        try:
            with open(self.sessions_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if 'sessions' in data and isinstance(data['sessions'], list):
                return data
        except (json.JSONDecodeError, IOError):
            pass
        return {"sessions": []}

    def _save_sessions_data(self, data):
        """保存完整会话数据"""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        temp_file = self.sessions_file.with_suffix('.tmp')
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        try:
            temp_file.replace(self.sessions_file)
        except OSError:
            if self.sessions_file.exists():
                self.sessions_file.unlink()
            temp_file.rename(self.sessions_file)

    def add_session(self, tabs, tab_count):
        """
        添加一个新会话到sessions.json（用于手动保存）。
        总是创建新会话，不覆盖已有会话。
        """
        now = datetime.now()
        session_id = now.strftime('%Y%m%d_%H%M%S_') + f'{now.microsecond // 1000:03d}'
        timestamp = now.isoformat()

        session = {
            "id": session_id,
            "timestamp": timestamp,
            "tabCount": tab_count,
            "tabs": tabs
        }

        data = self._load_sessions_data()
        data['sessions'].append(session)

        # 应用max_sessions限制
        config = load_config()
        max_sessions = config.get('max_sessions', DEFAULT_CONFIG['max_sessions'])
        if len(data['sessions']) > max_sessions:
            data['sessions'] = data['sessions'][-max_sessions:]

        self._save_sessions_data(data)
        return session_id

    def delete_session(self, session_id):
        """删除指定会话"""
        data = self._load_sessions_data()
        data['sessions'] = [s for s in data['sessions'] if s.get('id') != session_id]
        self._save_sessions_data(data)
        return True

    def clear_all_sessions(self):
        """清空所有会话"""
        try:
            data = {"sessions": []}
            with open(self.sessions_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except IOError:
            return False

    def has_changed(self):
        """检查文件是否有更新（用于自动刷新）"""
        try:
            mtime = self.sessions_file.stat().st_mtime if self.sessions_file.exists() else 0
        except OSError:
            mtime = 0
        if mtime != self._last_mtime:
            self._last_mtime = mtime
            return True
        return False


# ========== Chrome启动 ==========

def find_chrome():
    """查找Chrome可执行文件路径"""
    for path in CHROME_PATHS:
        if path.exists():
            return str(path)
    return None


def restore_tabs(chrome_path, urls):
    """用Chrome打开一组URL"""
    if not chrome_path:
        chrome_path = find_chrome()
    if not chrome_path:
        messagebox.showerror("错误", "未找到Chrome浏览器！\n请确认Chrome已安装。")
        return False

    if not urls:
        messagebox.showwarning("提示", "没有可恢复的标签页。")
        return False

    try:
        cmd = [chrome_path, '--new-window'] + urls
        subprocess.Popen(cmd)
        return True
    except Exception as e:
        messagebox.showerror("错误", f"启动Chrome失败：{e}")
        return False


# ========== 主界面 ==========

class TabSaverApp:
    """TabSaver桌面端主应用"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("TabSaver - 标签页保存器")
        self.root.geometry("800x550")
        self.root.minsize(600, 400)

        # 配置样式
        self.setup_styles()

        self.session_manager = SessionManager()
        self.chrome_path = find_chrome()
        self.sessions = []
        self.current_session = None

        # 确保数据目录存在
        self._ensure_data_dir()

        # 构建UI
        self.build_ui()

        # 加载数据
        self.refresh_sessions()

        # 启动自动刷新
        self.start_auto_refresh()

        # 窗口关闭处理
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def setup_styles(self):
        """配置ttk样式"""
        style = ttk.Style()
        style.theme_use('clam')

        style.configure('Title.TLabel', font=('Microsoft YaHei UI', 14, 'bold'), foreground='#1a1a1a')
        style.configure('Subtitle.TLabel', font=('Microsoft YaHei UI', 10), foreground='#666666')
        style.configure('Info.TLabel', font=('Microsoft YaHei UI', 9), foreground='#888888')
        style.configure('Primary.TButton', font=('Microsoft YaHei UI', 10))
        style.configure('Danger.TButton', font=('Microsoft YaHei UI', 9))
        style.configure('Save.TButton', font=('Microsoft YaHei UI', 10, 'bold'))
        style.configure('Session.TLabel', font=('Microsoft YaHei UI', 11), foreground='#333333')
        style.configure('SessionCount.TLabel', font=('Microsoft YaHei UI', 9), foreground='#1a73e8')

        style.configure('SessionList.TFrame', background='#ffffff')
        style.configure('Detail.TFrame', background='#fafafa')

    def build_ui(self):
        """构建主界面"""
        # 顶部标题栏
        header = ttk.Frame(self.root, padding=(16, 12, 16, 8))
        header.pack(fill=tk.X)

        ttk.Label(header, text="TabSaver", style='Title.TLabel').pack(side=tk.LEFT)

        # 当前模式标签
        config = load_config()
        mode = config.get('mode', 'auto')
        mode_text = "自动模式" if mode == "auto" else "手动模式"
        mode_color = '#34a853' if mode == 'auto' else '#f9ab00'
        self.mode_label = ttk.Label(header, text=f"[{mode_text}]", style='Info.TLabel', foreground=mode_color)
        self.mode_label.pack(side=tk.LEFT, padx=(12, 0))

        # Chrome状态
        chrome_status = "Chrome: 已检测到" if self.chrome_path else "Chrome: 未检测到"
        chrome_label = ttk.Label(header, text=chrome_status, style='Info.TLabel')
        chrome_label.pack(side=tk.RIGHT)

        # 分割线
        ttk.Separator(self.root, orient=tk.HORIZONTAL).pack(fill=tk.X)

        # 主体区域 - 左右分栏
        main_pane = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # 左侧：会话列表
        left_frame = ttk.Frame(main_pane)
        main_pane.add(left_frame, weight=1)

        # 左侧标题
        list_header = ttk.Frame(left_frame)
        list_header.pack(fill=tk.X, pady=(0, 4))

        ttk.Label(list_header, text="会话列表", style='Subtitle.TLabel').pack(side=tk.LEFT)

        btn_refresh = ttk.Button(list_header, text="刷新", command=self.refresh_sessions, width=6)
        btn_refresh.pack(side=tk.RIGHT)

        btn_settings = ttk.Button(list_header, text="设置", command=self.open_settings, width=8)
        btn_settings.pack(side=tk.RIGHT, padx=(0, 4))

        # 会话列表框
        list_frame = ttk.Frame(left_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar_left = ttk.Scrollbar(list_frame)
        scrollbar_left.pack(side=tk.RIGHT, fill=tk.Y)

        self.session_listbox = tk.Listbox(
            list_frame,
            yscrollcommand=scrollbar_left.set,
            font=('Microsoft YaHei UI', 10),
            selectmode=tk.SINGLE,
            activestyle='none',
            bd=0,
            highlightthickness=1,
            highlightcolor='#1a73e8',
            selectbackground='#e8f0fe',
            selectforeground='#1a73e8',
        )
        self.session_listbox.pack(fill=tk.BOTH, expand=True)
        scrollbar_left.config(command=self.session_listbox.yview)

        self.session_listbox.bind('<<ListboxSelect>>', self.on_session_select)

        # 左侧底部按钮
        btn_frame = ttk.Frame(left_frame)
        btn_frame.pack(fill=tk.X, pady=(8, 0))

        self.btn_save = ttk.Button(btn_frame, text="保存当前标签页", command=self.save_current_tabs, style='Save.TButton')
        self.btn_save.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 2))

        btn_restore = ttk.Button(btn_frame, text="一键恢复", command=self.restore_selected, style='Primary.TButton')
        btn_restore.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(2, 2))

        btn_delete = ttk.Button(btn_frame, text="删除", command=self.delete_selected, style='Danger.TButton')
        btn_delete.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(2, 0))

        # 右侧：会话详情
        right_frame = ttk.Frame(main_pane)
        main_pane.add(right_frame, weight=2)

        # 右侧标题
        detail_header = ttk.Frame(right_frame)
        detail_header.pack(fill=tk.X, pady=(0, 4))

        self.detail_title = ttk.Label(detail_header, text="选择一个会话查看详情", style='Subtitle.TLabel')
        self.detail_title.pack(side=tk.LEFT)

        self.detail_count = ttk.Label(detail_header, text="", style='Info.TLabel')
        self.detail_count.pack(side=tk.RIGHT)

        # 标签页列表
        detail_frame = ttk.Frame(right_frame)
        detail_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar_right = ttk.Scrollbar(detail_frame)
        scrollbar_right.pack(side=tk.RIGHT, fill=tk.Y)

        self.tab_detail = tk.Text(
            detail_frame,
            yscrollcommand=scrollbar_right.set,
            font=('Microsoft YaHei UI', 9),
            wrap=tk.WORD,
            bd=1,
            relief=tk.SOLID,
            padx=8,
            pady=8,
            state=tk.DISABLED,
            cursor='arrow',
            spacing1=2,
            spacing3=2,
        )
        self.tab_detail.pack(fill=tk.BOTH, expand=True)
        scrollbar_right.config(command=self.tab_detail.yview)

        self.tab_detail.tag_configure('title', font=('Microsoft YaHei UI', 10, 'bold'), foreground='#333333')
        self.tab_detail.tag_configure('url', font=('Consolas', 9), foreground='#1a73e8')
        self.tab_detail.tag_configure('separator', font=('Arial', 6), foreground='#e0e0e0')
        self.tab_detail.tag_configure('index', font=('Microsoft YaHei UI', 9, 'bold'), foreground='#888888')
        self.tab_detail.tag_configure('empty', font=('Microsoft YaHei UI', 11), foreground='#cccccc', justify=tk.CENTER)

        # 底部状态栏
        status_bar = ttk.Frame(self.root, padding=(16, 4))
        status_bar.pack(fill=tk.X)

        self.status_label = ttk.Label(status_bar, text="就绪", style='Info.TLabel')
        self.status_label.pack(side=tk.LEFT)

        ttk.Button(status_bar, text="清空所有", command=self.clear_all, width=8).pack(side=tk.RIGHT)

    def update_mode_display(self):
        """更新顶部模式标签"""
        config = load_config()
        mode = config.get('mode', 'auto')
        mode_text = "自动模式" if mode == "auto" else "手动模式"
        mode_color = '#34a853' if mode == 'auto' else '#f9ab00'
        self.mode_label.config(text=f"[{mode_text}]", foreground=mode_color)

    def save_current_tabs(self):
        """
        手动保存当前Chrome标签页。
        直接读取 latest_tabs.json，创建新会话写入 sessions.json。
        无需信号文件和心跳，零延迟。
        """
        # 读取 latest_tabs.json
        if not LATEST_TABS_FILE.exists():
            messagebox.showwarning(
                "无法保存",
                "未找到Chrome标签页数据。\n\n可能原因：\n"
                "- Chrome浏览器未运行\n"
                "- TabSaver扩展未启用\n\n"
                "请确认Chrome已打开且扩展正常工作。"
            )
            return

        try:
            with open(LATEST_TABS_FILE, 'r', encoding='utf-8') as f:
                latest_data = json.load(f)
        except (json.JSONDecodeError, IOError):
            messagebox.showerror("错误", "读取标签页数据失败，文件可能已损坏。")
            return

        tabs = latest_data.get('tabs', [])
        tab_count = latest_data.get('tabCount', len(tabs))
        timestamp_str = latest_data.get('timestamp', '')

        if not tabs:
            messagebox.showwarning("提示", "当前没有可保存的标签页。")
            return

        # 检查数据是否新鲜（超过2分钟视为过期）
        try:
            sync_dt = datetime.fromisoformat(timestamp_str)
            if sync_dt.tzinfo is not None:
                sync_dt = sync_dt.astimezone()
            elapsed = (datetime.now() - sync_dt).total_seconds()
            if elapsed > 120:
                messagebox.showwarning(
                    "数据可能过期",
                    f"标签页数据是 {int(elapsed)} 秒前的，可能不是最新的。\n\n"
                    "请确认Chrome正在运行且TabSaver扩展已启用。"
                )
                return
        except (ValueError, TypeError):
            pass  # 无法解析时间，继续保存

        # 直接写入 sessions.json（总是创建新会话，不覆盖）
        try:
            session_id = self.session_manager.add_session(tabs, tab_count)
            self.status_label.config(text=f"已保存 {tab_count} 个标签页")
            self.refresh_sessions()
        except Exception as e:
            messagebox.showerror("保存失败", f"写入会话数据时出错：{e}")

    def refresh_sessions(self):
        """刷新会话列表"""
        self.sessions = self.session_manager.load_sessions()
        self.session_listbox.delete(0, tk.END)

        if not self.sessions:
            self.session_listbox.insert(tk.END, "暂无保存的会话")
            self.session_listbox.config(state=tk.DISABLED)
            self.current_session = None
            self.show_empty_detail()
            return

        self.session_listbox.config(state=tk.NORMAL)

        for session in self.sessions:
            timestamp = session.get('timestamp', '')
            tab_count = session.get('tabCount', 0)

            try:
                dt = datetime.fromisoformat(timestamp)
                if dt.tzinfo is not None:
                    dt = dt.astimezone()
                time_str = dt.strftime('%Y-%m-%d %H:%M')
            except (ValueError, TypeError):
                time_str = timestamp

            display_text = f"{time_str}  ({tab_count}个标签页)"
            self.session_listbox.insert(tk.END, display_text)

        config = load_config()
        mode = config.get('mode', 'auto')
        self.status_label.config(text=f"已加载 {len(self.sessions)} 个会话 | {'自动' if mode == 'auto' else '手动'}模式")

    def on_session_select(self, event=None):
        """选中会话时显示详情"""
        selection = self.session_listbox.curselection()
        if not selection:
            return

        idx = selection[0]
        if idx >= len(self.sessions):
            return

        self.current_session = self.sessions[idx]
        self.show_session_detail(self.current_session)

    def show_session_detail(self, session):
        """显示会话的标签页详情"""
        self.tab_detail.config(state=tk.NORMAL)
        self.tab_detail.delete('1.0', tk.END)

        timestamp = session.get('timestamp', '')
        tabs = session.get('tabs', [])
        tab_count = session.get('tabCount', len(tabs))

        try:
            dt = datetime.fromisoformat(timestamp)
            if dt.tzinfo is not None:
                dt = dt.astimezone()
            time_str = dt.strftime('%Y-%m-%d %H:%M:%S')
        except (ValueError, TypeError):
            time_str = timestamp

        self.detail_title.config(text=f"会话详情 - {time_str}")
        self.detail_count.config(text=f"{tab_count} 个标签页")

        if not tabs:
            self.tab_detail.insert(tk.END, "\n  此会话无标签页数据", 'empty')
            self.tab_detail.config(state=tk.DISABLED)
            return

        for i, tab in enumerate(tabs):
            title = tab.get('title', '无标题')
            url = tab.get('url', '')

            self.tab_detail.insert(tk.END, f" {i+1}. ", 'index')
            self.tab_detail.insert(tk.END, f"{title}\n", 'title')
            self.tab_detail.insert(tk.END, f"    {url}\n", 'url')
            if i < len(tabs) - 1:
                self.tab_detail.insert(tk.END, "    " + "-" * 40 + "\n", 'separator')

        self.tab_detail.config(state=tk.DISABLED)

    def show_empty_detail(self):
        """显示空状态"""
        self.tab_detail.config(state=tk.NORMAL)
        self.tab_detail.delete('1.0', tk.END)

        config = load_config()
        mode = config.get('mode', 'auto')

        self.tab_detail.insert(tk.END, "\n\n    暂无保存的标签页会话\n\n", 'empty')
        if mode == 'manual':
            self.tab_detail.insert(tk.END, "    手动模式下，点击下方\n", 'empty')
            self.tab_detail.insert(tk.END, "    \"保存当前标签页\" 按钮保存\n", 'empty')
        else:
            self.tab_detail.insert(tk.END, "    关闭Chrome浏览器时\n", 'empty')
            self.tab_detail.insert(tk.END, "    标签页将被自动保存到这里", 'empty')
        self.tab_detail.config(state=tk.DISABLED)
        self.detail_title.config(text="选择一个会话查看详情")
        self.detail_count.config(text="")

    def restore_selected(self):
        """恢复选中会话的所有标签页"""
        if not self.current_session:
            messagebox.showwarning("提示", "请先选择一个会话")
            return

        tabs = self.current_session.get('tabs', [])
        urls = [tab['url'] for tab in tabs if tab.get('url')]

        if not urls:
            messagebox.showwarning("提示", "此会话没有可恢复的标签页")
            return

        chrome = self.chrome_path or find_chrome()
        if not chrome:
            messagebox.showerror("错误", "未找到Chrome浏览器！")
            return

        success = restore_tabs(chrome, urls)
        if success:
            self.status_label.config(text=f"已恢复 {len(urls)} 个标签页")
            messagebox.showinfo("成功", f"已在Chrome中打开 {len(urls)} 个标签页！")

    def delete_selected(self):
        """删除选中会话"""
        if not self.current_session:
            messagebox.showwarning("提示", "请先选择一个会话")
            return

        session_id = self.current_session.get('id', '')
        tab_count = self.current_session.get('tabCount', 0)

        if not messagebox.askyesno("确认删除", f"确定要删除此会话（{tab_count}个标签页）吗？"):
            return

        if self.session_manager.delete_session(session_id):
            self.status_label.config(text="会话已删除")
            self.current_session = None
            self.refresh_sessions()
        else:
            messagebox.showerror("错误", "删除会话失败")

    def clear_all(self):
        """清空所有会话"""
        if not self.sessions:
            messagebox.showinfo("提示", "没有可清空的会话")
            return

        count = len(self.sessions)
        if not messagebox.askyesno("确认清空", f"确定要清空所有 {count} 个会话吗？\n此操作不可撤销！"):
            return

        if self.session_manager.clear_all_sessions():
            self.status_label.config(text="所有会话已清空")
            self.current_session = None
            self.refresh_sessions()
        else:
            messagebox.showerror("错误", "清空会话失败")

    def open_settings(self):
        """打开设置对话框"""
        dialog = tk.Toplevel(self.root)
        dialog.title("TabSaver 设置")
        dialog.geometry("440x340")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        # 居中显示
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 440) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 340) // 2
        dialog.geometry(f"+{x}+{y}")

        # 加载当前配置
        config = load_config()

        # 标题
        ttk.Label(dialog, text="TabSaver 设置", font=('Microsoft YaHei UI', 14, 'bold')).pack(pady=(20, 16))
        ttk.Separator(dialog, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=20)

        # 设置表单
        form = ttk.Frame(dialog, padding=20)
        form.pack(fill=tk.BOTH, expand=True)

        # 保存模式
        row0 = ttk.Frame(form)
        row0.pack(fill=tk.X, pady=(0, 4))

        ttk.Label(row0, text="保存模式：", font=('Microsoft YaHei UI', 10)).pack(side=tk.LEFT)
        mode_var = tk.StringVar(value=config.get('mode', 'auto'))
        mode_combo = ttk.Combobox(row0, textvariable=mode_var, values=['auto', 'manual'],
                                   state='readonly', width=10, font=('Microsoft YaHei UI', 10))
        mode_combo.pack(side=tk.RIGHT)

        mode_desc = ttk.Label(form, text="auto = 自动保存 | manual = 手动保存", font=('Microsoft YaHei UI', 8), foreground='#888888')
        mode_desc.pack(anchor=tk.W, pady=(0, 12))

        # max_sessions
        row1 = ttk.Frame(form)
        row1.pack(fill=tk.X, pady=(0, 4))

        ttk.Label(row1, text="最大保存会话数：", font=('Microsoft YaHei UI', 10)).pack(side=tk.LEFT)
        max_sessions_var = tk.IntVar(value=config.get('max_sessions', 100))
        spin_max = ttk.Spinbox(row1, from_=1, to=9999, textvariable=max_sessions_var, width=8, font=('Microsoft YaHei UI', 10))
        spin_max.pack(side=tk.RIGHT)

        ttk.Label(form, text="超过此数量的旧会话将被自动删除", font=('Microsoft YaHei UI', 8), foreground='#888888').pack(anchor=tk.W, pady=(0, 8))

        # threshold
        row2 = ttk.Frame(form)
        row2.pack(fill=tk.X, pady=(0, 4))

        ttk.Label(row2, text="最少标签页数：", font=('Microsoft YaHei UI', 10)).pack(side=tk.LEFT)
        threshold_var = tk.IntVar(value=config.get('threshold', 1))
        spin_threshold = ttk.Spinbox(row2, from_=1, to=999, textvariable=threshold_var, width=8, font=('Microsoft YaHei UI', 10))
        spin_threshold.pack(side=tk.RIGHT)

        ttk.Label(form, text="打开标签页少于此数时不保存会话", font=('Microsoft YaHei UI', 8), foreground='#888888').pack(anchor=tk.W)

        # 按钮
        btn_frame = ttk.Frame(form)
        btn_frame.pack(fill=tk.X, pady=(20, 0))

        def save_settings():
            try:
                max_val = max_sessions_var.get()
                thresh_val = threshold_var.get()
                mode_val = mode_var.get()
                if max_val < 1 or thresh_val < 1:
                    messagebox.showwarning("提示", "数值必须大于0", parent=dialog)
                    return
                if mode_val not in ('auto', 'manual'):
                    messagebox.showwarning("提示", "模式必须为 auto 或 manual", parent=dialog)
                    return
                new_config = {
                    "mode": mode_val,
                    "max_sessions": max_val,
                    "threshold": thresh_val
                }
                save_config(new_config)
                self.update_mode_display()
                mode_text = "自动" if mode_val == "auto" else "手动"
                self.status_label.config(text=f"设置已保存：{mode_text}模式，最多{max_val}个会话，最少{thresh_val}个标签页")
                dialog.destroy()
            except (tk.TclError, ValueError):
                messagebox.showwarning("提示", "请输入有效的数字", parent=dialog)

        ttk.Button(btn_frame, text="保存", command=save_settings, width=10).pack(side=tk.RIGHT, padx=(8, 0))
        ttk.Button(btn_frame, text="取消", command=dialog.destroy, width=10).pack(side=tk.RIGHT)

        # 支持Enter保存，Esc取消
        dialog.bind('<Return>', lambda e: save_settings())
        dialog.bind('<Escape>', lambda e: dialog.destroy())

    def start_auto_refresh(self):
        """启动自动刷新（每5秒检查文件变化）"""
        import threading
        import time

        def auto_refresh():
            while True:
                try:
                    if self.session_manager.has_changed():
                        self.root.after(0, self.refresh_sessions)
                except Exception:
                    pass
                time.sleep(5)

        thread = threading.Thread(target=auto_refresh, daemon=True)
        thread.start()

    def _ensure_data_dir(self):
        """确保数据目录和文件存在"""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if not SESSIONS_FILE.exists():
            try:
                with open(SESSIONS_FILE, 'w', encoding='utf-8') as f:
                    json.dump({"sessions": []}, f, ensure_ascii=False, indent=2)
            except IOError:
                pass

    def on_close(self):
        """窗口关闭处理"""
        self.root.destroy()

    def run(self):
        """运行应用"""
        self.root.mainloop()


# ========== 入口 ==========

if __name__ == '__main__':
    app = TabSaverApp()
    app.run()
