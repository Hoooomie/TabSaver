// TabSaver - Dashboard Logic
// 专注力报告页面的数据获取与Chart.js渲染

// ========== 状态管理 ==========

let currentDate = new Date();
let viewMode = 'day'; // 'day' | 'week'
let hourlyChart = null;
let topSitesChart = null;
let categoryChart = null;

// 分类颜色映射
const CATEGORY_COLORS = {
  'Development': '#1a73e8',
  'Social':      '#ea4335',
  'Communication': '#f9ab00',
  'Entertainment': '#34a853',
  'News':        '#9334e6',
  'Work':        '#e8710a',
  'Shopping':    '#12b5cb',
  'Learning':    '#7baaf7',
  'Other':       '#9aa0a6'
};

// ========== 初始化 ==========

document.addEventListener('DOMContentLoaded', () => {
  initControls();
  loadData();
});

function initControls() {
  document.getElementById('btnDay').addEventListener('click', () => setViewMode('day'));
  document.getElementById('btnWeek').addEventListener('click', () => setViewMode('week'));
  document.getElementById('btnPrev').addEventListener('click', () => navigateDate(-1));
  document.getElementById('btnNext').addEventListener('click', () => navigateDate(1));
  document.getElementById('btnToday').addEventListener('click', () => {
    currentDate = new Date();
    loadData();
  });
  document.getElementById('btnClearData').addEventListener('click', clearData);
}

function setViewMode(mode) {
  viewMode = mode;
  document.getElementById('btnDay').classList.toggle('active', mode === 'day');
  document.getElementById('btnWeek').classList.toggle('active', mode === 'week');
  document.getElementById('btnPrev').textContent = mode === 'day' ? '\u2190 前一天' : '\u2190 前一周';
  document.getElementById('btnNext').textContent = mode === 'day' ? '后一天 \u2192' : '后一周 \u2192';
  loadData();
}

function navigateDate(delta) {
  if (viewMode === 'day') {
    currentDate.setDate(currentDate.getDate() + delta);
  } else {
    currentDate.setDate(currentDate.getDate() + delta * 7);
  }
  loadData();
}

// ========== 数据加载 ==========

function loadData() {
  updateDateLabel();

  const { startDate, endDate } = getDateRange();
  const startDateStr = formatDate(startDate);
  const endDateStr = formatDate(endDate);

  // 向background.js请求报告数据
  chrome.runtime.sendMessage({
    action: 'track_report',
    startDate: startDateStr,
    endDate: endDateStr
  }, (response) => {
    if (chrome.runtime.lastError || !response || response.status === 'error') {
      showEmptyState(response?.message || '无法连接到Native Host');
      return;
    }
    renderDashboard(response);
  });
}

function getDateRange() {
  if (viewMode === 'day') {
    const d = new Date(currentDate);
    return { startDate: d, endDate: d };
  } else {
    // 周视图：当前日期所在周（周一到周日）
    const d = new Date(currentDate);
    const day = d.getDay();
    const monday = new Date(d);
    monday.setDate(d.getDate() - (day === 0 ? 6 : day - 1));
    const sunday = new Date(monday);
    sunday.setDate(monday.getDate() + 6);
    return { startDate: monday, endDate: sunday };
  }
}

function formatDate(date) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

function updateDateLabel() {
  const { startDate, endDate } = getDateRange();
  if (viewMode === 'day') {
    const weekDays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];
    const wd = weekDays[startDate.getDay()];
    document.getElementById('dateLabel').textContent =
      `${formatDate(startDate)} ${wd}`;
  } else {
    document.getElementById('dateLabel').textContent =
      `${formatDate(startDate)} ~ ${formatDate(endDate)}`;
  }
}

// ========== 渲染 ==========

function renderDashboard(data) {
  renderStats(data);
  renderHourlyChart(data);
  renderTopSitesChart(data);
  renderCategoryChart(data);
}

function renderStats(data) {
  // 总活跃时长
  document.getElementById('statTotal').textContent = formatDuration(data.totalActiveMs || 0);

  // 最常访问
  const topDomain = (data.topDomains || [])[0];
  document.getElementById('statTopDomain').textContent =
    topDomain ? `${topDomain.domain} (${formatDuration(topDomain.ms)})` : '-';

  // 最活跃时段
  const peakHour = data.mostActiveHour;
  document.getElementById('statPeakHour').textContent =
    peakHour >= 0 ? `${String(peakHour).padStart(2, '0')}:00 - ${String(peakHour).padStart(2, '0')}:59` : '-';

  // 专注分数
  const score = data.focusScore || 0;
  const scoreEl = document.getElementById('statFocusScore');
  scoreEl.textContent = `${score}/100`;
  scoreEl.style.color = score >= 70 ? '#34a853' : score >= 40 ? '#f9ab00' : '#ea4335';
}

function renderHourlyChart(data) {
  const ctx = document.getElementById('hourlyChart').getContext('2d');

  if (hourlyChart) hourlyChart.destroy();

  const buckets = data.hourlyBuckets || new Array(24).fill(0);
  const labels = Array.from({ length: 24 }, (_, i) => `${String(i).padStart(2, '0')}:00`);

  // 将毫秒转为分钟用于显示
  const minutes = buckets.map(ms => Math.round(ms / 60000));

  hourlyChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: '活跃时间 (分钟)',
        data: minutes,
        backgroundColor: minutes.map(m =>
          m > 30 ? '#1a73e8' : m > 10 ? '#7baaf7' : '#e8f0fe'
        ),
        borderRadius: 4,
        borderSkipped: false
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => `${ctx.raw} 分钟`
          }
        }
      },
      scales: {
        y: {
          beginAtZero: true,
          title: { display: true, text: '分钟' },
          grid: { color: '#f0f0f0' }
        },
        x: {
          grid: { display: false },
          ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 12 }
        }
      }
    }
  });
}

function renderTopSitesChart(data) {
  const ctx = document.getElementById('topSitesChart').getContext('2d');

  if (topSitesChart) topSitesChart.destroy();

  const domains = data.topDomains || [];
  const labels = domains.map(d => d.domain);
  const durations = domains.map(d => Math.round(d.ms / 60000));

  topSitesChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: '活跃时间 (分钟)',
        data: durations,
        backgroundColor: '#1a73e8',
        borderRadius: 4,
        borderSkipped: false
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => `${ctx.raw} 分钟`
          }
        }
      },
      scales: {
        x: {
          beginAtZero: true,
          title: { display: true, text: '分钟' },
          grid: { color: '#f0f0f0' }
        },
        y: {
          grid: { display: false },
          ticks: { font: { size: 11 } }
        }
      }
    }
  });
}

function renderCategoryChart(data) {
  const ctx = document.getElementById('categoryChart').getContext('2d');

  if (categoryChart) categoryChart.destroy();

  const categories = data.topCategories || [];
  const labels = categories.map(c => c.category);
  const durations = categories.map(c => c.ms);
  const colors = labels.map(l => CATEGORY_COLORS[l] || '#9aa0a6');

  categoryChart = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: labels,
      datasets: [{
        data: durations,
        backgroundColor: colors,
        borderWidth: 2,
        borderColor: '#fff'
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'right',
          labels: { padding: 12, font: { size: 12 } }
        },
        tooltip: {
          callbacks: {
            label: (ctx) => {
              const total = ctx.dataset.data.reduce((a, b) => a + b, 0);
              const pct = total > 0 ? Math.round(ctx.raw / total * 100) : 0;
              return `${ctx.label}: ${formatDuration(ctx.raw)} (${pct}%)`;
            }
          }
        }
      }
    }
  });
}

// ========== 工具函数 ==========

function formatDuration(ms) {
  if (!ms || ms <= 0) return '0分钟';
  const totalMin = Math.floor(ms / 60000);
  const hours = Math.floor(totalMin / 60);
  const mins = totalMin % 60;
  if (hours > 0) {
    return mins > 0 ? `${hours}小时${mins}分钟` : `${hours}小时`;
  }
  return `${mins}分钟`;
}

function showEmptyState(msg) {
  document.querySelectorAll('.chart-card').forEach(el => {
    el.innerHTML = `<div class="empty-state"><p>${msg || '暂无数据'}</p><small>浏览网页后，追踪数据会自动记录</small></div>`;
  });
  document.getElementById('statTotal').textContent = '-';
  document.getElementById('statTopDomain').textContent = '-';
  document.getElementById('statPeakHour').textContent = '-';
  document.getElementById('statFocusScore').textContent = '-';
}

function clearData() {
  if (!confirm('确定要清除所有追踪数据吗？此操作不可撤销。')) return;

  chrome.runtime.sendMessage({ action: 'clearTrackerData' }, (response) => {
    if (response && response.success) {
      showEmptyState('数据已清除');
    } else {
      alert('清除失败，请重试');
    }
  });
}
