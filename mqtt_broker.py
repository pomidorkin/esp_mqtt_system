import subprocess
import os
import time
import socket
import sys

def get_resource_path(relative_path):
    """Получаем правильный путь к файлам (как в старом проекте)"""
    if hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class MQTTBroker:
    def __init__(self):
        self.process = None
        self.is_running = False
        
    def start_broker(self):
        """Запуск MQTT брокера (исправленная версия)"""
        try:
            # Проверяем доступность порта
            if self._is_port_in_use(1883):
                print("⚠️ MQTT порт уже занят, предполагаем что брокер запущен")
                self.is_running = True
                return True
            
            # Используем правильный путь как в старом проекте
            mosquitto_path = get_resource_path("mosquitto.exe")
            config_path = get_resource_path("mosquitto.conf")
            
            print(f"🔧 Поиск mosquitto: {mosquitto_path}")
            
            # Проверяем что файл существует
            if not os.path.exists(mosquitto_path):
                print(f"❌ Файл mosquitto.exe не найден по пути: {mosquitto_path}")
                return False
            
            # Создаем конфиг если его нет
            if not os.path.exists(config_path):
                print("📁 Создание конфиг файла...")
                with open(config_path, 'w') as f:
                    f.write("listener 1883 0.0.0.0\nallow_anonymous true\n")
            
            print("🚀 Запуск MQTT брокера...")
            
            # Настройки для скрытия окна (как в старом проекте)
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0  # SW_HIDE - скрыть окно
            
            # Запускаем mosquitto (проще, как в старом проекте)
            self.process = subprocess.Popen([
                mosquitto_path, 
                "-c", config_path,
                "-p", "1883"
            ], 
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.DEVNULL,
            startupinfo=startupinfo)
            
            # Даем время брокеру запуститься
            time.sleep(2)
            
            # Проверяем что процесс запустился
            if self.process.poll() is None:
                self.is_running = True
                print("✅ MQTT брокер запущен на порту 1883")
                return True
            else:
                print("❌ MQTT брокер не запустился")
                return False
                
        except Exception as e:
            print(f"❌ Ошибка запуска MQTT брокера: {e}")
            return False
    
    def stop_broker(self):
        """Остановка MQTT брокера"""
        try:
            if self.process and self.process.poll() is None:
                self.process.terminate()
                self.process.wait(timeout=5)
                print("✅ MQTT брокер остановлен")
            
            self.is_running = False
            
        except Exception as e:
            print(f"⚠️ Ошибка остановки MQTT брокера: {e}")
            if self.process:
                self.process.kill()
    
    def _is_port_in_use(self, port: int) -> bool:
        """Проверка занятости порта"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            return s.connect_ex(('localhost', port)) == 0