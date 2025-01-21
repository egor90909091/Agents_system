# scripts/run_server.py
from delivery_system.networking.server import DeliveryServer
from delivery_system.model import DeliveryModel
import os

def main():
    # Создаем директорию для данных, если её нет
    os.makedirs('data', exist_ok=True)
    
    # Инициализируем модель с данными из файла
    input_file = 'data/input_data.json'
    
    # Проверяем существование файла с данными
    if not os.path.exists(input_file):
        print(f"Ошибка: Файл {input_file} не найден!")
        return
    
    model = DeliveryModel(input_file)
    
    # Создаем и запускаем сервер
    server = DeliveryServer(host='0.0.0.0', port=5000)
    server.model = model
    
    print(f"Запуск сервера на localhost:5000...")
    try:
        server.start()
    except KeyboardInterrupt:
        print("\nСохранение результатов...")
        # Сохраняем результаты во все файлы
        model.save_results('data/results.csv')
        model.save_real_deliveries('real_deliveries')
        print("Результаты сохранены в:")
        print("- data/results.csv")
        print("- data/real_deliveries.txt")
        print("\nСервер остановлен")
    except Exception as e:
        print(f"\nОшибка: {e}")
        print("Попытка сохранить результаты...")
        model.save_results('data/results.csv')
        model.save_real_deliveries('real_deliveries')

if __name__ == "__main__":
    main()