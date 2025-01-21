# delivery_system/networking/client.py
import socket
import json
from typing import Dict, Any

class DeliveryClient:
    def __init__(self, host: str = 'localhost', port: int = 5000):
        self.host = host
        self.port = port
        self.sock = None
        
    def connect(self):
        """Подключение к серверу"""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.host, self.port))
        
    def disconnect(self):
        """Отключение от сервера"""
        if self.sock:
            self.sock.close()
            self.sock = None
            
    def send_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Отправка сообщения серверу"""
        if not self.sock:
            raise ConnectionError("Not connected to server")
            
        try:
            # Отправляем сообщение
            self.sock.send(json.dumps(message).encode())
            
            # Получаем ответ
            response = self.sock.recv(4096)
            return json.loads(response.decode())
        except Exception as e:
            raise ConnectionError(f"Error communicating with server: {e}")
            
    def get_store_status(self, store_id: int) -> Dict[str, Any]:
        """Получение статуса магазина"""
        message = {
            'type': 'get_store_status',
            'store_id': store_id
        }
        return self.send_message(message)
        
    def get_vehicle_status(self, vehicle_id: int) -> Dict[str, Any]:
        """Получение статуса транспортного средства"""
        message = {
            'type': 'get_vehicle_status',
            'vehicle_id': vehicle_id
        }
        return self.send_message(message)