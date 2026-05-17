# TabSaver

> Chrome 标签页自动保存与一键恢复工具

每次关闭 Chrome 浏览器时，自动记录当前所有标签页。下次想恢复时，点击一下就能全部重新打开，再也不用一个一个去找了。

## 工作原理

TabSaver 由三个部分协作：

| 组件 | 说明 |
| :---: | :---: |
| **Chrome 扩展** | 实时监控标签页变化，通过 Native Messaging 将数据同步到本地 |
| **Native Messaging Host** | Chrome 自动启动的中转脚本，接收扩展消息并写入 JSON 文件 |
| **桌面端应用** | 读取会话数据，提供可视化界面和一键恢复功能 |

关键：**即使桌面端没有启动，Chrome 关闭时标签页也会被自动保存**——因为 Chrome 会自动拉起 Native Host 进程。

## 安装

### 方式一：下载 Release（推荐）

1. 从 [Releases](../../releases) 下载最新版 `TabSaver.zip`
2. 解压到任意目录
3. 运行 `install.bat`
4. 按照提示完成 Chrome 扩展加载
5. 双击 `TabSaver.exe` 启动，可右键发送快捷方式到桌面

### 方式二：从源码运行

需要安装 Python 3.10+ 和 Pillow。

```bash
# 克隆仓库
git clone https://github.com/Hoooomie/TabSaver.git
cd TabSaver

# 运行安装脚本
install.bat

# 启动桌面端
start.bat
```

## 详细安装步骤

### 1. 运行安装脚本

双击 `install.bat`，它会自动：

- 创建数据目录 `%APPDATA%\TabSaver\`
- 安装 Native Messaging Host 脚本
- 注册 Windows 注册表项
- 初始化数据文件

### 2. 加载 Chrome 扩展

1. 打开 Chrome，访问 `chrome://extensions/`
2. 开启右上角 **开发者模式**
3. 点击 **加载已解压的扩展程序**
4. 选择项目中的 `extension/` 文件夹
5. 记下扩展卡片上显示的 **Extension ID**

### 3. 配置 Extension ID

编辑文件 `%APPDATA%\TabSaver\native-host\com.tabsaver.host.json`，将 `EXTENSION_ID_PLACEHOLDER` 替换为实际的扩展 ID：

```json
{
  "allowed_origins": [
    "chrome-extension://你的扩展ID/"
  ]
}
```

### 4. 启动桌面端

双击 `TabSaver.exe` 即可启动。也可以右键 → 发送到 → 桌面快捷方式，以后从桌面一键打开。

## 使用方法

1. 正常使用 Chrome 浏览网页
2. 关闭 Chrome 时，所有标签页会被自动保存（自动模式下）
3. 打开 TabSaver 桌面端，左侧显示历史会话列表
4. 选中一个会话，点击 **一键恢复** 即可在 Chrome 中打开所有标签页
5. 手动模式下，点击 **💾 保存当前标签页** 按钮手动保存

### 自动模式 vs 手动模式

| 模式 | 行为 |
| :---: | :--- |
| **auto（自动）** | 标签页在每次变化时自动同步，关闭 Chrome 时自动保存 |
| **manual（手动）** | 标签页不会自动保存，需在桌面端点击"保存当前标签页"按钮手动保存 |

两种模式下，Chrome 扩展都会持续监控标签页变化，区别仅在于是否自动写入会话文件。

### 手动保存流程

1. 切换到手动模式（设置 → 保存模式 → manual）
2. 正常使用 Chrome 浏览网页
3. 想保存时，打开 TabSaver 桌面端，点击 **💾 保存当前标签页**
4. 应用会通过信号文件通知 Chrome 扩展同步当前标签页
5. 保存成功后自动刷新会话列表

> **注意**：手动保存需要 Chrome 浏览器正在运行且 TabSaver 扩展已启用。如果超时未响应，会提示检查 Chrome 状态。

### 智能去重

当保存时，如果当前打开的标签页集合与某个已有会话完全一致（URL 集合相同），TabSaver 会自动跳过保存，避免产生重复记录。手动保存时默认跳过去重检查，确保用户意图始终生效。

### 设置

点击会话列表右上角的 **⚙ 设置** 按钮可配置：

| 参数 | 说明 | 默认值 |
| :---: | :--- | :---: |
| **保存模式** | auto（自动保存）或 manual（手动保存） | auto |
| **最大保存会话数** | 最多保留多少个历史会话，超出后自动删除最旧的 | 100 |
| **最少标签页数** | 打开的标签页少于此数时不保存会话（避免只开了1个标签也存一份） | 1 |

配置保存在 `%APPDATA%\TabSaver\data\config.json`，修改后即时生效。

## 从源码构建 exe

```bash
pip install pyinstaller Pillow
pyinstaller --onefile --noconsole --name TabSaver --icon=app/tab-saver.ico --distpath ./dist app/main.py
```

构建产物在 `dist/TabSaver.exe`，无需 Python 环境即可运行。

## 项目结构

```
TabSaver/
├── extension/              # Chrome 扩展 (Manifest V3)
│   ├── manifest.json
│   ├── background.js       # 标签页监控与 Native Messaging 通信
│   ├── popup.html / .js    # 扩展弹窗
│   └── icons/              # 扩展图标
├── native-host/            # Native Messaging Host
│   ├── tab_saver_host.py   # 接收扩展消息，写入 sessions.json
│   └── com.tabsaver.host.json  # NM 清单文件
├── app/                    # Python 桌面端
│   ├── main.py             # tkinter UI + 会话管理 + 一键恢复
│   ├── tab-saver.ico       # 应用图标
│   └── requirements.txt    # Python 依赖
├── install.bat             # 安装脚本
├── start.bat               # 启动脚本（源码运行时使用）
├── README.md
└── LICENSE
```

## 数据存储

标签页数据存储在：`%APPDATA%\TabSaver\data\sessions.json`

配置文件存储在：`%APPDATA%\TabSaver\data\config.json`

每个会话记录包含：

- 保存时间
- 标签页数量
- 每个标签页的 URL、标题、图标

默认最多保留 100 个会话（可在设置中调整）。

## 技术栈

- **Chrome 扩展**: Manifest V3, Service Worker
- **Native Messaging Host**: Python 3, Chrome Native Messaging 协议
- **桌面端**: Python 3 + tkinter
- **打包**: PyInstaller

## 许可证

MIT License
