import time
import json
from typing import Dict, List
from dataclasses import dataclass
from collections import defaultdict

@dataclass
class Device:
    device_id: str
    device_type: str
    ip_address: str
    status: str
    last_seen: float
    attributes: dict

class DeviceManager:
    def __init__(self):
        self.devices: Dict[str, Device] = {}
        self.device_types = defaultdict(list)
        
    def register_device(self, device_id: str, device_type: str, ip_address: str, attributes: dict = None):
        """Регистрация нового устройства"""
        device = Device(
            device_id=device_id,
            device_type=device_type,
            ip_address=ip_address,
            status="connected",
            last_seen=time.time(),
            attributes=attributes or {}
        )
        
        self.devices[device_id] = device
        self.device_types[device_type].append(device_id)
        
        print(f"✅ Устройство зарегистрировано: {device_id} ({device_type})")
        return device
    
    def update_device_status(self, device_id: str, status: str, attributes: dict = None):
        """Обновление статуса устройства"""
        if device_id in self.devices:
            self.devices[device_id].status = status
            self.devices[device_id].last_seen = time.time()
            
            if attributes:
                self.devices[device_id].attributes.update(attributes)
                
            print(f"📡 Статус обновлен: {device_id} -> {status}")
    
    def remove_device(self, device_id: str):
        """Удаление устройства"""
        if device_id in self.devices:
            device_type = self.devices[device_id].device_type
            if device_id in self.device_types[device_type]:
                self.device_types[device_type].remove(device_id)
            del self.devices[device_id]
            print(f"🗑️ Устройство удалено: {device_id}")
    
    def get_online_devices(self) -> List[Device]:
        """Получение списка онлайн устройств"""
        current_time = time.time()
        online_devices = []
        
        for device in self.devices.values():
            if current_time - device.last_seen < 60:  # 60 секунд таймаут
                online_devices.append(device)
            else:
                device.status = "disconnected"
                
        return online_devices
    
    def get_device_count(self) -> dict:
        """Статистика по устройствам"""
        online_count = len(self.get_online_devices())
        type_count = {}
        
        for device_type, devices in self.device_types.items():
            type_count[device_type] = len([d for d in devices if self.devices[d].status == "connected"])
        
        return {
            "total": len(self.devices),
            "online": online_count,
            "by_type": type_count
        }