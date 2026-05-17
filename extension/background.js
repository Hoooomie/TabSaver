// TabSaver - Background Service Worker
// 监控标签页变化，通过Native Messaging将数据同步到本地

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
    });

    nativePort.onDisconnect.addListener(() => {
      const error = chrome.runtime.lastError;
      console.log('[TabSaver] Native port disconnected:', error?.message || 'normal');
      nativePort = null;
    });

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

// 标签页切换 - 不触发同步
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
  });
});

// 接收来自popup的消息
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
});
