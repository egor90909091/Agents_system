# scripts/run_server.py
from delivery_system.networking.server import DeliveryServer
from delivery_system.model import DeliveryModel
import os


def main():
    # Создаем директорию для данных, если её нет
    os.makedirs("data", exist_ok=True)

    # Инициализируем модель с данными из файла
    input_file = "data/input_data.json"

    # Проверяем существование файла
    if not os.path.exists(input_file):
        print(f"Ошибка: Файл {input_file} не найден!")
        return

    model = DeliveryModel(input_file)
    server = DeliveryServer(host="0.0.0.0", port=5001)
    server.model = model

    print(f"Запуск сервера на localhost:5000...")
    server.start()


if __name__ == "__main__":
    main()
