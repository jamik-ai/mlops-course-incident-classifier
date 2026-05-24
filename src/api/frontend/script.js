const API = window.API_BASE_URL || 'http://localhost:8000';
let ws = null;
let notificationCount = 0;

// ---- TABS ----
document.querySelectorAll('.nav-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('tab-' + btn.dataset.tab).classList.add('active');

    if (btn.dataset.tab === 'history') loadHistory();
    if (btn.dataset.tab === 'drift') loadFeatureFlags();
    if (btn.dataset.tab === 'experiments') loadExperiments();
    if (btn.dataset.tab === 'alerts') loadNotifications();
  });
});

// ---- FORECAST ----
document.getElementById('forecastForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const date = document.getElementById('date').value;
  if (!date) return;
  const loading = document.getElementById('loading');
  const result = document.getElementById('result');
  loading.style.display = 'block';
  result.style.display = 'none';
  try {
    const res = await fetch(API + '/api/forecast', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ date }) });
    const data = await res.json();
    if (res.ok) {
      displayForecast(result, data);
      refreshDriftFlags();
    } else {
      result.innerHTML = '<p class="error">Ошибка: ' + (data.detail || 'Неизвестная ошибка') + '</p>';
      result.style.display = 'block';
    }
  } catch (err) {
    result.innerHTML = '<p class="error">Ошибка соединения с backend</p>';
    result.style.display = 'block';
  } finally {
    loading.style.display = 'none';
  }
});

function displayForecast(container, data) {
  const vals = data.hourly_forecast.map(v => Math.round(v));
  const mx = Math.max(...vals);
  const mn = Math.min(...vals);
  const av = (vals.reduce((a, b) => a + b, 0) / vals.length).toFixed(2);
  const tot = vals.reduce((a, b) => a + b, 0);
  const pk = vals.indexOf(mx);
  let rows = '';
  vals.forEach((v, h) => { rows += '<tr><td>' + pad(h) + ':00</td><td>' + v + '</td></tr>'; });
  container.innerHTML =
    '<h2>Прогноз на ' + formatDate(data.date) + '</h2>' +
    '<div class="metrics">' +
    '<div class="metric"><span>Максимум</span><strong>' + mx + '</strong><small>' + pad(pk) + ':00</small></div>' +
    '<div class="metric"><span>Минимум</span><strong>' + mn + '</strong></div>' +
    '<div class="metric"><span>Среднее</span><strong>' + av + '</strong></div>' +
    '<div class="metric"><span>Всего</span><strong>' + tot + '</strong></div>' +
    '</div>' +
    '<table><thead><tr><th>Час</th><th>Прогноз</th></tr></thead><tbody>' + rows + '</tbody></table>';
  container.style.display = 'block';
}

// ---- DRIFT FLAGS ----
document.getElementById('refreshFlagsBtn').addEventListener('click', refreshDriftFlags);

async function refreshDriftFlags() {
  try {
    const res = await fetch(API + '/api/drift/status');
    const d = await res.json();
    setFlag('flag-data', d.data_drift_detected);
    setFlag('flag-target', d.target_drift_detected);
    setFlag('flag-concept', d.concept_drift_detected);
    document.getElementById('flag-last-check').textContent = d.last_check_at || '—';
    loadFeatureFlags();
  } catch (_) { /* ignore */ }
}

function setFlag(id, detected) {
  const el = document.getElementById(id);
  el.className = 'flag-badge ' + (detected === true ? 'critical' : detected === false ? 'ok' : 'unknown');
  el.textContent = detected === true ? '⚠ ОБНАРУЖЕН' : detected === false ? '✓ Норма' : '—';
}

async function loadFeatureFlags() {
  try {
    const res = await fetch(API + '/api/drift/status');
    const d = await res.json();
    const wrap = document.getElementById('featureFlagsTable');
    if (!d.feature_flags || !d.feature_flags.length) { wrap.innerHTML = '<p class="empty-state">Нет данных. Запустите проверку drift.</p>'; return; }
    let html = '<table><thead><tr><th>Признак</th><th>PSI</th><th>KS p-val</th><th>JS dist</th><th>Drift</th></tr></thead><tbody>';
    d.feature_flags.forEach(f => {
      html += '<tr><td>' + f.feature + '</td><td>' + f.psi.toFixed(4) + '</td><td>' + f.ks_pvalue.toFixed(4) + '</td><td>' + f.js_distance.toFixed(4) + '</td><td class="' + (f.drift_detected ? 'text-red' : 'text-green') + '">' + (f.drift_detected ? 'ДА' : 'Нет') + '</td></tr>';
    });
    html += '</tbody></table>';
    wrap.innerHTML = html;
  } catch (_) { /* ignore */ }
}

// ---- DRIFT OPS BUTTONS ----
document.getElementById('driftButton').addEventListener('click', async () => {
  const st = document.getElementById('opsStatus');
  st.textContent = 'Запускаю drift check...';
  try {
    const res = await fetch(API + '/api/drift/run', { method: 'POST' });
    const data = await res.json();
    st.textContent = res.ok ? JSON.stringify(data, null, 2) : (data.detail || 'Ошибка drift check');
    refreshDriftFlags();
    loadNotifications();
  } catch (err) {
    st.textContent = 'Ошибка соединения с backend';
  }
});

document.getElementById('reportButton').addEventListener('click', () => {
  window.open(API + '/api/drift/report', '_blank');
});

document.getElementById('retrainButton').addEventListener('click', async () => {
  const st = document.getElementById('opsStatus');
  st.textContent = 'Запускаю retraining...';
  try {
    const res = await fetch(API + '/api/retrain', { method: 'POST' });
    const data = await res.json();
    st.textContent = res.ok ? data.message : (data.detail || 'Ошибка retraining');
    loadNotifications();
  } catch (err) {
    st.textContent = 'Ошибка соединения с backend';
  }
});

// ---- PREDICTION HISTORY ----
async function loadHistory() {
  const wrap = document.getElementById('historyTableWrap');
  wrap.innerHTML = '<p class="loading">Загрузка...</p>';
  try {
    const res = await fetch(API + '/api/predictions/history?limit=50');
    const entries = await res.json();
    if (!entries.length) { wrap.innerHTML = '<p class="empty-state">Пока нет предсказаний.</p>'; return; }
    let html = '<table><thead><tr><th>Время</th><th>Дата</th><th>Мин</th><th>Макс</th><th>Среднее</th><th>Всего</th></tr></thead><tbody>';
    entries.forEach(e => {
      const v = e.hourly_forecast.map(x => Math.round(x));
      const mn = Math.min(...v);
      const mx = Math.max(...v);
      const av = (v.reduce((a, b) => a + b, 0) / v.length).toFixed(1);
      const tot = v.reduce((a, b) => a + b, 0);
      html += '<tr><td>' + new Date(e.timestamp).toLocaleTimeString('ru-RU') + '</td><td>' + e.date + '</td><td>' + mn + '</td><td>' + mx + '</td><td>' + av + '</td><td>' + tot + '</td></tr>';
    });
    html += '</tbody></table>';
    wrap.innerHTML = html;
  } catch (_) {
    wrap.innerHTML = '<p class="error">Ошибка загрузки истории</p>';
  }
};

// ---- NOTIFICATIONS ----
async function loadNotifications() {
  try {
    const res = await fetch(API + '/api/notifications?limit=100');
    const alerts = await res.json();
    const wrap = document.getElementById('alertsList');
    const badge = document.getElementById('alertBadge');
    notificationCount = alerts.length;
    badge.textContent = notificationCount;
    badge.classList.toggle('hidden', notificationCount === 0);

    if (!alerts.length) { wrap.innerHTML = '<p class="empty-state">Нет уведомлений.</p>'; return; }
    let html = '';
    alerts.forEach(a => {
      const sevClass = a.severity === 'critical' ? 'severity-critical' : a.severity === 'warning' ? 'severity-warning' : 'severity-info';
      html += '<div class="alert-item ' + sevClass + '">' +
        '<div class="alert-left"><span class="alert-sev">' + a.severity.toUpperCase() + '</span><span class="alert-type">' + a.alert_type + '</span></div>' +
        '<div class="alert-msg">' + a.message + '</div>' +
        '<div class="alert-ts">' + new Date(a.timestamp).toLocaleString('ru-RU') + '</div>' +
        '</div>';
    });
    wrap.innerHTML = html;
  } catch (_) { /* ignore */ }
}

document.getElementById('clearAlertsBtn').addEventListener('click', async () => {
  await fetch(API + '/api/notifications/clear', { method: 'DELETE' });
  loadNotifications();
});

// ---- EXPERIMENTS ----
document.getElementById('refreshExpBtn').addEventListener('click', loadExperiments);

async function loadExperiments() {
  const errEl = document.getElementById('expErrors');
  const loadEl = document.getElementById('expLoading');
  const namesEl = document.getElementById('expNames');
  const runsEl = document.getElementById('expRuns');
  errEl.textContent = '';
  loadEl.style.display = 'block';
  namesEl.innerHTML = '';
  runsEl.innerHTML = '';
  try {
    const res = await fetch(API + '/api/mlflow/experiments');
    if (!res.ok) throw new Error(res.statusText);
    const data = await res.json();

    if (data.experiments.length) {
      namesEl.innerHTML = '<h3>Эксперименты (' + data.experiments.length + ')</h3><div class="tag-list">' +
        data.experiments.map(n => '<span class="tag">' + n + '</span>').join('') + '</div>';
    }

    if (!data.runs.length) { runsEl.innerHTML = '<p class="empty-state">Нет записей о запусках.</p>'; }
    else {
      let grouped = {};
      data.runs.forEach(r => {
        if (!grouped[r.experiment_name]) grouped[r.experiment_name] = [];
        grouped[r.experiment_name].push(r);
      });

      let html = '';
      Object.keys(grouped).forEach(expName => {
        html += '<h3>' + expName + ' (' + grouped[expName].length + ')</h3>';
        html += '<table class="exp-table"><thead><tr><th>Run ID</th><th>Name</th><th>Status</th><th>Start</th><th>MAE</th><th>RMSE</th><th>Params</th></tr></thead><tbody>';
        grouped[expName].forEach(r => {
          const mae = r.metrics.find(m => m.key === 'mae');
          const rmse = r.metrics.find(m => m.key === 'rmse');
          const paramsStr = r.params.slice(0, 3).map(p => p.key + '=' + p.value).join(', ');
          html += '<tr>' +
            '<td class="run-id">' + r.run_id.substring(0, 8) + '</td>' +
            '<td>' + (r.run_name || '—') + '</td>' +
            '<td class="' + (r.status === 'FINISHED' ? 'text-green' : 'text-red') + '">' + r.status + '</td>' +
            '<td>' + new Date(r.start_time).toLocaleString('ru-RU') + '</td>' +
            '<td>' + (mae ? mae.value.toFixed(3) : '—') + '</td>' +
            '<td>' + (rmse ? rmse.value.toFixed(3) : '—') + '</td>' +
            '<td>' + paramsStr + '</td>' +
            '</tr>';
        });
        html += '</tbody></table>';
      });
      runsEl.innerHTML = html;
    }
  } catch (err) {
    errEl.textContent = 'Ошибка загрузки MLflow: ' + err.message;
  } finally {
    loadEl.style.display = 'none';
  }
}

// ---- WEBSOCKET ----
function connectWS() {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = window.location.host || 'localhost:8000';
  ws = new WebSocket(proto + '//' + host + '/ws/drift-alerts');

  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    showToast(msg.message, msg.severity);
    loadNotifications();
    if (msg.type === 'drift_alert' || msg.type === 'retrain_done') {
      refreshDriftFlags();
    }
  };

  ws.onclose = () => { setTimeout(connectWS, 5000); };
}

function showToast(text, severity) {
  const toast = document.getElementById('toast');
  toast.textContent = text;
  toast.className = 'toast toast-' + (severity || 'info');
  toast.classList.remove('hidden');
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => toast.classList.add('hidden'), 6000);
}

// ---- INIT ----
(function init() {
  const today = new Date().toISOString().split('T', 1)[0];
  document.getElementById('date').value = today;
  refreshDriftFlags();
  connectWS();
})();

function pad(n) { return n < 10 ? '0' + n : '' + n; }
function formatDate(ds) {
  const d = new Date(ds);
  return d.toLocaleDateString('ru-RU', { year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' });
}