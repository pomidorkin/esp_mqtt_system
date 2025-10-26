class ESPDeviceManager {
    constructor() {
        this.devices = new Map();
        this.systemStatus = {
            mqtt: false,
            webserver: true,
            uptime: 0
        };
        this.init();
    }

    init() {
        this.loadDevices();
        this.startAutoRefresh();
        this.updateSystemStatus();

        // Обновляем время работы каждую секунду
        setInterval(() => {
            this.systemStatus.uptime++;
            this.updateUptimeDisplay();
        }, 1000);
    }

    async loadDevices() {
        try {
            const response = await fetch('/api/devices');
            const data = await response.json();

            if (data.status === 'success') {
                this.updateDevicesDisplay(data.devices);
                this.updateStats(data.stats);
                this.systemStatus.mqtt = true;
            }
        } catch (error) {
            console.error('Ошибка загрузки устройств:', error);
            this.systemStatus.mqtt = false;
        }

        this.updateSystemStatus();
    }

    updateDevicesDisplay(devices) {
        const devicesList = document.getElementById('devices-list');
        if (!devicesList) return;

        if (devices.length === 0) {
            devicesList.innerHTML = '<div class="no-devices">🚫 Нет подключенных устройств</div>';
            return;
        }

        devicesList.innerHTML = devices.map(device => {
            const isRGB = device.type === 'rgb_controller' || device.type === 'color_mixer';
            const buttonPressed = device.action_button_pressed;
            const ledOn = device.led_on;
            const rgbColor = device.rgb_color || '0,0,0';
            const available = device.available;

            // Парсим RGB цвет
            const [r, g, b] = rgbColor.split(',').map(Number);
            const colorStyle = `background: rgb(${r}, ${g}, ${b})`;

            return `
            <div class="device-card">
                <div class="device-header">
                    <div class="device-name">${device.id}</div>
                    <div class="device-type">
                        ${this.getDeviceTypeIcon(device.type)} ${device.type}
                        ${isRGB ? `
                            <span class="device-status-badge ${available ? 'status-available' : 'status-pressed'}">
                                ${available ? '✅ Доступно' : '⏸️ Кнопка нажата'}
                            </span>
                        ` : ''}
                    </div>
                </div>
                
                <div class="device-details">
                    <div class="detail-item">
                        <span>Статус:</span>
                        <strong style="color: ${device.status === 'connected' ? '#27ae60' : '#e74c3c'}">
                            ${device.status === 'connected' ? '✅ Онлайн' : '❌ Офлайн'}
                        </strong>
                    </div>
                    <div class="detail-item">
                        <span>IP адрес:</span>
                        <strong>${device.ip}</strong>
                    </div>
                    <div class="detail-item">
                        <span>Последняя активность:</span>
                        <strong>${this.formatTime(device.last_seen)}</strong>
                    </div>
                    ${isRGB ? `
                    <div class="detail-item">
                        <span>Светодиод:</span>
                        <strong style="color: ${ledOn ? '#27ae60' : '#e74c3c'}">
                            ${ledOn ? '🟢 Включен' : '🔴 Выключен'}
                        </strong>
                    </div>
                    <div class="detail-item">
                        <span>Цвет:</span>
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <div class="rgb-color-indicator" style="${colorStyle}"></div>
                            <strong>RGB(${r}, ${g}, ${b})</strong>
                        </div>
                    </div>
                    ` : ''}
                </div>

                <div class="device-actions">
                    <button class="btn btn-primary" onclick="deviceManager.sendDeviceCommand('${device.id}', 'STATUS')">
                        📡 Статус
                    </button>
                    ${isRGB ? `
                    <button class="btn btn-success" onclick="deviceManager.openColorModal('${device.id}')">
                        🎨 Цвет
                    </button>
                    ${buttonPressed ? `
                    <button class="btn btn-warning" onclick="deviceManager.resetDeviceButton('${device.id}')">
                        🔄 Сброс кнопки
                    </button>
                    ` : ''}
                    ` : ''}
                    <button class="btn btn-secondary" onclick="deviceManager.sendDeviceCommand('${device.id}', 'RESTART')">
                        🔄 Перезагрузка
                    </button>
                    ${device.type === 'color_mixer' ? `
                    <button class="btn btn-info" onclick="deviceManager.mixColors()">
                        🎨 Перемешать
                    </button>
                    ` : ''}
                </div>
            </div>
            `;
        }).join('');
    }

    updateStats(stats) {
        const totalEl = document.getElementById('total-devices');
        const onlineEl = document.getElementById('online-devices');
        const typesEl = document.getElementById('device-types');
        const availableRgbEl = document.getElementById('available-rgb');

        if (totalEl) totalEl.textContent = stats.total;
        if (onlineEl) onlineEl.textContent = stats.online;
        if (typesEl) typesEl.textContent = Object.keys(stats.by_type).length;

        // Обновляем статистику RGB устройств
        if (availableRgbEl) {
            const rgbStats = stats.rgb_controllers || { available: 0 };
            availableRgbEl.textContent = rgbStats.available || 0;
        }
    }

    updateSystemStatus() {
        const statusIndicator = document.getElementById('status-indicator');
        const statusText = document.getElementById('status-text');

        if (statusIndicator && statusText) {
            if (this.systemStatus.mqtt && this.systemStatus.webserver) {
                statusIndicator.style.background = '#27ae60';
                statusText.textContent = '✅ Система работает нормально';
            } else {
                statusIndicator.style.background = '#e74c3c';
                statusText.textContent = '⚠️ Проблемы с подключением';
            }
        }
    }

    updateUptimeDisplay() {
        const uptimeEl = document.getElementById('uptime');
        if (uptimeEl) {
            const hours = Math.floor(this.systemStatus.uptime / 3600);
            const minutes = Math.floor((this.systemStatus.uptime % 3600) / 60);
            const seconds = this.systemStatus.uptime % 60;
            uptimeEl.textContent = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
        }
    }

    getDeviceTypeIcon(type) {
        const icons = {
            'rgb_controller': '🎨',
            'color_mixer': '🔄',
            'sensor': '📊',
            'switch': '🔌',
            'mixer': '🔄',
            'unknown': '❓'
        };
        return icons[type] || '📱';
    }

    formatTime(timestamp) {
        const now = Date.now() / 1000;
        const diff = now - timestamp;

        if (diff < 60) return 'только что';
        if (diff < 3600) return `${Math.floor(diff / 60)} мин назад`;
        if (diff < 86400) return `${Math.floor(diff / 3600)} ч назад`;

        return new Date(timestamp * 1000).toLocaleString();
    }

    async sendDeviceCommand(deviceId, command) {
        try {
            const response = await fetch(`/api/device/${deviceId}/command`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ command: command })
            });

            const data = await response.json();
            this.showNotification(data.message, data.status);

        } catch (error) {
            console.error('Ошибка отправки команды:', error);
            this.showNotification('Ошибка отправки команды', 'error');
        }
    }

    setDeviceColor

    async resetDeviceButton(deviceId) {
        try {
            const response = await fetch(`/api/device/${deviceId}/reset_button`, {
                method: 'POST'
            });

            const data = await response.json();
            this.showNotification(data.message, data.status);
            this.loadDevices(); // Обновляем список устройств

        } catch (error) {
            console.error('Ошибка сброса кнопки:', error);
            this.showNotification('Ошибка сброса кнопки', 'error');
        }
    }

    async mixColors() {
        try {
            const response = await fetch('/api/devices/mix_colors', {
                method: 'POST'
            });

            const data = await response.json();
            this.showNotification(data.message, data.status);
            this.loadDevices(); // Обновляем список устройств

        } catch (error) {
            console.error('Ошибка перемешивания цветов:', error);
            this.showNotification('Ошибка перемешивания цветов', 'error');
        }
    }

    openColorModal(deviceId) {
        if (typeof openColorModal === 'function') {
            openColorModal(deviceId);
        }
    }

    showNotification(message, type = 'info') {
        // Создаем уведомление
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.textContent = message;

        document.body.appendChild(notification);

        // Удаляем через 5 секунд
        setTimeout(() => {
            notification.remove();
        }, 5000);
    }

    startAutoRefresh() {
        // Обновляем устройства каждые 5 секунд
        setInterval(() => {
            this.loadDevices();
        }, 5000);
    }
}

// Глобальные функции
function refreshDevices() {
    if (window.deviceManager) {
        deviceManager.loadDevices();
        deviceManager.showNotification('Устройства обновляются...', 'info');
    }
}

function discoverDevices() {
    if (window.deviceManager) {
        deviceManager.showNotification('Поиск устройств...', 'info');
        fetch('/api/discover', { method: 'POST' })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    deviceManager.showNotification('Поиск устройств запущен', 'success');
                }
            });
        refreshDevices();
    }
}

function mixColors() {
    if (window.deviceManager) {
        deviceManager.mixColors();
    }
}

function shutdownSystem() {
    if (confirm('Вы уверены, что хотите завершить работу системы?\n\nВсе подключения будут разорваны.')) {
        fetch('/api/shutdown', { method: 'POST' })
            .then(() => {
                alert('Система завершает работу...');
                window.close();
            })
            .catch(() => {
                alert('Система завершена. Закройте окно.');
                window.close();
            });
    }
}

// Инициализация при загрузке страницы
let deviceManager;
document.addEventListener('DOMContentLoaded', function () {
    deviceManager = new ESPDeviceManager();
});