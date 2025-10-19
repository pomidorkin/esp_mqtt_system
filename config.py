# config.py - ПЕРЕРАБОТАННАЯ ВЕРСИЯ
import os
import sys
import socket

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

def get_resource_path(relative_path):
    """Получаем правильный путь к файлам"""
    if hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# АВТОМАТИЧЕСКОЕ ОПРЕДЕЛЕНИЕ СЕТЕВЫХ НАСТРОЕК
LOCAL_IP = get_local_ip()
MQTT_BROKER_IP = LOCAL_IP  # Используем тот же IP для брокера

class Config:
    # MQTT настройки - АВТООПРЕДЕЛЕНИЕ
    MQTT_BROKER_HOST = MQTT_BROKER_IP
    MQTT_BROKER_PORT = 1883
    MQTT_KEEPALIVE = 60
    
    # Веб-сервер
    WEB_HOST = "0.0.0.0"
    WEB_PORT = 5000
    
    # Устройства
    DEVICE_TOPIC_PREFIX = "devices"
    
    # Пути
    MOSQUITTO_PATH = get_resource_path("mosquitto.exe")
    MOSQUITTO_CONFIG_PATH = get_resource_path("mosquitto.conf")
    
    # Информация для отображения
    LOCAL_IP = LOCAL_IP
    WEB_URL = f"http://{LOCAL_IP}:{WEB_PORT}"

# Выводим информацию о конфигурации
print("=" * 50)
print("🌐 АВТОМАТИЧЕСКАЯ КОНФИГУРАЦИЯ СИСТЕМЫ")
print(f"📍 Локальный IP: {LOCAL_IP}")
print(f"🔗 MQTT брокер: {MQTT_BROKER_IP}:1883")
print(f"🌐 Веб-интерфейс: http://{LOCAL_IP}:5000")
print("=" * 50)