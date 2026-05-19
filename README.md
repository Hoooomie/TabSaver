# TabSaver

> Chrome 标签页自动保存与一键恢复 + 专注力追踪工具

每次关闭 Chrome 浏览器时，自动记录当前所有标签页。下次想恢复时，点击一下就能全部重新打开，再也不用一个一个去找了。新增 **TabTracker 专注力追踪**——自动记录你在每个网页上停留的时间，生成可视化报告。

## 功能亮点

- 🔄 **标签页自动/手动保存** — 关闭 Chrome 也不丢标签
- 🎯 **专注力追踪** — 记录每个页面的停留时长，按域名自动分类
- 📊 **可视化报告** — 每小时活跃时间、Top 站点、分类占比、专注分数
- 🔌 **离线可用** — Native Host 确保数据持久化到本地，不依赖云端

## 工作原理

TabSaver 由三个部分协作：

| 组件 | 说明 |
| :---: | :---: |
| **Chrome 扩展** | 实时监控标签页变化，追踪浏览时长，通过 Native Messaging 将数据同步到本地 |
| **Native Messaging Host** | Chrome 自动启动的中转脚本，接收扩展消息并写入 JSON 文件 |
| **桌面端应用** | 读取会话数据，提供可视化界面和一键恢复功能 |

关键：**即使桌面端没有启动，Chrome 关闭时标签页也会被自动保存**——因为 Chrome 会自动拉起 Native Host 进程。

## 安装

### 方式一：下载 Release（推荐）

1. 从 [Releases](../../releases) 下载最新版 `TabSaver.zip`
2. 解压到任意目录
3. 运行 `install.bat`，按提示输入 Extension ID
4. 双击 `TabSaver.exe` 启动，可右键发送快捷方式到桌面

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
- 提示输入 Extension ID 并写入配置
- 注册 Windows 注册表项
- 初始化数据文件

### 2. 加载 Chrome 扩展

1. 打开 Chrome，访问 `chrome://extensions/`
2. 开启右上角 **开发者模式**
3. 点击 **加载已解压的扩展程序**
4. 选择项目中的 `extension/` 文件夹
5. 记下扩展卡片上显示的 **Extension ID**

### 3. 输入 Extension ID

安装脚本会提示你输入 Extension ID，输入后自动配置。如果跳过了这一步，需要手动编辑 `%APPDATA%\TabSaver\native-host\com.tabsaver.host.json`，将 `EXTENSION_ID_PLACEHOLDER` 替换为实际的扩展 ID：

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

### 标签页保存

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

## 🎯 TabTracker 专注力追踪

TabTracker 自动记录你在每个网页上停留的时长，无需手动操作。

### 查看专注力报告

1. 点击 Chrome 工具栏的 TabSaver 图标
2. 点击 **查看专注力报告** 按钮
3. 打开 Dashboard 页面，查看当日/当周的浏览数据

### Dashboard 报告内容

| 图表 | 说明 |
| :---: | :--- |
| **每小时活跃时间** | 柱状图展示一天24小时的浏览活跃度分布 |
| **Top 站点** | 横向柱状图展示停留时间最长的10个网站 |
| **分类占比** | 环形图展示各类别（开发、社交、娱乐等）的时间占比 |

### 统计指标

| 指标 | 说明 |
| :---: | :--- |
| **总活跃时间** | 当日/当周的总浏览时长 |
| **最常访问** | 停留时间最长的域名 |
| **最活跃时段** | 浏览时间最多的小时 |
| **专注分数** | 0-100 分，综合持续度和稳定度 |

### 专注分数算法

专注分数由两个维度加权计算：

| 维度 | 权重 | 说明 |
| :---: | :---: | :--- |
| **持续度** | 60% | 单次停留时间越长分越高（指数曲线，2分钟≈60分，5分钟≈满分） |
| **稳定度** | 40% | 切换标签频率越低分越高（每5分钟切一次接近满分） |

评分参考：

| 分数 | 等级 | 含义 |
| :---: | :---: | :--- |
| ≥70 | 🟢 专注 | 大部分时间在深度浏览 |
| 40-69 | 🟡 一般 | 频繁切换，注意力分散 |
| <40 | 🔴 分心 | 频繁跳转，基本没有长停留 |

### 域名分类

自动将浏览的网站归入以下类别：

| 类别 | 示例 |
| :---: | :--- |
| Development | github.com, stackoverflow.com |
| Social | weibo.com, twitter.com, reddit.com |
| Communication | mail.google.com, web.wechat.com |
| Entertainment | bilibili.com, youtube.com |
| News | zhihu.com, news.ycombinator.com |
| Work | docs.google.com, notion.so |
| Shopping | taobao.com, jd.com |
| Learning | coursera.org, leetcode.com |

### 数据存储

追踪数据按日存储在 `%APPDATA%\TabSaver\data\activity\activity_YYYY-MM-DD.json`，每5分钟自动 flush 一次。Dashboard 查询时也会先 flush 待发送数据，确保报告内容是最新的。

### 设置

点击会话列表右上角的 **⚙ 设置** 按钮可配置：

| 参数 | 说明 | 默认值 |
| :---: | :--- | :---: |
| **保存模式** | auto（自动保存）或 manual（手动保存） | auto |
| **最大保存会话数** | 最多保留多少个历史会话，超出后自动删除最旧的 | 100 |
| **最少标签页数** | 打开的标签页少于此数时不保存会话 | 1 |

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
│   ├── background.js       # 标签页监控 + Native Messaging 通信 + 报告转发
│   ├── tracker.js          # TabTracker 时间追踪核心
│   ├── categories.js       # 域名→分类映射
│   ├── popup.html / .js    # 扩展弹窗（含专注力报告入口）
│   ├── dashboard/          # 专注力报告页面
│   │   ├── dashboard.html
│   │   ├── dashboard.js    # Chart.js 图表渲染
│   │   └── dashboard.css
│   ├── lib/
│   │   └── chart.min.js    # Chart.js v4
│   └── icons/              # 扩展图标
├── native-host/            # Native Messaging Host
│   ├── tab_saver_host.py   # 标签页同步 + 活动数据持久化 + 报告生成
│   └── com.tabsaver.host.json  # NM 清单文件（模板）
├── app/                    # Python 桌面端
│   ├── main.py             # tkinter UI + 会话管理 + 一键恢复
│   ├── tab-saver.ico       # 应用图标
│   └── requirements.txt    # Python 依赖
├── install.bat             # 安装脚本（自动提示 Extension ID）
├── start.bat               # 启动脚本（源码运行时使用）
├── README.md
└── LICENSE
```

## 数据存储

| 文件 | 说明 |
| :---: | :--- |
| `%APPDATA%\TabSaver\data\sessions.json` | 标签页会话记录 |
| `%APPDATA%\TabSaver\data\latest_tabs.json` | 当前标签页快照 |
| `%APPDATA%\TabSaver\data\config.json` | 配置文件 |
| `%APPDATA%\TabSaver\data\activity\activity_YYYY-MM-DD.json` | 每日追踪数据 |

默认最多保留 100 个会话（可在设置中调整）。

## 技术栈

- **Chrome 扩展**: Manifest V3, Service Worker, chrome.idle API
- **Native Messaging Host**: Python 3, Chrome Native Messaging 协议
- **桌面端**: Python 3 + tkinter
- **报告可视化**: Chart.js v4
- **打包**: PyInstaller

## 许可证

MIT License
