const API_BASE_URL = window.API_BASE_URL || 'http://localhost:8000';
const resultDiv = document.getElementById('result');
const loadingDiv = document.getElementById('loading');
const opsStatus = document.getElementById('opsStatus');

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
  try {
    const response = await fetch(`${API_BASE_URL}/api/drift/run`, { method: 'POST' });
    const data = await response.json();
    opsStatus.textContent = response.ok ? JSON.stringify(data, null, 2) : (data.detail || 'Ошибка drift check');
  } catch (error) {
    opsStatus.textContent = 'Ошибка соединения с backend';
  }
});

document.getElementById('reportButton').addEventListener('click', () => {
  window.open(`${API_BASE_URL}/api/drift/report`, '_blank');
});

document.getElementById('retrainButton').addEventListener('click', async () => {
  opsStatus.textContent = 'Запускаю retraining...';
  try {
    const response = await fetch(`${API_BASE_URL}/api/retrain`, { method: 'POST' });
    const data = await response.json();
    opsStatus.textContent = response.ok ? data.message : (data.detail || 'Ошибка retraining');
  } catch (error) {
    opsStatus.textContent = 'Ошибка соединения с backend';
  }
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
