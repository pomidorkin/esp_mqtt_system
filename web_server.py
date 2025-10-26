# web_server.py - ПОЛНОСТЬЮ ПЕРЕРАБОТАННАЯ ВЕРСИЯ С АВТООПРЕДЕЛЕНИЕМ IP
from flask import Flask, render_template, jsonify, request, send_from_directory
import paho.mqtt.client as mqtt
import json
import time
import threading
import os
from datetime import datetime
from collections import defaultdict
import logging
import socket

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# АВТОМАТИЧЕСКОЕ ОПРЕДЕЛЕНИЕ СЕТЕВЫХ НАСТРОЕК
def get_local_ip():
    """Автоматическое определение локального IP"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

LOCAL_IP = get_local_ip()

# Конфигурация С АВТООПРЕДЕЛЕНИЕМ
class Config:
    MQTT_BROKER_HOST = LOCAL_IP  # АВТООПРЕДЕЛЕНИЕ!
    MQTT_BROKER_PORT = 1883
    MQTT_KEEPALIVE = 60
    WEB_HOST = "0.0.0.0"
    WEB_PORT = 5000
    DEVICE_TOPIC_PREFIX = "devices"
    STATUS_UPDATE_INTERVAL = 30  # секунды

# Выводим информацию о конфигурации
print("=" * 50)
print("🌐 АВТОМАТИЧЕСКАЯ КОНФИГУРАЦИЯ СИСТЕМЫ")
print(f"📍 Локальный IP: {LOCAL_IP}")
print(f"🔗 MQTT брокер: {Config.MQTT_BROKER_HOST}:{Config.MQTT_BROKER_PORT}")
print(f"🌐 Веб-интерфейс: http://{LOCAL_IP}:{Config.WEB_PORT}")
print("=" * 50)

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
        """Добавление нового устройства с поддержкой RGB устройств"""
        device_data = {
            'id': device_id,
            'type': device_type,
            'ip': ip_address,
            'status': 'connected',
            'last_seen': time.time(),
            'attributes': attributes or {},
            'created_at': datetime.now().isoformat(),
            # Новые поля для RGB устройств
            'action_button_pressed': False,
            'led_on': True,
            'rgb_color': '0,0,0',  # формат: "red,green,blue"
            'available': True      # доступно для перемешивания
        }
        
        # Обновляем атрибуты из MQTT сообщения
        if attributes:
            if 'action_button_pressed' in attributes:
                device_data['action_button_pressed'] = attributes['action_button_pressed']
            if 'led_on' in attributes:
                device_data['led_on'] = attributes['led_on']
            if 'rgb_color' in attributes:
                device_data['rgb_color'] = attributes['rgb_color']
            if 'available' in attributes:
                device_data['available'] = attributes['available']
        
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
            
            # Автоматически обновляем доступность для RGB контроллеров
            if self.devices[device_id]['type'] == 'rgb_controller':
                action_pressed = self.devices[device_id].get('action_button_pressed', False)
                self.devices[device_id]['available'] = not action_pressed
    
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

    # ========== НОВЫЕ МЕТОДЫ ДЛЯ RGB УСТРОЙСТВ ==========
    
    def get_available_rgb_controllers(self):
        """Получение доступных RGB контроллеров (кнопка не нажата)"""
        available_devices = []
        for device_id, device in self.devices.items():
            if (device.get('type') == 'rgb_controller' and 
                device.get('status') == 'connected' and
                not device.get('action_button_pressed', False)):
                available_devices.append(device)
        return available_devices
    
    def set_device_color(self, device_id, red, green, blue):
        """Установка цвета для устройства через MQTT"""
        if device_id not in self.devices:
            logger.error(f"Устройство {device_id} не найдено для установки цвета")
            return False
        
        try:
            topic = f"{Config.DEVICE_TOPIC_PREFIX}/{device_id}/command"
            mqtt_client.publish(topic, json.dumps({
                'command': 'SET_COLOR',
                'red': max(0, min(255, red)),
                'green': max(0, min(255, green)),
                'blue': max(0, min(255, blue)),
                'timestamp': time.time()
            }))
            
            self.log_event(f"Команда SET_COLOR отправлена: {device_id} -> RGB({red},{green},{blue})")
            logger.info(f"🎨 Установка цвета: {device_id} -> RGB({red},{green},{blue})")
            
            # Предварительно обновляем локальные данные
            self.devices[device_id]['rgb_color'] = f"{red},{green},{blue}"
            self.devices[device_id]['led_on'] = (red > 0 or green > 0 or blue > 0)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка установки цвета для {device_id}: {e}")
            self.error_count += 1
            return False
    
    def mix_colors(self):
        """Перемешивание цветов между доступными RGB контроллерами"""
        try:
            available_devices = self.get_available_rgb_controllers()
            
            if len(available_devices) < 2:
                message = "Недостаточно доступных устройств для перемешивания"
                self.log_event(message, 'warning')
                return {"status": "error", "message": message}
            
            # Собираем текущие цвета
            colors = []
            device_ids = []
            
            for device in available_devices:
                rgb_str = device.get('rgb_color', '0,0,0')
                try:
                    colors.append([int(x) for x in rgb_str.split(',')])
                    device_ids.append(device['id'])
                except ValueError:
                    colors.append([0, 0, 0])  # цвет по умолчанию при ошибке
            
            # Перемешиваем цвета (циклический сдвиг вправо)
            mixed_colors = [colors[-1]] + colors[:-1]
            
            # Устанавливаем новые цвета
            success_count = 0
            for i, device_id in enumerate(device_ids):
                if i < len(mixed_colors):
                    new_color = mixed_colors[i]
                    if self.set_device_color(device_id, new_color[0], new_color[1], new_color[2]):
                        success_count += 1
            
            message = f"Цвета перемешаны для {success_count} из {len(available_devices)} устройств"
            self.log_event(message)
            logger.info(f"🎨 {message}")
            
            return {
                "status": "success", 
                "message": message,
                "mixed_count": success_count,
                "total_available": len(available_devices)
            }
            
        except Exception as e:
            error_msg = f"Ошибка перемешивания цветов: {str(e)}"
            logger.error(f"❌ {error_msg}")
            self.error_count += 1
            self.log_event(error_msg, 'error')
            return {"status": "error", "message": error_msg}
    
    def reset_device_button(self, device_id):
        """Сброс состояния кнопки устройства"""
        if device_id not in self.devices:
            logger.error(f"Устройство {device_id} не найдено для сброса кнопки")
            return False
        
        try:
            topic = f"{Config.DEVICE_TOPIC_PREFIX}/{device_id}/command"
            mqtt_client.publish(topic, json.dumps({
                'command': 'RESET_BUTTON',
                'timestamp': time.time()
            }))
            
            self.log_event(f"Команда RESET_BUTTON отправлена: {device_id}")
            logger.info(f"🔄 Сброс кнопки: {device_id}")
            
            # Предварительно обновляем локальные данные
            self.devices[device_id]['action_button_pressed'] = False
            self.devices[device_id]['available'] = True
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка сброса кнопки для {device_id}: {e}")
            self.error_count += 1
            return False
    
    def get_rgb_controllers_info(self):
        """Детальная информация о всех RGB контроллерах"""
        rgb_devices = []
        for device_id, device in self.devices.items():
            if device.get('type') == 'rgb_controller':
                rgb_info = {
                    'id': device['id'],
                    'status': device['status'],
                    'action_button_pressed': device.get('action_button_pressed', False),
                    'led_on': device.get('led_on', False),
                    'rgb_color': device.get('rgb_color', '0,0,0'),
                    'available': device.get('available', True),
                    'last_seen': device.get('last_seen'),
                    'ip': device.get('ip', 'unknown')
                }
                rgb_devices.append(rgb_info)
        
        return {
            'total': len(rgb_devices),
            'devices': rgb_devices
        }
    
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
        logger.info(f"✅ MQTT клиент подключен к брокеру {Config.MQTT_BROKER_HOST}:{Config.MQTT_BROKER_PORT}")
        
        # Подписываемся на топики устройств
        topics = [
            f"{Config.DEVICE_TOPIC_PREFIX}/+/status",      # Статус устройств
            f"{Config.DEVICE_TOPIC_PREFIX}/+/disconnect",  # Отключения
            f"{Config.DEVICE_TOPIC_PREFIX}/+/data",        # Данные с датчиков
            f"{Config.DEVICE_TOPIC_PREFIX}/+/error",       # Ошибки
            f"{Config.DEVICE_TOPIC_PREFIX}/+/button"       # Состояния кнопок
        ]
        
        for topic in topics:
            client.subscribe(topic)
            logger.info(f"📡 Подписка на топик: {topic}")
            
        storage.log_event("MQTT клиент подключен к брокеру")
        
        # Отправляем broadcast для поиска устройств
        client.publish(f"{Config.DEVICE_TOPIC_PREFIX}/discovery", json.dumps({
            'command': 'DISCOVER',
            'timestamp': time.time(),
            'source': 'server'
        }))
        
        logger.info("🔍 Отправлена команда DISCOVER для поиска устройств")
        
    else:
        logger.error(f"❌ Ошибка подключения MQTT: {rc}")
        storage.error_count += 1
        storage.log_event(f"Ошибка подключения MQTT: код {rc}", 'error')

def on_mqtt_message(client, userdata, msg):
    """Обработчик входящих MQTT сообщений"""
    try:
        storage.message_count += 1
        
        # ВРЕМЕННАЯ ОТЛАДКА - логируем ВСЕ сообщения
        payload_str = msg.payload.decode('utf-8')
        logger.info(f"🔍 MQTT сообщение: [{msg.topic}] {payload_str}")
        
        topic_parts = msg.topic.split('/')
        if len(topic_parts) < 3:
            logger.warning(f"⚠️ Неверный формат топика: {msg.topic}")
            return
            
        device_id = topic_parts[1]
        message_type = topic_parts[2]
        
        logger.info(f"📨 Обработка: устройство={device_id}, тип={message_type}")
        
        if message_type == "status":
            # Регистрация/обновление устройства
            try:
                data = json.loads(payload_str)
                
                # ОБНОВЛЕННЫЙ MAPPING ПОЛЕЙ (поддержка старых и новых имен)
                device_type = data.get('t', data.get('type', 'unknown'))
                ip_address = data.get('ip', 'unknown')
                
                # Собираем все атрибуты для устройства
                attributes = {
                    'mac': data.get('mac', ''),
                    'rssi': data.get('rssi', 0),
                    'free_heap': data.get('heap', data.get('free_heap', 0)),
                    'uptime': data.get('up', data.get('uptime', 0)),
                    'version': data.get('ver', data.get('version', 'unknown')),
                    'firmware': data.get('fw', data.get('firmware', 'unknown')),
                    'config_mode': data.get('cfg', data.get('config_mode', False)),
                    'mqtt_broker': data.get('mqtt', data.get('mqtt_broker', '')),
                    'led_state': data.get('led_s', data.get('led_state', True)),
                    # Поля для RGB устройств
                    'action_button_pressed': data.get('btn', data.get('action_button_pressed', False)),
                    'led_on': data.get('led', data.get('led_on', True)),
                    'rgb_color': data.get('rgb', data.get('rgb_color', '0,0,0')),
                    'available': data.get('avail', data.get('available', True))
                }
                
                # Логируем полученные данные
                logger.info(f"✅ Получен статус от {device_id}: type={device_type}, ip={ip_address}")
                
                storage.add_device(
                    device_id=device_id,
                    device_type=device_type,
                    ip_address=ip_address,
                    attributes=attributes
                )
                
            except json.JSONDecodeError as e:
                logger.error(f"❌ Ошибка парсинга JSON от {device_id}: {e}")
                storage.error_count += 1
                storage.log_event(f"Ошибка JSON от {device_id}: {str(e)}", 'error')
                
        elif message_type == "data":
            # Данные от устройства
            try:
                data = json.loads(payload_str)
                storage.update_device(device_id, {
                    'last_data': data,
                    'last_data_time': time.time()
                })
                logger.info(f"📊 Данные от {device_id}: {data}")
            except json.JSONDecodeError as e:
                logger.error(f"❌ Ошибка парсинга данных от {device_id}: {e}")
                
        elif message_type == "button":
            # Состояние кнопки
            try:
                data = json.loads(payload_str)
                storage.update_device(device_id, {
                    'action_button_pressed': data.get('action_button_pressed', False),
                    'led_on': data.get('led_on', True),
                    'last_button_time': time.time()
                })
                logger.info(f"🔘 Статус кнопки от {device_id}: pressed={data.get('action_button_pressed')}")
            except json.JSONDecodeError as e:
                logger.error(f"❌ Ошибка парсинга кнопки от {device_id}: {e}")
                
        elif message_type == "disconnect":
            # Отключение устройства
            storage.remove_device(device_id)
            logger.info(f"🔴 Устройство отключено: {device_id}")
            
        elif message_type == "error":
            # Ошибка от устройства
            try:
                data = json.loads(payload_str)
                storage.error_count += 1
                error_msg = data.get('error', 'Unknown error')
                storage.log_event(f"Ошибка устройства {device_id}: {error_msg}", 'error')
                logger.error(f"❌ Ошибка от {device_id}: {error_msg}")
            except json.JSONDecodeError as e:
                logger.error(f"❌ Ошибка парсинга ошибки от {device_id}: {e}")
                
        else:
            logger.warning(f"⚠️ Неизвестный тип сообщения от {device_id}: {message_type}")
            
    except Exception as e:
        logger.error(f"❌ Критическая ошибка обработки MQTT сообщения: {e}")
        storage.error_count += 1
        storage.log_event(f"Критическая ошибка MQTT: {str(e)}", 'error')

def setup_mqtt():
    """Настройка MQTT клиента"""
    global mqtt_client
    
    mqtt_client = mqtt.Client()
    mqtt_client.on_connect = on_mqtt_connect
    mqtt_client.on_message = on_mqtt_message
    
    try:
        logger.info(f"🔄 Подключение к MQTT брокеру: {Config.MQTT_BROKER_HOST}:{Config.MQTT_BROKER_PORT}")
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
    return render_template('index.html', local_ip=LOCAL_IP)

@app.route('/status')
def status_page():
    """Страница статуса системы"""
    return render_template('status.html', local_ip=LOCAL_IP)

@app.route('/commands')
def commands_page():
    """Страница отправки команд"""
    return render_template('commands.html', local_ip=LOCAL_IP)

@app.route('/devices')
def devices_page():
    """Страница управления устройствами"""
    return render_template('devices.html', local_ip=LOCAL_IP)

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
            'timestamp': time.time(),
            'mqtt_broker': Config.MQTT_BROKER_HOST
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
                'error_count': system_info['error_count'],
                'mqtt_broker': Config.MQTT_BROKER_HOST
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
            'timestamp': time.time(),
            'source': 'web'
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

@app.route('/api/device/<device_id>/set_color', methods=['POST'])
def api_set_device_color(device_id):
    """API: Установка цвета для устройства"""
    try:
        data = request.get_json()
        red = data.get('red', 0)
        green = data.get('green', 0)
        blue = data.get('blue', 0)
        
        success = storage.set_device_color(device_id, red, green, blue)
        if success:
            return jsonify({'status': 'success', 'message': f'Color set for {device_id}'})
        else:
            return jsonify({'status': 'error', 'message': f'Failed to set color for {device_id}'}), 500
            
    except Exception as e:
        logger.error(f"❌ Ошибка установки цвета: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/devices/mix_colors', methods=['POST'])
def api_mix_colors():
    """API: Перемешивание цветов"""
    try:
        result = storage.mix_colors()
        return jsonify(result)
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/device/<device_id>/reset_button', methods=['POST'])
def api_reset_button(device_id):
    """API: Сброс состояния кнопки"""
    try:
        topic = f"{Config.DEVICE_TOPIC_PREFIX}/{device_id}/command"
        mqtt_client.publish(topic, json.dumps({
            'command': 'RESET_BUTTON',
            'timestamp': time.time()
        }))
        return jsonify({'status': 'success', 'message': f'Button reset for {device_id}'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

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
        logger.info(f"🌐 Веб-интерфейс будет доступен по адресу: http://{LOCAL_IP}:{Config.WEB_PORT}")
        
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