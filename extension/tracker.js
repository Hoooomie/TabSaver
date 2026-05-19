// TabSaver - TabTracker 时间追踪模块
// 记录用户在每个标签页/网页上停留的时长，生成活跃段数据

const MIN_SEGMENT_MS = 1000;  // 最短段时长，低于此值丢弃（过滤噪声）
const FLUSH_INTERVAL_MS = 5 * 60 * 1000;  // 每5分钟flush一次到Native Host
const STORAGE_KEY = 'tracker_segments';    // chrome.storage.local 中的key
const TRACKER_STATE_KEY = 'tracker_state'; // 追踪状态持久化key

class TabTracker {
  constructor() {
    // 当前活跃标签追踪状态
    this.currentTabId = null;
    this.currentUrl = null;
    this.currentDomain = null;
    this.currentTitle = null;
    this.segmentStart = null;

    // 全局状态
    this.isWindowFocused = true;
    this.isUserIdle = false;
    this.pendingSegments = [];  // 待flush的段
    this.flushTimer = null;

    // Native Host 端口引用（由background.js设置）
    this.nativePort = null;

    // 是否已初始化
    this._initialized = false;
  }

  /**
   * 启动追踪
   */
  startTracking() {
    if (this._initialized) return;
    this._initialized = true;

    console.log('[TabTracker] Starting time tracking...');

    // 设置空闲检测间隔（60秒）
    chrome.idle.setDetectionInterval(60);

    // 监听标签页激活（切换标签）
    chrome.tabs.onActivated.addListener((activeInfo) => this._onTabActivated(activeInfo));

    // 监听标签页更新（URL变化）
    chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => this._onTabUpdated(tabId, changeInfo, tab));

    // 监听标签页关闭
    chrome.tabs.onRemoved.addListener((tabId) => this._onTabRemoved(tabId));

    // 监听窗口焦点变化
    chrome.windows.onFocusChanged.addListener((windowId) => this._onWindowFocusChanged(windowId));

    // 监听空闲状态变化
    chrome.idle.onStateChanged.addListener((newState) => this._onIdleStateChanged(newState));

    // 恢复上次未flush的段
    this._loadPendingSegments();

    // 获取当前活跃标签，开始追踪
    this._initActiveTab();

    // 定期flush到Native Host
    this.flushTimer = setInterval(() => this._flushToNativeHost(), FLUSH_INTERVAL_MS);

    console.log('[TabTracker] Tracking started');
  }

  /**
   * 初始化：获取当前活跃标签并开始计时
   */
  async _initActiveTab() {
    try {
      // 获取当前焦点窗口
      const focusedWindow = await chrome.windows.getCurrent();
      if (!focusedWindow || !focusedWindow.focused) {
        this.isWindowFocused = false;
        return;
      }

      // 获取该窗口的活跃标签
      const tabs = await chrome.tabs.query({ active: true, windowId: focusedWindow.id });
      if (tabs.length > 0) {
        this._startNewSegment(tabs[0]);
      }
    } catch (e) {
      console.warn('[TabTracker] Failed to init active tab:', e);
    }
  }

  /**
   * 标签页激活（切换标签）
   */
  _onTabActivated(activeInfo) {
    // 先结束当前段
    this._finalizeCurrentSegment();

    // 获取新激活标签的信息
    chrome.tabs.get(activeInfo.tabId).then((tab) => {
      if (tab && tab.url && !this._isSystemUrl(tab.url)) {
        this._startNewSegment(tab);
      }
    }).catch(() => {});
  }

  /**
   * 标签页更新（URL变化、标题变化、加载完成）
   */
  _onTabUpdated(tabId, changeInfo, tab) {
    // 只关心当前活跃标签的URL变化
    if (tabId !== this.currentTabId) return;
    if (!changeInfo.url && !changeInfo.status) return;

    // URL变化 → 结束旧段，开始新段
    if (changeInfo.url) {
      this._finalizeCurrentSegment();
      if (tab.url && !this._isSystemUrl(tab.url)) {
        this._startNewSegment(tab);
      }
    }
  }

  /**
   * 标签页关闭
   */
  _onTabRemoved(tabId) {
    if (tabId === this.currentTabId) {
      this._finalizeCurrentSegment();
    }
  }

  /**
   * 窗口焦点变化
   */
  _onWindowFocusChanged(windowId) {
    if (windowId === chrome.windows.WINDOW_ID_NONE) {
      // 失去焦点 → 暂停追踪
      this.isWindowFocused = false;
      this._finalizeCurrentSegment();
    } else {
      // 获得焦点 → 恢复追踪
      this.isWindowFocused = true;
      this._initActiveTab();
    }
  }

  /**
   * 空闲状态变化
   */
  _onIdleStateChanged(newState) {
    if (newState === 'active') {
      // 从空闲恢复 → 重新开始追踪
      this.isUserIdle = false;
      if (this.isWindowFocused) {
        this._initActiveTab();
      }
    } else {
      // 进入空闲 → 暂停追踪
      this.isUserIdle = true;
      this._finalizeCurrentSegment();
      // 空闲时顺便flush
      this._flushToNativeHost();
    }
  }

  /**
   * 开始新段
   */
  _startNewSegment(tab) {
    if (!tab || !tab.url || this._isSystemUrl(tab.url)) return;

    this.currentTabId = tab.id;
    this.currentUrl = tab.url;
    this.currentDomain = this._extractDomain(tab.url);
    this.currentTitle = tab.title || tab.url;
    this.segmentStart = Date.now();

    // 持久化状态（防止Service Worker重启丢状态）
    this._saveTrackerState();
  }

  /**
   * 结束当前段，生成段记录
   */
  _finalizeCurrentSegment() {
    if (!this.currentTabId || !this.segmentStart) return;

    const now = Date.now();
    const duration = now - this.segmentStart;

    // 过短段丢弃
    if (duration >= MIN_SEGMENT_MS) {
      const segment = {
        url: this.currentUrl,
        domain: this.currentDomain,
        title: this.currentTitle,
        startTime: this.segmentStart,
        endTime: now,
        duration: duration,
        category: getCategoryForDomain(this.currentDomain)
      };
      this.pendingSegments.push(segment);
      console.log(`[TabTracker] Segment: ${this.currentDomain} (${Math.round(duration / 1000)}s)`);
    }

    // 重置当前段
    this.currentTabId = null;
    this.currentUrl = null;
    this.currentDomain = null;
    this.currentTitle = null;
    this.segmentStart = null;

    // 保存到 chrome.storage.local（缓冲）
    this._saveSegmentsToStorage();
    this._saveTrackerState();
  }

  /**
   * 将段数据保存到 chrome.storage.local
   */
  _saveSegmentsToStorage() {
    if (this.pendingSegments.length === 0) return;

    chrome.storage.local.get([STORAGE_KEY], (result) => {
      const existing = result[STORAGE_KEY] || [];
      const merged = existing.concat(this.pendingSegments);

      // 只保留最近2天的数据（安全缓冲）
      const twoDaysAgo = Date.now() - 2 * 24 * 60 * 60 * 1000;
      const trimmed = merged.filter(s => s.startTime >= twoDaysAgo);

      chrome.storage.local.set({ [STORAGE_KEY]: trimmed });
    });
  }

  /**
   * 持久化追踪器状态（防止MV3 Service Worker重启）
   */
  _saveTrackerState() {
    const state = {
      currentTabId: this.currentTabId,
      currentUrl: this.currentUrl,
      currentDomain: this.currentDomain,
      currentTitle: this.currentTitle,
      segmentStart: this.segmentStart,
      isWindowFocused: this.isWindowFocused,
      isUserIdle: this.isUserIdle,
      savedAt: Date.now()
    };
    chrome.storage.local.set({ [TRACKER_STATE_KEY]: state });
  }

  /**
   * 从 chrome.storage.local 加载未flush的段
   */
  _loadPendingSegments() {
    chrome.storage.local.get([STORAGE_KEY], (result) => {
      const stored = result[STORAGE_KEY] || [];
      if (stored.length > 0) {
        this.pendingSegments = stored;
        console.log(`[TabTracker] Loaded ${stored.length} pending segments from storage`);
      }
    });

    // 恢复追踪器状态
    chrome.storage.local.get([TRACKER_STATE_KEY], (result) => {
      const state = result[TRACKER_STATE_KEY];
      if (state && state.segmentStart) {
        // 如果上次保存时间在5分钟内，恢复状态
        const elapsed = Date.now() - state.savedAt;
        if (elapsed < 5 * 60 * 1000) {
          this.currentTabId = state.currentTabId;
          this.currentUrl = state.currentUrl;
          this.currentDomain = state.currentDomain;
          this.currentTitle = state.currentTitle;
          this.segmentStart = state.segmentStart;
          this.isWindowFocused = state.isWindowFocused;
          this.isUserIdle = state.isUserIdle;
          console.log('[TabTracker] Restored tracker state from storage');
        } else {
          // 超过5分钟，视为旧段已失效，finalize它
          this.currentTabId = state.currentTabId;
          this.currentUrl = state.currentUrl;
          this.currentDomain = state.currentDomain;
          this.currentTitle = state.currentTitle;
          this.segmentStart = state.segmentStart;
          this._finalizeCurrentSegment();
        }
      }
    });
  }

  /**
   * 将段数据flush到Native Host，写入每日活动文件
   */
  _flushToNativeHost() {
    if (this.pendingSegments.length === 0) {
      console.log('[TabTracker] No segments to flush');
      return;
    }

    const segmentsToFlush = [...this.pendingSegments];
    this.pendingSegments = [];

    // 先结束当前段（确保最新数据也flush）
    this._finalizeCurrentSegment();

    const message = {
      action: 'track_flush',
      segments: segmentsToFlush,
      timestamp: new Date().toISOString()
    };

    this._sendToNativeHost(message, (success) => {
      if (success) {
        // flush成功，清除storage中已flush的段
        chrome.storage.local.get([STORAGE_KEY], (result) => {
          const stored = result[STORAGE_KEY] || [];
          // 移除已flush的段（通过startTime匹配）
          const flushedStartTimes = new Set(segmentsToFlush.map(s => s.startTime));
          const remaining = stored.filter(s => !flushedStartTimes.has(s.startTime));
          chrome.storage.local.set({ [STORAGE_KEY]: remaining });
        });
        console.log(`[TabTracker] Flushed ${segmentsToFlush.length} segments to native host`);
      } else {
        // flush失败，把段放回去，下次重试
        this.pendingSegments = segmentsToFlush.concat(this.pendingSegments);
        this._saveSegmentsToStorage();
        console.warn('[TabTracker] Flush failed, segments kept for retry');
      }
    });
  }

  /**
   * 发送消息到Native Host
   */
  _sendToNativeHost(message, callback) {
    if (!this.nativePort) {
      if (callback) callback(false);
      return;
    }

    try {
      // 临时监听器来获取响应
      const tempListener = (response) => {
        if (response && response.status === 'ok') {
          if (callback) callback(true);
        } else {
          if (callback) callback(false);
        }
        this.nativePort.onMessage.removeListener(tempListener);
      };

      this.nativePort.onMessage.addListener(tempListener);
      this.nativePort.postMessage(message);
    } catch (e) {
      console.error('[TabTracker] Failed to send to native host:', e);
      if (callback) callback(false);
    }
  }

  /**
   * 请求报告数据（由dashboard调用，通过background.js转发）
   */
  requestReport(startDate, endDate, callback) {
    const message = {
      action: 'track_report',
      startDate: startDate,  // "YYYY-MM-DD"
      endDate: endDate       // "YYYY-MM-DD"
    };

    this._sendToNativeHost(message, (success) => {
      // 注意：报告数据通过nativePort.onMessage返回，需要特殊处理
      // 在background.js的消息转发中处理
    });
  }

  // ========== 工具方法 ==========

  /**
   * 从URL提取域名
   */
  _extractDomain(url) {
    try {
      return new URL(url).hostname;
    } catch {
      return '';
    }
  }

  /**
   * 判断是否为系统URL（不追踪）
   */
  _isSystemUrl(url) {
    return url.startsWith('chrome://') ||
           url.startsWith('chrome-extension://') ||
           url.startsWith('edge://') ||
           url.startsWith('about:') ||
           url.startsWith('devtools://');
  }

  /**
   * 获取追踪统计（用于popup显示）
   */
  getTodayStats() {
    return new Promise((resolve) => {
      chrome.storage.local.get([STORAGE_KEY], (result) => {
        const segments = result[STORAGE_KEY] || [];
        const today = new Date().toISOString().slice(0, 10);
        const todayStart = new Date(today).getTime();

        const todaySegments = segments.filter(s => s.startTime >= todayStart);
        const totalMs = todaySegments.reduce((sum, s) => sum + s.duration, 0);
        const domains = {};
        todaySegments.forEach(s => {
          domains[s.domain] = (domains[s.domain] || 0) + s.duration;
        });

        const topDomain = Object.entries(domains).sort((a, b) => b[1] - a[1])[0];

        resolve({
          totalMs: totalMs,
          segmentCount: todaySegments.length,
          topDomain: topDomain ? topDomain[0] : null,
          topDomainMs: topDomain ? topDomain[1] : 0
        });
      });
    });
  }

  /**
   * 清除所有追踪数据
   */
  clearAllData() {
    this.pendingSegments = [];
    chrome.storage.local.remove([STORAGE_KEY, TRACKER_STATE_KEY]);
    console.log('[TabTracker] All tracking data cleared');
  }
}

// 全局实例
const tabTracker = new TabTracker();
