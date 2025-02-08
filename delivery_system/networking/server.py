# delivery_system/networking/server.py
import socket
import json
import threading
from typing import Dict, Any
import signal

class DeliveryServer:
    def __init__(self, host: str = '0.0.0.0', port: int = 5001):
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.clients = []
        self.model = None
        self._running = True
        
        # Обработчик сигнала прерывания
        signal.signal(signal.SIGINT, self.shutdown)
        signal.signal(signal.SIGTERM, self.shutdown)
        
    def shutdown(self, signum, frame):
        """Корректное завершение работы сервера"""
        print("\nПолучен сигнал завершения работы...")
        self._running = False
        
        if self.model:
            print("Сохранение результатов...")
            try:
                self.model.save_results('data/results.csv')
                self.model.save_real_deliveries('real_deliveries')
                self.model.save_system_log('system_log')
                print("\nРезультаты сохранены в:")
                print("- data/results.csv")
                print("- data/real_deliveries.txt")
                print("- data/system_log.txt")
            except Exception as e:
                print(f"Ошибка при сохранении результатов: {e}")
        
        # Закрываем все клиентские соединения
        print("Закрываем все соединения...")
        for client in self.clients:
            try:
                client.close()
            except:
                pass
                
        # Закрываем серверный сокет
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
            self.sock.close()
        except:
            pass
            
        print("Сервер остановлен")
        
    def start(self):
        """Запуск сервера"""
        try:
            self.sock.bind((self.host, self.port))
            self.sock.listen(5)
            
            hostname = socket.gethostname()
            addresses = socket.getaddrinfo(hostname, None)
            print(f"\nСервер доступен по следующим адресам:")
            for addr in addresses:
                if addr[0] == socket.AF_INET:  # только IPv4
                    print(f"  {addr[4][0]}:{self.port}")
            
            print(f"\nОжидание подключений на {self.host}:{self.port}...")
            
            while self._running:
                try:
                    self.sock.settimeout(1.0)
                    try:
                        client, address = self.sock.accept()
                        print(f"\nНовое подключение с {address}")
                        print(f"Всего активных подключений: {len(self.clients) + 1}")
                        
                        self.clients.append(client)
                        client_thread = threading.Thread(
                            target=self.handle_client,
                            args=(client, address)
                        )
                        client_thread.daemon = True
                        client_thread.start()
                    except socket.timeout:
                        continue
                except Exception as e:
                    if self._running:
                        print(f"Ошибка при принятии подключения: {e}")
                        
        except Exception as e:
            print(f"Критическая ошибка сервера: {e}")
            raise
        finally:
            self.shutdown(None, None)
            
    def handle_client(self, client: socket.socket, address: tuple):
        """Обработка клиентских подключений"""
        try:
            while self._running:
                data = client.recv(4096)
                if not data:
                    break
                    
                message = json.loads(data.decode())
                response = self.process_message(message)
                client.send(json.dumps(response).encode())
        except Exception as e:
            print(f"Ошибка при обработке клиента {address}: {e}")
        finally:
            client.close()
            if client in self.clients:
                self.clients.remove(client)
            print(f"Клиент отключен: {address}")
            
  
    
    def process_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Обработка сообщений от клиентов"""
        try:
            if not self.model:
                return {'status': 'error', 'message': 'Model not initialized'}
                
            # Выполняем шаг симуляции при каждом запросе
            self.model.step()
                
            msg_type = message.get('type')
            if msg_type == 'get_store_status':
                store_id = message.get('store_id')
                # Находим магазин
                store = next((s for s in self.model.stores if s.unique_id == store_id), None)
                if store:
                    return {
                        'status': 'success',
                        'data': {
                            'store_id': store_id,
                            'inventory': store.inventory,
                            'requirements': store.product_requirements,
                            'delivery_windows': store.delivery_windows,
                            'name': store.name
                        }
                    }
                else:
                    return {'status': 'error', 'message': f'Store {store_id} not found'}
                    
            elif msg_type == 'get_vehicle_status':
                vehicle_id = message.get('vehicle_id')
                # Находим транспорт
                vehicle = next((v for v in self.model.vehicles if v.unique_id == vehicle_id), None)
                if vehicle:
                    return {
                        'status': 'success',
                        'data': {
                            'vehicle_id': vehicle_id,
                            'status': vehicle.status,
                            'current_load': vehicle.current_load,
                            'capacity': vehicle.capacity,
                            'destination': vehicle.destination.name if vehicle.destination else None
                        }
                    }
                else:
                    return {'status': 'error', 'message': f'Vehicle {vehicle_id} not found'}
                    
            else:
                return {
                    'status': 'error',
                    'message': f'Unknown message type: {msg_type}'
                }
                
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Error processing message: {str(e)}'
            }