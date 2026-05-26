const API_BASE_URL = window.API_BASE_URL || 'http://localhost:8000';

function showToast(title, msg = '', type = 'info', duration = 6000) {
  const icons = { success: '✅', error: '❌', info: 'ℹ️' };
  const container = document.getElementById('toastContainer');
  const toast = document.createElement('div');
  toast.className = `toast toast--${type}`;
  toast.innerHTML = `
    <span class="toast__icon">${icons[type] || 'ℹ️'}</span>
    <div class="toast__body">
      <div class="toast__title">${title}</div>
      ${msg ? `<div class="toast__msg">${msg}</div>` : ''}
    </div>
    <button class="toast__close" onclick="this.closest('.toast').remove()">✕</button>
  `;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(40px)';
    setTimeout(() => toast.remove(), 400);
  }, duration);
}

function sendBrowserNotification(title, body) {
  if (!('Notification' in window)) return;
  if (Notification.permission === 'granted') {
    new Notification(title, { body });
  } else if (Notification.permission !== 'denied') {
    Notification.requestPermission().then(p => {
      if (p === 'granted') new Notification(title, { body });
    });
  }
}
const resultDiv = document.getElementById('result');
const driftResultDiv = document.getElementById('driftResult');
const loadingDiv = document.getElementById('loading');
const opsStatus = document.getElementById('opsStatus');
const syntheticInfo = document.getElementById('syntheticInfo');
const modelResult = document.getElementById('modelResult');
let lastReportUrl = null;

async function loadSyntheticInfo() {
  try {
    const resp = await fetch(`${API_BASE_URL}/api/synthetic/info`);
    if (!resp.ok) return;
    const data = await resp.json();
    if (!data.exists) {
      syntheticInfo.textContent = 'Текущие данные: отсутствуют (будут сгенерированы автоматически при drift check)';
    } else {
      const age = data.stale ? ' — устарели!' : '';
      const dt = data.generated_at ? new Date(data.generated_at).toLocaleString('ru-RU') : '?';
      syntheticInfo.textContent = `Текущие данные: ${data.rows} строк, обновлено ${dt}${age}`;
      syntheticInfo.style.color = data.stale ? '#c0392b' : '#888';
    }
  } catch (_) { /* ignore */ }
}

loadSyntheticInfo();

if ('Notification' in window && Notification.permission === 'default') {
  Notification.requestPermission();
}

document.getElementById('generateSyntheticButton').addEventListener('click', async () => {
  opsStatus.textContent = 'Генерирую синтетические данные...';
  try {
    const resp = await fetch(`${API_BASE_URL}/api/synthetic/generate`, { method: 'POST' });
    const data = await resp.json();
    if (resp.ok) {
      opsStatus.textContent = `Синтетика сгенерирована: ${data.rows} строк`;
      await loadSyntheticInfo();
    } else {
      opsStatus.textContent = data.detail || 'Ошибка генерации данных';
    }
  } catch (error) {
    opsStatus.textContent = 'Ошибка соединения с backend';
  }
});

document.getElementById('forecastForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const date = document.getElementById('date').value;
  if (!date) return showError(resultDiv, 'Пожалуйста, выберите дату');
  loadingDiv.style.display = 'block';
  resultDiv.style.display = 'none';
  try {
    const response = await fetch(`${API_BASE_URL}/api/forecast`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ date }) });
    const data = await response.json();
    response.ok ? displayForecast(resultDiv, data) : showError(resultDiv, data.detail || 'Ошибка при получении прогноза');
  } catch (error) {
    showError(resultDiv, 'Ошибка соединения с backend');
  } finally {
    loadingDiv.style.display = 'none';
  }
});

document.getElementById('driftButton').addEventListener('click', async () => {
  opsStatus.textContent = 'Запускаю drift check...';
  driftResultDiv.innerHTML = '';
  try {
    const response = await fetch(`${API_BASE_URL}/api/drift/run`, { method: 'POST' });
    const data = await response.json();
    if (response.ok) {
      opsStatus.textContent = 'Drift-проверка завершена';
      displayDriftResult(data);
    } else {
      opsStatus.textContent = data.detail || 'Ошибка drift check';
    }
  } catch (error) {
    opsStatus.textContent = 'Ошибка соединения с backend';
  }
});

document.getElementById('reportButton').addEventListener('click', () => {
  const url = lastReportUrl || `${API_BASE_URL}/api/drift/report`;
  window.open(url, '_blank');
});

// Download report button
const dlBtn = document.getElementById('downloadReportButton');
if (dlBtn) {
  dlBtn.addEventListener('click', async () => {
    const url = lastReportUrl || `${API_BASE_URL}/api/drift/report`;
    try {
      const resp = await fetch(url);
      const ct = resp.headers.get('content-type') || '';
      if (ct.includes('text/html')) {
        const text = await resp.text();
        const blob = new Blob([text], { type: 'text/html' });
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = 'drift_report.html';
        document.body.appendChild(a);
        a.click();
        a.remove();
      } else {
        const json = await resp.json();
        const blob = new Blob([JSON.stringify(json, null, 2)], { type: 'application/json' });
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = 'drift_report.json';
        document.body.appendChild(a);
        a.click();
        a.remove();
      }
    } catch (err) {
      alert('Скачать отчёт не удалось');
    }
  });
}

document.getElementById('retrainButton').addEventListener('click', async () => {
  opsStatus.textContent = 'Запускаю retraining...';
  try {
    const response = await fetch(`${API_BASE_URL}/api/retrain`, { method: 'POST' });
    const data = await response.json();
    if (!response.ok) {
      opsStatus.textContent = data.detail || 'Ошибка retraining';
      return;
    }
    opsStatus.textContent = data.message;
    await pollRetrainStatus();
  } catch (error) {
    opsStatus.textContent = 'Ошибка соединения с backend';
  }
});

async function pollRetrainStatus() {
  const statusUrl = `${API_BASE_URL}/api/retrain/status`;
  for (let attempt = 0; attempt < 30; attempt += 1) {
    try {
      const response = await fetch(statusUrl);
      const statusData = await response.json();
      if (!response.ok) {
        opsStatus.textContent = statusData.detail || 'Не удалось получить статус переобучения';
        return;
      }
      if (statusData.status === 'running') {
        opsStatus.textContent = `Переобучение в процессе... (${attempt + 1})`;
        await new Promise((resolve) => setTimeout(resolve, 2000));
        continue;
      }
      if (statusData.status === 'completed') {
        opsStatus.textContent = 'Переобучение завершено успешно';
        displayModelResult(statusData.result);
        const mae = statusData.result?.mae?.toFixed(3) ?? '—';
        showToast('Новая модель активна', `MAE: ${mae} · Run ID: ${statusData.result?.run_id?.slice(0, 8)}...`, 'success', 8000);
        sendBrowserNotification('Модель переобучена', `Новая модель активна. MAE: ${mae}`);
        return;
      }
      if (statusData.status === 'failed') {
        opsStatus.textContent = `Переобучение не удалось: ${statusData.message}`;
        showToast('Переобучение не удалось', statusData.message, 'error');
        sendBrowserNotification('Ошибка переобучения', statusData.message);
        return;
      }
    } catch (error) {
      opsStatus.textContent = 'Ошибка при проверке статуса переобучения';
      return;
    }
  }
  opsStatus.textContent = 'Переобучение выполняется слишком долго. Статус можно проверить позже.';
}

function displayModelResult(result) {
  if (!result || !modelResult) return;
  const mae = typeof result.mae === 'number' ? result.mae.toFixed(3) : '—';
  const rmse = typeof result.rmse === 'number' ? result.rmse.toFixed(3) : '—';
  const runId = result.run_id ? result.run_id.slice(0, 8) + '...' : '—';
  modelResult.style.display = 'block';
  modelResult.innerHTML = `
    <h3>Новая модель обучена</h3>
    <div class="drift-summary">
      <div class="drift-card">
        <span>MAE</span>
        <strong>${mae}</strong>
      </div>
      <div class="drift-card">
        <span>RMSE</span>
        <strong>${rmse}</strong>
      </div>
      <div class="drift-card">
        <span>MLflow Run ID</span>
        <strong title="${result.run_id || ''}">${runId}</strong>
      </div>
      <div class="drift-card">
        <span>Модель</span>
        <strong>${result.registered_model || '—'}</strong>
      </div>
    </div>
  `;
}

function displayDriftResult(data) {
  const driftFound = data.data_drift_detected || data.target_drift_detected || data.concept_drift_detected;
  const statusText = driftFound ? 'Дрейф обнаружен' : 'Дрейф не обнаружен';
  const statusClass = driftFound ? 'badge--error' : 'badge--ok';

  const summaryHtml = `
    <div class="drift-summary">
      <div class="drift-card">
        <span>Состояние</span>
        <strong>${statusText}</strong>
        <span class="badge ${statusClass}">${statusText}</span>
      </div>
      <div class="drift-card">
        <span>Data drift</span>
        <strong>${data.data_drift_detected ? 'Да' : 'Нет'}</strong>
      </div>
      <div class="drift-card">
        <span>Target drift</span>
        <strong>${data.target_drift_detected ? 'Да' : 'Нет'}</strong>
      </div>
      <div class="drift-card">
        <span>Concept drift</span>
        <strong>${data.concept_drift_detected ? 'Да' : 'Нет'}</strong>
      </div>
      <div class="drift-card">
        <span>Data drift share</span>
        <strong>${(data.data_drift_share * 100).toFixed(0)}%</strong>
      </div>
    </div>
  `;

  const featureRows = Object.entries(data.features || {}).map(([feature, stats]) => {
    const drifted = stats.drift_detected ? 'badge--error' : 'badge--ok';
    return `
      <tr>
        <td>${feature}</td>
        <td>${stats.psi.toFixed(3)}</td>
        <td>${stats.ks_pvalue.toExponential(2)}</td>
        <td>${stats.js_distance.toFixed(3)}</td>
        <td class="status-cell"><span class="badge ${drifted}">${stats.drift_detected ? 'drift' : 'ok'}</span></td>
      </tr>
    `;
  }).join('');

  const targetHtml = `
    <div class="drift-summary">
      <div class="drift-card">
        <span>Target PSI</span>
        <strong>${data.target.psi.toFixed(3)}</strong>
      </div>
      <div class="drift-card">
        <span>Target KS</span>
        <strong>${data.target.ks_pvalue.toExponential(2)}</strong>
      </div>
      <div class="drift-card">
        <span>Target JS</span>
        <strong>${data.target.js_distance.toFixed(3)}</strong>
      </div>
      <div class="drift-card">
        <span>Current MAE</span>
        <strong>${data.concept.current_mae.toFixed(3)}</strong>
      </div>
      <div class="drift-card">
        <span>MAE degradation</span>
        <strong>${(data.concept.relative_degradation * 100).toFixed(1)}%</strong>
      </div>
    </div>
  `;

  driftResultDiv.innerHTML = `
    <h3>Результаты drift-проверки</h3>
    ${summaryHtml}
    ${targetHtml}
    <div class="drift-card">
      <strong>По признакам</strong>
      <table class="feature-table">
        <thead><tr><th>Признак</th><th>PSI</th><th>KS p-value</th><th>JS</th><th>Статус</th></tr></thead>
        <tbody>${featureRows}</tbody>
      </table>
    </div>
  `;

  // Встроенный HTML-отчёт (если есть)
  const reportContainer = document.getElementById('driftReport');
  const reportFrame = document.getElementById('driftReportFrame');
  if (reportContainer && reportFrame) {
    if (data.html_report) {
      const path = `${API_BASE_URL}/api/drift/report`;
      lastReportUrl = path;
      reportFrame.src = path;
      reportContainer.style.display = 'block';
    } else {
      reportContainer.style.display = 'none';
      reportFrame.src = '';
    }
  }
}

// JSON modal utilities
function showJsonModal(obj) {
  const modal = document.getElementById('jsonModal');
  const content = document.getElementById('jsonModalContent');
  if (!modal || !content) return alert(JSON.stringify(obj, null, 2));
  content.textContent = JSON.stringify(obj, null, 2);
  modal.style.display = 'flex';
}
const closeJsonModal = document.getElementById('closeJsonModal');
if (closeJsonModal) closeJsonModal.addEventListener('click', () => {
  const modal = document.getElementById('jsonModal');
  if (modal) modal.style.display = 'none';
});

function displayForecast(container, data) {
  const values = data.hourly_forecast.map(Math.round);
  const max = Math.max(...values);
  const min = Math.min(...values);
  const avg = (values.reduce((a, b) => a + b, 0) / values.length).toFixed(2);
  const total = values.reduce((a, b) => a + b, 0).toFixed(0);
  const peakHour = values.indexOf(max);
  let rows = values.map((value, hour) => `<tr><td>${hour}:00</td><td>${value}</td></tr>`).join('');
  container.innerHTML = `<h2>Прогноз на ${formatDate(data.date)}</h2><div class="metrics"><div class="metric"><span>Максимум</span><strong>${max}</strong><small>${peakHour}:00</small></div><div class="metric"><span>Минимум</span><strong>${min}</strong></div><div class="metric"><span>Среднее</span><strong>${avg}</strong></div><div class="metric"><span>Всего</span><strong>${total}</strong></div></div><table><thead><tr><th>Час</th><th>Прогноз</th></tr></thead><tbody>${rows}</tbody></table>`;
  container.style.display = 'block';
}

function showError(container, message) {
  container.innerHTML = `<p class="error">Ошибка: ${message}</p>`;
  container.style.display = 'block';
}

function formatDate(dateStr) {
  const date = new Date(dateStr);
  return date.toLocaleDateString('ru-RU', { year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' });
}

const today = new Date().toISOString().split('T')[0];
document.getElementById('date').min = today;
document.getElementById('date').value = today;
