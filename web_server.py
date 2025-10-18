# web_server.py - ПОЛНОСТЬЮ ПЕРЕРАБОТАННАЯ ВЕРСИЯ
from flask import Flask, render_template, jsonify, request, send_from_directory
import paho.mqtt.client as mqtt
import json
import time
import threading
import os
from datetime import datetime
from collections import defaultdict
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Конфигурация
class Config:
    MQTT_BROKER_HOST = "localhost"
    MQTT_BROKER_PORT = 1883
    MQTT_KEEPALIVE = 60
    WEB_HOST = "0.0.0.0"
    WEB_PORT = 5000
    DEVICE_TOPIC_PREFIX = "devices"
    STATUS_UPDATE_INTERVAL = 30  # секунды

# Хранилище данных
class DeviceStorage:
    def __init__(self):
        self.devices = {}
        self.device_types = defaultdict(list)
        self.message_count = 0
        self.error_count = 0
        self.start_time = time.time()
        self.event_log = []
        
    def add_device(self, device_id, device_type, ip_address, attributes=None):
        """Добавление нового устройства"""
        device_data = {
            'id': device_id,
            'type': device_type,
            'ip': ip_address,
            'status': 'connected',
            'last_seen': time.time(),
            'attributes': attributes or {},
            'created_at': datetime.now().isoformat()
        }
        
        self.devices[device_id] = device_data
        
        if device_id not in self.device_types[device_type]:
            self.device_types[device_type].append(device_id)
            
        self.log_event(f"Устройство подключено: {device_id} ({device_type})")
        logger.info(f"Устройство зарегистрировано: {device_id}")
        
        return device_data
    
    def update_device(self, device_id, updates):
        """Обновление данных устройства"""
        if device_id in self.devices:
            self.devices[device_id].update(updates)
            self.devices[device_id]['last_seen'] = time.time()
            
    def remove_device(self, device_id):
        """Удаление устройства"""
        if device_id in self.devices:
            device_type = self.devices[device_id]['type']
            if device_id in self.device_types[device_type]:
                self.device_types[device_type].remove(device_id)
                
            self.log_event(f"Устройство отключено: {device_id}")
            del self.devices[device_id]
            logger.info(f"Устройство удалено: {device_id}")
    
    def get_online_devices(self):
        """Получение онлайн устройств"""
        current_time = time.time()
        online_devices = []
        
        for device_id, device in self.devices.items():
            if current_time - device['last_seen'] < Config.STATUS_UPDATE_INTERVAL:
                online_devices.append(device)
            else:
                device['status'] = 'disconnected'
                
        return online_devices
    
    def get_device_stats(self):
        """Статистика по устройствам"""
        online_devices = self.get_online_devices()
        
        stats = {
            'total': len(self.devices),
            'online': len(online_devices),
            'by_type': {}
        }
        
        for device_type, devices in self.device_types.items():
            online_count = sum(1 for device_id in devices 
                             if self.devices[device_id]['status'] == 'connected')
            stats['by_type'][device_type] = online_count
            
        return stats
    
    def log_event(self, message, level='info'):
        """Логирование события"""
        event = {
            'timestamp': datetime.now().isoformat(),
            'message': message,
            'level': level
        }
        
        self.event_log.append(event)
        
        # Ограничиваем размер лога
        if len(self.event_log) > 1000:
            self.event_log = self.event_log[-500:]
    
    def get_system_info(self):
        """Информация о системе"""
        uptime = time.time() - self.start_time
        hours = int(uptime // 3600)
        minutes = int((uptime % 3600) // 60)
        seconds = int(uptime % 60)
        
        return {
            'uptime': f"{hours:02d}:{minutes:02d}:{seconds:02d}",
            'message_count': self.message_count,
            'error_count': self.error_count,
            'device_count': len(self.devices),
            'online_count': len(self.get_online_devices())
        }

# Инициализация хранилища
storage = DeviceStorage()
mqtt_client = None

# MQTT обработчики
def on_mqtt_connect(client, userdata, flags, rc):
    """Обработчик подключения MQTT"""
    if rc == 0:
        logger.info("✅ MQTT клиент подключен к брокеру")
        
        # Подписываемся на топики устройств
        topics = [
            f"{Config.DEVICE_TOPIC_PREFIX}/+/status",
            f"{Config.DEVICE_TOPIC_PREFIX}/+/disconnect", 
            f"{Config.DEVICE_TOPIC_PREFIX}/+/data",
            f"{Config.DEVICE_TOPIC_PREFIX}/+/error"
        ]
        
        for topic in topics:
            client.subscribe(topic)
            logger.info(f"📡 Подписка на топик: {topic}")
            
        storage.log_event("MQTT клиент подключен к брокеру")
    else:
        logger.error(f"❌ Ошибка подключения MQTT: {rc}")
        storage.error_count += 1

def on_mqtt_message(client, userdata, msg):
    """Обработчик входящих MQTT сообщений"""
    try:
        storage.message_count += 1
        
        topic_parts = msg.topic.split('/')
        if len(topic_parts) < 3:
            return
            
        device_id = topic_parts[1]
        message_type = topic_parts[2]
        payload = msg.payload.decode('utf-8')
        
        logger.info(f"📨 MQTT: [{msg.topic}] {payload}")
        
        if message_type == "status":
            # Регистрация/обновление устройства
            data = json.loads(payload)
            storage.add_device(
                device_id=device_id,
                device_type=data.get('type', 'unknown'),
                ip_address=data.get('ip', 'unknown'),
                attributes=data
            )
            
        elif message_type == "data":
            # Данные от устройства
            data = json.loads(payload)
            storage.update_device(device_id, {
                'last_data': data,
                'last_data_time': time.time()
            })
            
        elif message_type == "disconnect":
            # Отключение устройства
            storage.remove_device(device_id)
            
        elif message_type == "error":
            # Ошибка от устройства
            data = json.loads(payload)
            storage.error_count += 1
            storage.log_event(f"Ошибка устройства {device_id}: {data.get('error', 'Unknown')}", 'error')
            
    except Exception as e:
        logger.error(f"❌ Ошибка обработки MQTT сообщения: {e}")
        storage.error_count += 1
        storage.log_event(f"Ошибка обработки MQTT: {str(e)}", 'error')

def setup_mqtt():
    """Настройка MQTT клиента"""
    global mqtt_client
    
    mqtt_client = mqtt.Client()
    mqtt_client.on_connect = on_mqtt_connect
    mqtt_client.on_message = on_mqtt_message
    
    try:
        mqtt_client.connect(Config.MQTT_BROKER_HOST, Config.MQTT_BROKER_PORT, Config.MQTT_KEEPALIVE)
        
        # Запускаем MQTT loop в отдельном потоке
        def mqtt_loop():
            try:
                mqtt_client.loop_forever()
            except Exception as e:
                logger.error(f"❌ Ошибка MQTT loop: {e}")
                storage.error_count += 1
        
        mqtt_thread = threading.Thread(target=mqtt_loop, daemon=True)
        mqtt_thread.start()
        
        logger.info("✅ MQTT клиент запущен")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка подключения MQTT: {e}")
        storage.error_count += 1
        return False

# Flask маршруты
@app.route('/')
def index():
    """Главная страница"""
    return render_template('index.html')

@app.route('/status')
def status_page():
    """Страница статуса системы"""
    return render_template('status.html')

@app.route('/commands')
def commands_page():
    """Страница отправки команд"""
    return render_template('commands.html')

@app.route('/devices')
def devices_page():
    """Страница управления устройствами"""
    return render_template('devices.html')

# API endpoints
@app.route('/api/devices')
def api_get_devices():
    """API: Получение списка устройств"""
    try:
        online_devices = storage.get_online_devices()
        
        return jsonify({
            'status': 'success',
            'devices': online_devices,
            'stats': storage.get_device_stats(),
            'timestamp': time.time()
        })
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения устройств: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/device/<device_id>/command', methods=['POST'])
def api_send_command(device_id):
    """API: Отправка команды устройству"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'No JSON data provided'}), 400
            
        command = data.get('command')
        if not command:
            return jsonify({'status': 'error', 'message': 'Command not specified'}), 400
        
        # Проверяем существование устройства
        if device_id not in storage.devices:
            return jsonify({'status': 'error', 'message': f'Device {device_id} not found'}), 404
        
        # Отправляем команду через MQTT
        topic = f"{Config.DEVICE_TOPIC_PREFIX}/{device_id}/command"
        mqtt_client.publish(topic, json.dumps({
            'command': command,
            'timestamp': time.time(),
            'source': 'web'
        }))
        
        storage.log_event(f"Команда отправлена: {device_id} -> {command}")
        logger.info(f"✅ Команда отправлена: {device_id} -> {command}")
        
        return jsonify({
            'status': 'success',
            'message': f'Command sent to {device_id}',
            'device_id': device_id,
            'command': command
        })
        
    except Exception as e:
        logger.error(f"❌ Ошибка отправки команды: {e}")
        storage.error_count += 1
        return jsonify({
            'status': 'error', 
            'message': str(e)
        }), 500

@app.route('/api/broadcast', methods=['POST'])
def api_broadcast_command():
    """API: Отправка команды всем устройствам"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'No JSON data provided'}), 400
            
        command = data.get('command')
        if not command:
            return jsonify({'status': 'error', 'message': 'Command not specified'}), 400
        
        # Отправляем команду всем онлайн устройствам
        online_devices = storage.get_online_devices()
        sent_count = 0
        
        for device in online_devices:
            topic = f"{Config.DEVICE_TOPIC_PREFIX}/{device['id']}/command"
            mqtt_client.publish(topic, json.dumps({
                'command': command,
                'timestamp': time.time(),
                'source': 'broadcast'
            }))
            sent_count += 1
        
        storage.log_event(f"Broadcast команда: {command} -> {sent_count} устройств")
        logger.info(f"📢 Broadcast команда: {command} -> {sent_count} устройств")
        
        return jsonify({
            'status': 'success',
            'message': f'Command broadcast to {sent_count} devices',
            'sent_count': sent_count,
            'command': command
        })
        
    except Exception as e:
        logger.error(f"❌ Ошибка broadcast команды: {e}")
        storage.error_count += 1
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/system/status')
def api_system_status():
    """API: Статус системы"""
    try:
        system_info = storage.get_system_info()
        device_stats = storage.get_device_stats()
        
        # Проверяем MQTT соединение
        mqtt_connected = mqtt_client and mqtt_client.is_connected()
        
        return jsonify({
            'status': 'success',
            'system': {
                'mqtt_connected': mqtt_connected,
                'web_server': True,
                'uptime': system_info['uptime'],
                'message_count': system_info['message_count'],
                'error_count': system_info['error_count']
            },
            'devices': device_stats,
            'timestamp': time.time()
        })
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения статуса системы: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/system/events')
def api_system_events():
    """API: Получение событий системы"""
    try:
        limit = request.args.get('limit', 50, type=int)
        events = storage.event_log[-limit:] if storage.event_log else []
        
        return jsonify({
            'status': 'success',
            'events': events,
            'total_count': len(storage.event_log)
        })
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения событий: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/device/<device_id>/info')
def api_device_info(device_id):
    """API: Подробная информация об устройстве"""
    try:
        if device_id not in storage.devices:
            return jsonify({'status': 'error', 'message': 'Device not found'}), 404
        
        device = storage.devices[device_id]
        return jsonify({
            'status': 'success',
            'device': device
        })
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения информации об устройстве: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/discover', methods=['POST'])
def api_discover_devices():
    """API: Принудительный поиск устройств"""
    try:
        # Отправляем broadcast команду для поиска устройств
        discovery_topic = f"{Config.DEVICE_TOPIC_PREFIX}/discovery"
        mqtt_client.publish(discovery_topic, json.dumps({
            'command': 'DISCOVER',
            'timestamp': time.time()
        }))
        
        storage.log_event("Запущен принудительный поиск устройств")
        logger.info("🔍 Запущен принудительный поиск устройств")
        
        return jsonify({
            'status': 'success',
            'message': 'Device discovery initiated'
        })
        
    except Exception as e:
        logger.error(f"❌ Ошибка поиска устройств: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/system/shutdown', methods=['POST'])
def api_system_shutdown():
    """API: Завершение работы системы"""
    try:
        storage.log_event("Запрошено завершение работы системы", 'warning')
        logger.warning("🛑 Запрошено завершение работы системы")
        
        # Здесь можно добавить логику корректного завершения
        def delayed_shutdown():
            time.sleep(2)
            os._exit(0)
        
        shutdown_thread = threading.Thread(target=delayed_shutdown, daemon=True)
        shutdown_thread.start()
        
        return jsonify({
            'status': 'success',
            'message': 'System shutdown initiated'
        })
        
    except Exception as e:
        logger.error(f"❌ Ошибка завершения работы: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# Статические файлы
@app.route('/static/<path:filename>')
def serve_static(filename):
    """Обслуживание статических файлов"""
    return send_from_directory('static', filename)

# Обработчики ошибок
@app.errorhandler(404)
def not_found(error):
    return jsonify({'status': 'error', 'message': 'Resource not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"500 Internal Server Error: {error}")
    return jsonify({'status': 'error', 'message': 'Internal server error'}), 500

def start_web_server():
    """Запуск веб-сервера"""
    try:
        # Настраиваем MQTT клиент
        if not setup_mqtt():
            logger.error("❌ Не удалось запустить MQTT клиент")
            return False
        
        logger.info("🚀 Запуск веб-сервера...")
        logger.info(f"🌐 Веб-интерфейс будет доступен по адресу: http://{Config.WEB_HOST}:{Config.WEB_PORT}")
        
        storage.log_event("Веб-сервер запущен")
        
        # Запускаем Flask сервер
        app.run(
            host=Config.WEB_HOST,
            port=Config.WEB_PORT,
            debug=False,
            threaded=True
        )
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка запуска веб-сервера: {e}")
        return False

# Запуск при прямом выполнении
if __name__ == '__main__':
    start_web_server()