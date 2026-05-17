// TabSaver - Popup Script

document.addEventListener('DOMContentLoaded', () => {
  const connectionStatus = document.getElementById('connectionStatus');
  const tabCount = document.getElementById('tabCount');
  const lastSync = document.getElementById('lastSync');
  const btnSync = document.getElementById('btnSync');

  // 获取状态
  function refreshStatus() {
    chrome.runtime.sendMessage({ action: 'getStatus' }, (response) => {
      if (chrome.runtime.lastError || !response) {
        connectionStatus.textContent = '未连接';
        connectionStatus.className = 'status-value status-disconnected';
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

  refreshStatus();
});
