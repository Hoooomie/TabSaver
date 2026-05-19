// TabSaver - Background Service Worker
// 监控标签页变化，通过Native Messaging将数据同步到本地
// 集成 TabTracker 时间追踪功能

importScripts('tracker.js', 'categories.js');

const NATIVE_HOST_NAME = 'com.tabsaver.host';
const DEBOUNCE_MS = 1000; // 防抖：1秒内的多次变化合并为一次同步

let nativePort = null;
let syncTimer = null;
let currentMode = 'auto'; // 当前模式，从Native Host响应中获取

// ========== Native Messaging 连接管理 ==========

function connectNative() {
  try {
    nativePort = chrome.runtime.connectNative(NATIVE_HOST_NAME);

    nativePort.onMessage.addListener((response) => {
      console.log('[TabSaver] Native host response:', response);

      // 更新当前模式
      if (response.mode) {
        currentMode = response.mode;
        chrome.storage.local.set({ currentMode: response.mode });
      }

      // 转发 track_report 响应给 dashboard
      if (response._reportId) {
        chrome.runtime.sendMessage({
          action: 'track_report_response',
          reportId: response._reportId,
          data: response
        }).catch(() => {});
      }
    });

    nativePort.onDisconnect.addListener(() => {
      const error = chrome.runtime.lastError;
      console.log('[TabSaver] Native port disconnected:', error?.message || 'normal');
      nativePort = null;
      tabTracker.nativePort = null;
    });

    // 将端口共享给 tracker
    tabTracker.nativePort = nativePort;

    console.log('[TabSaver] Native messaging connected');

  } catch (e) {
    console.error('[TabSaver] Failed to connect native host:', e);
    nativePort = null;
  }
}

// ========== 标签页数据采集 ==========

async function collectAllTabs() {
  const tabs = await chrome.tabs.query({});
  return tabs
    .filter(tab => tab.url && !tab.url.startsWith('chrome://') && !tab.url.startsWith('chrome-extension://'))
    .map(tab => ({
      url: tab.url,
      title: tab.title || tab.url,
      favIconUrl: tab.favIconUrl || ''
    }));
}

// ========== 数据同步 ==========

async function syncTabsToNativeHost() {
  const tabs = await collectAllTabs();

  const message = {
    action: 'sync',
    timestamp: new Date().toISOString(),
    tabCount: tabs.length,
    tabs: tabs
  };

  // 备份到 chrome.storage.local
  chrome.storage.local.set({
    lastSync: message.timestamp,
    lastTabCount: tabs.length,
    lastTabs: tabs
  });

  // 发送到 Native Host（无论什么模式都发送，Native Host 根据模式决定是否保存）
  if (!nativePort) {
    connectNative();
  }

  if (nativePort) {
    try {
      nativePort.postMessage(message);
      console.log(`[TabSaver] Synced ${tabs.length} tabs to native host`);
    } catch (e) {
      console.error('[TabSaver] Failed to send to native host:', e);
      // 尝试重新连接
      connectNative();
      if (nativePort) {
        try {
          nativePort.postMessage(message);
        } catch (e2) {
          console.error('[TabSaver] Retry failed:', e2);
        }
      }
    }
  } else {
    console.warn('[TabSaver] Cannot sync: native host not connected');
  }
}

// 防抖同步
function debouncedSync() {
  if (syncTimer) clearTimeout(syncTimer);
  syncTimer = setTimeout(() => {
    syncTabsToNativeHost();
  }, DEBOUNCE_MS);
}

// ========== 事件监听 ==========

// 标签页创建
chrome.tabs.onCreated.addListener(() => {
  debouncedSync();
});

// 标签页更新（URL变化、标题变化等）
chrome.tabs.onUpdated.addListener((tabId, changeInfo) => {
  if (changeInfo.url || changeInfo.title || changeInfo.status === 'complete') {
    debouncedSync();
  }
});

// 标签页关闭
chrome.tabs.onRemoved.addListener(() => {
  debouncedSync();
});

// 标签页移动
chrome.tabs.onMoved.addListener(() => {
  debouncedSync();
});

// 标签页切换 - 不触发同步（但TabTracker已在tracker.js中独立监听）
chrome.tabs.onActivated.addListener(() => {});

// 窗口关闭 - 触发最终同步
chrome.windows.onRemoved.addListener(() => {
  syncTabsToNativeHost();
});

// Service Worker 启动时初始化
chrome.runtime.onStartup.addListener(() => {
  chrome.storage.local.get(['currentMode'], (result) => {
    if (result.currentMode) {
      currentMode = result.currentMode;
    }
    connectNative();
    syncTabsToNativeHost();
    // 启动时间追踪
    tabTracker.nativePort = nativePort;
    tabTracker.startTracking();
  });
});

// 扩展安装/更新时初始化
chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.local.get(['currentMode'], (result) => {
    if (result.currentMode) {
      currentMode = result.currentMode;
    }
    connectNative();
    syncTabsToNativeHost();
    // 启动时间追踪
    tabTracker.nativePort = nativePort;
    tabTracker.startTracking();
  });
});

// ========== 消息处理 ==========

// 接收来自popup和dashboard的消息
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === 'getStatus') {
    chrome.storage.local.get(['lastSync', 'lastTabCount', 'currentMode'], (result) => {
      sendResponse({
        connected: nativePort !== null,
        lastSync: result.lastSync || null,
        tabCount: result.lastTabCount || 0,
        mode: result.currentMode || currentMode
      });
    });
    return true; // 异步响应
  }

  if (message.action === 'syncNow') {
    syncTabsToNativeHost().then(() => {
      sendResponse({ success: true });
    });
    return true;
  }

  // TabTracker: 获取今日统计
  if (message.action === 'getTodayStats') {
    tabTracker.getTodayStats().then((stats) => {
      sendResponse(stats);
    });
    return true;
  }

  // TabTracker: 请求报告数据（来自dashboard）
  if (message.action === 'track_report') {
    if (!nativePort) {
      connectNative();
    }

    // 先 flush 待发送的段，确保最新数据写入 Native Host
    const doFlush = new Promise((resolve) => {
      if (tabTracker.pendingSegments.length > 0 && nativePort) {
        tabTracker._flushToNativeHost();
        // 给 flush 1秒时间完成
        setTimeout(resolve, 1000);
      } else {
        resolve();
      }
    });

    doFlush.then(() => {
      if (nativePort) {
        try {
          // 生成报告ID，用于匹配响应
          const reportId = 'rpt_' + Date.now();
          const reportMessage = {
            action: 'track_report',
            startDate: message.startDate,
            endDate: message.endDate,
            _reportId: reportId
          };
          nativePort.postMessage(reportMessage);

          // 设置一次性监听器等待响应
          const responseListener = (response) => {
            if (response._reportId === reportId) {
              nativePort.onMessage.removeListener(responseListener);

              // 如果 Native Host 没有持久化数据，用 chrome.storage.local 的段作为 fallback
              if (response.totalActiveMs === 0 && response.segmentCount === 0) {
                _mergeStorageFallback(response, message.startDate, message.endDate, sendResponse);
              } else {
                sendResponse(response);
              }
            }
          };
          nativePort.onMessage.addListener(responseListener);

          // 超时处理（10秒）
          setTimeout(() => {
            nativePort.onMessage.removeListener(responseListener);
            // 超时后也尝试 fallback
            _mergeStorageFallback(
              { status: 'ok', totalActiveMs: 0, segmentCount: 0 },
              message.startDate, message.endDate, sendResponse
            );
          }, 10000);

        } catch (e) {
          // 发送失败，尝试 fallback
          _mergeStorageFallback(
            { status: 'ok', totalActiveMs: 0, segmentCount: 0 },
            message.startDate, message.endDate, sendResponse
          );
        }
      } else {
        // Native Host 不可用，纯 storage fallback
        _mergeStorageFallback(
          { status: 'ok', totalActiveMs: 0, segmentCount: 0 },
          message.startDate, message.endDate, sendResponse
        );
      }
    });
    return true;
  }

  // TabTracker: 清除追踪数据
  if (message.action === 'clearTrackerData') {
    tabTracker.clearAllData();
    sendResponse({ success: true });
    return true;
  }
});

// ========== Storage Fallback 报告生成 ==========
// 当 Native Host 没有 activity 文件时，从 chrome.storage.local 读取段数据生成报告

function _mergeStorageFallback(nativeResponse, startDate, endDate, sendResponse) {
  const STORAGE_KEY = 'tracker_segments';

  chrome.storage.local.get([STORAGE_KEY], (result) => {
    const allSegments = result[STORAGE_KEY] || [];

    // 过滤日期范围内的段
    const startMs = new Date(startDate + 'T00:00:00').getTime();
    const endMs = new Date(endDate + 'T23:59:59.999').getTime();
    const filtered = allSegments.filter(s => s.startTime >= startMs && s.startTime <= endMs);

    if (filtered.length === 0) {
      // 真的没有数据，返回原始空响应
      nativeResponse.topDomains = nativeResponse.topDomains || [];
      nativeResponse.topCategories = nativeResponse.topCategories || [];
      nativeResponse.hourlyBuckets = nativeResponse.hourlyBuckets || new Array(24).fill(0);
      nativeResponse.mostActiveHour = -1;
      nativeResponse.focusScore = 0;
      sendResponse(nativeResponse);
      return;
    }

    // 从段数据计算报告
    const totalActiveMs = filtered.reduce((sum, s) => sum + (s.duration || 0), 0);
    const domainMs = {};
    const categoryMs = {};
    const hourlyBuckets = new Array(24).fill(0);

    filtered.forEach(seg => {
      const domain = seg.domain || 'unknown';
      const duration = seg.duration || 0;
      const category = seg.category || 'Other';

      domainMs[domain] = (domainMs[domain] || 0) + duration;
      categoryMs[category] = (categoryMs[category] || 0) + duration;

      const hour = new Date(seg.startTime).getHours();
      hourlyBuckets[hour] += duration;
    });

    const topDomains = Object.entries(domainMs)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 10)
      .map(([domain, ms]) => ({ domain, ms }));

    const topCategories = Object.entries(categoryMs)
      .sort((a, b) => b[1] - a[1])
      .map(([category, ms]) => ({ category, ms }));

    const mostActiveHour = hourlyBuckets.indexOf(Math.max(...hourlyBuckets));

    // 专注分数：综合"持续度"和"切换频率"两个维度
    // 维度1 - 持续度：按段时长加权计分（1min=30分, 2min=60分, 5min=100分, 指数曲线）
    // 维度2 - 稳定度：1 - (切换次数/总活跃分钟)，切换越少分越高
    let continuityScore = 0;
    filtered.forEach(s => {
      const durMin = (s.duration || 0) / 60000;
      // 指数曲线：1分钟约30分，2分钟约60分，5分钟100分
      continuityScore += (1 - Math.exp(-durMin / 1.5)) * (s.duration || 0);
    });
    const avgContinuity = totalActiveMs > 0 ? continuityScore / totalActiveMs * 100 : 0;

    const totalActiveMin = totalActiveMs / 60000;
    const switchPenalty = totalActiveMin > 0 ? Math.min(1, (filtered.length - 1) / totalActiveMin) : 1;
    const stabilityScore = (1 - switchPenalty) * 100;

    const focusScore = totalActiveMs > 0 ? Math.round(avgContinuity * 0.6 + stabilityScore * 0.4) : 0;

    sendResponse({
      status: 'ok',
      startDate: startDate,
      endDate: endDate,
      totalActiveMs: totalActiveMs,
      segmentCount: filtered.length,
      focusScore: focusScore,
      topDomains: topDomains,
      topCategories: topCategories,
      hourlyBuckets: hourlyBuckets,
      mostActiveHour: mostActiveHour,
      _source: 'storage_fallback'
    });
  });
}
