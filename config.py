import os
import sys

def get_resource_path(relative_path):
    """Получаем правильный путь к файлам"""
    if hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class Config:
    # MQTT настройки
    MQTT_BROKER_HOST = "localhost"
    MQTT_BROKER_PORT = 1883
    MQTT_KEEPALIVE = 60
    
    # Веб-сервер
    WEB_HOST = "0.0.0.0"
    WEB_PORT = 5000
    
    # Устройства
    DEVICE_TOPIC_PREFIX = "devices"
    
    # Пути (используем функцию get_resource_path)
    MOSQUITTO_PATH = get_resource_path("mosquitto.exe")
    MOSQUITTO_CONFIG_PATH = get_resource_path("mosquitto.conf")