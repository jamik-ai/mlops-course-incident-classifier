// src/api/frontend/script.js
// Автоматическое определение API URL
const API_BASE_URL = 'http://localhost:8000';  // 👈 Прямое обращение к бэкенду

// Остальной код без изменений
document.getElementById('forecastForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    const date = document.getElementById('date').value;
    const resultDiv = document.getElementById('result');
    const loadingDiv = document.getElementById('loading');

    if (!date) {
        showError(resultDiv, 'Пожалуйста, выберите дату');
        return;
    }

    loadingDiv.style.display = 'block';
    resultDiv.innerHTML = '';

    try {
        // Используем API_BASE_URL
        const response = await fetch(`${API_BASE_URL}/api/forecast`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ date })
        });

        const data = await response.json();

        if (response.ok) {
            displayForecast(resultDiv, data);
        } else {
            showError(resultDiv, data.detail || 'Ошибка при получении прогноза');
        }
    } catch (error) {
        showError(resultDiv, 'Ошибка соединения с сервером. Убедитесь, что сервер запущен.');
        console.error('Error:', error);
    } finally {
        loadingDiv.style.display = 'none';
    }
});
function displayForecast(container, data) {
    const hourlyForecast = data.hourly_forecast.map(value => Math.round(value));

    // Вычисляем статистику
    const maxForecast = Math.max(...hourlyForecast);
    const minForecast = Math.min(...hourlyForecast);
    const avgForecast = (hourlyForecast.reduce((a, b) => a + b, 0) / hourlyForecast.length).toFixed(2);
    const totalForecast = hourlyForecast.reduce((a, b) => a + b, 0).toFixed(0);

    // Находим пиковые часы
    const peakHour = hourlyForecast.indexOf(maxForecast);

    let html = `
        <div class="result-card">
            <h2>📊 Прогноз на ${formatDate(data.date)}</h2>

            <div class="stats">
                <div class="stat-item">
                    <div class="stat-label">📈 Максимум</div>
                    <div class="stat-value">${maxForecast}</div>
                    <div class="stat-label">вызовов (${peakHour}:00)</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">📉 Минимум</div>
                    <div class="stat-value">${minForecast}</div>
                    <div class="stat-label">вызовов</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">📊 Среднее</div>
                    <div class="stat-value">${avgForecast}</div>
                    <div class="stat-label">вызовов/час</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">📞 Всего</div>
                    <div class="stat-value">${totalForecast}</div>
                    <div class="stat-label">вызовов</div>
                </div>
            </div>

            <table>
                <thead>
                    <tr>
                        <th>Час</th>
                        <th>Прогноз вызовов</th>
                    </tr>
                </thead>
                <tbody>
    `;

    for (let i = 0; i < hourlyForecast.length; i++) {
        const forecast = hourlyForecast[i];
        html += `
            <tr>
                <td class="hour-cell">${i}:00</td>
                <td class="forecast-cell"><strong>${forecast}</strong></td>
            </tr>
        `;
    }

    html += `
                </tbody>
            </table>
        </div>
    `;

    container.innerHTML = html;

    // Плавный скролл к результатам
    container.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function showError(container, message) {
    container.innerHTML = `
        <div class="error">
            <strong>❌ Ошибка:</strong> ${message}
        </div>
    `;
}

function formatDate(dateStr) {
    const date = new Date(dateStr);
    const months = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
                   'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'];
    const days = ['воскресенье', 'понедельник', 'вторник', 'среду', 'четверг', 'пятницу', 'субботу'];

    return `${date.getDate()} ${months[date.getMonth()]} ${date.getFullYear()} года (${days[date.getDay()]})`;
}

// Установка минимальной даты (сегодня)
const today = new Date().toISOString().split('T')[0];
document.getElementById('date').min = today;
document.getElementById('date').value = today;