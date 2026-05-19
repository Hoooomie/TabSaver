// TabSaver - Popup Script

document.addEventListener('DOMContentLoaded', () => {
  const connectionStatus = document.getElementById('connectionStatus');
  const modeStatus = document.getElementById('modeStatus');
  const tabCount = document.getElementById('tabCount');
  const lastSync = document.getElementById('lastSync');
  const btnSync = document.getElementById('btnSync');
  const btnTracker = document.getElementById('btnTracker');
  const tipText = document.getElementById('tipText');
  const todayActive = document.getElementById('todayActive');
  const todayTopDomain = document.getElementById('todayTopDomain');

  // 获取状态
  function refreshStatus() {
    chrome.runtime.sendMessage({ action: 'getStatus' }, (response) => {
      if (chrome.runtime.lastError || !response) {
        connectionStatus.textContent = '未连接';
        connectionStatus.className = 'status-value status-disconnected';
        modeStatus.textContent = '-';
        tabCount.textContent = '-';
        lastSync.textContent = '-';
        return;
      }

      if (response.connected) {
        connectionStatus.textContent = '已连接';
        connectionStatus.className = 'status-value status-connected';
      } else {
        connectionStatus.textContent = '未连接';
        connectionStatus.className = 'status-value status-disconnected';
      }

      // 显示当前模式
      const mode = response.mode || 'auto';
      if (mode === 'manual') {
        modeStatus.textContent = '手动';
        modeStatus.className = 'status-value mode-manual';
        tipText.innerHTML = '手动模式：标签页不会自动保存。<br>请在桌面端应用中点击"保存当前标签页"。';
      } else {
        modeStatus.textContent = '自动';
        modeStatus.className = 'status-value mode-auto';
        tipText.innerHTML = '标签页数据会在每次变化时自动同步。<br>关闭Chrome时，所有标签页将被保存到本地。';
      }

      tabCount.textContent = response.tabCount || '0';

      if (response.lastSync) {
        const date = new Date(response.lastSync);
        const hours = date.getHours().toString().padStart(2, '0');
        const mins = date.getMinutes().toString().padStart(2, '0');
        const secs = date.getSeconds().toString().padStart(2, '0');
        lastSync.textContent = `${hours}:${mins}:${secs}`;
      } else {
        lastSync.textContent = '-';
      }
    });

    // 获取今日追踪统计
    refreshTrackerStats();
  }

  // 获取今日追踪统计
  function refreshTrackerStats() {
    chrome.runtime.sendMessage({ action: 'getTodayStats' }, (response) => {
      if (chrome.runtime.lastError || !response) {
        todayActive.textContent = '-';
        todayTopDomain.textContent = '-';
        return;
      }

      // 格式化时长
      const totalMin = Math.floor((response.totalMs || 0) / 60000);
      const hours = Math.floor(totalMin / 60);
      const mins = totalMin % 60;
      todayActive.textContent = hours > 0 ? `${hours}h${mins}m` : `${mins}m`;

      // 最常访问域名
      todayTopDomain.textContent = response.topDomain || '-';
    });
  }

  // 立即同步按钮
  btnSync.addEventListener('click', () => {
    btnSync.textContent = '同步中...';
    btnSync.disabled = true;

    chrome.runtime.sendMessage({ action: 'syncNow' }, (response) => {
      if (chrome.runtime.lastError || !response) {
        btnSync.textContent = '同步失败';
        setTimeout(() => {
          btnSync.textContent = '立即同步';
          btnSync.disabled = false;
        }, 2000);
        return;
      }

      btnSync.textContent = '同步成功!';
      setTimeout(() => {
        btnSync.textContent = '立即同步';
        btnSync.disabled = false;
        refreshStatus();
      }, 1000);
    });
  });

  // 查看专注力报告按钮
  btnTracker.addEventListener('click', () => {
    chrome.tabs.create({ url: chrome.runtime.getURL('dashboard/dashboard.html') });
  });

  refreshStatus();
});
