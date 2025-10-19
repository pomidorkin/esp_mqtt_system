# main_launcher.py - ОБНОВЛЕННАЯ ВЕРСИЯ
import sys
import os
import time
import atexit
import signal
from mqtt_broker import MQTTBroker
from web_server import start_web_server
import threading
from config import Config  # Импортируем автоматический конфиг

class SystemLauncher:
    def __init__(self):
        self.mqtt_broker = MQTTBroker()
        self.is_running = False
        
    def cleanup(self):
        """Очистка ресурсов при завершении"""
        print("\n🧹 Завершение работы системы...")
        self.mqtt_broker.stop_broker()
        self.is_running = False
        print("✅ Система остановлена")
    
    def wait_for_mqtt(self, timeout=30):
        """Ожидание запуска MQTT брокера"""
        print("⏳ Ожидание запуска MQTT брокера...")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.mqtt_broker.is_running:
                print("✅ MQTT брокер готов")
                return True
            time.sleep(1)
        
        print("❌ Таймаут ожидания MQTT брокера")
        return False
    
    def start(self):
        """Запуск всей системы"""
        print("=" * 50)
        print("🚀 СИСТЕМА УПРАВЛЕНИЯ ESP УСТРОЙСТВАМИ")
        print("=" * 50)
        
        # Показываем автоматическую конфигурацию
        print(f"📍 Автоопределенный IP: {Config.LOCAL_IP}")
        print(f"🔗 MQTT брокер: {Config.MQTT_BROKER_HOST}:{Config.MQTT_BROKER_PORT}")
        print(f"🌐 Веб-интерфейс: {Config.WEB_URL}")
        print("=" * 50)
        
        # Регистрируем обработчики завершения
        atexit.register(self.cleanup)
        signal.signal(signal.SIGINT, lambda s, f: self.cleanup())
        
        # Запускаем MQTT брокер
        if not self.mqtt_broker.start_broker():
            print("❌ Не удалось запустить MQTT брокер")
            return
        
        # Ждем запуска брокера
        if not self.wait_for_mqtt():
            self.cleanup()
            return
        
        # Запускаем веб-сервер в отдельном потоке
        print("🌐 Запуск веб-интерфейса...")
        web_thread = threading.Thread(target=start_web_server, daemon=True)
        web_thread.start()
        
        print("✅ Система успешно запущена!")
        print(f"📱 Веб-интерфейс: {Config.WEB_URL}")
        print("💡 Убедитесь, что ESP устройства в той же WiFi сети")
        print("⏹️  Для остановки нажмите Ctrl+C")
        
        self.is_running = True
        
        # Главный цикл
        try:
            while self.is_running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.cleanup()

if __name__ == "__main__":
    launcher = SystemLauncher()
    launcher.start()