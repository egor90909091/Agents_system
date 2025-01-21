# scripts/run_client.py
from delivery_system.networking.client import DeliveryClient
import argparse
import time
import json

def main():
    # Создаем парсер аргументов командной строки
    parser = argparse.ArgumentParser(description='Клиент системы доставки')
    parser.add_argument('--server', type=str, default='localhost',
                      help='IP-адрес сервера (по умолчанию: localhost)')
    parser.add_argument('--port', type=int, default=5000,
                      help='Порт сервера (по умолчанию: 5000)')
    
    args = parser.parse_args()
    
    # Создаем клиент с указанными параметрами подключения
    client = DeliveryClient(host=args.server, port=args.port)
    
    print(f"Подключение к серверу {args.server}:{args.port}")
    
    try:
        client.connect()
        print("Успешное подключение к серверу!")
        
        while True:  # Бесконечный цикл для поддержания соединения
            test_requests = [
                {
                    'type': 'get_store_status',
                    'store_id': 1
                },
                {
                    'type': 'get_store_status',
                    'store_id': 2
                }
            ]
            
            for request in test_requests:
                print("\nОтправка запроса:", request)
                response = client.send_message(request)
                print("Получен ответ:", response)
                time.sleep(5)  # Пауза между запросами
            
    except ConnectionRefusedError:
        print(f"Ошибка: Не удалось подключиться к серверу {args.server}:{args.port}")
        print("Убедитесь, что сервер запущен и доступен.")
    except KeyboardInterrupt:
        print("\nЗавершение работы клиента...")
    finally:
        print("Отключение от сервера...")
        client.disconnect()
        print("Клиент остановлен")

if __name__ == "__main__":
    main()