# scripts/run_server.py
from delivery_system.networking.server import DeliveryServer
from delivery_system.model import DeliveryModel
import os


from delivery_system.networking.server import DeliveryServer
from delivery_system.model import DeliveryModel
import os


def main():
    # Файл находится в папке data в корне проекта
    input_file = "data/input_data.json"

    # Проверяем существование файла
    if not os.path.exists(input_file):
        print(f"Ошибка: Файл {input_file} не найден!")
        return

    model = DeliveryModel(input_file)
    server = DeliveryServer(host="0.0.0.0", port=5001)
    server.model = model

    print(f"Запуск сервера на localhost:5001...")
    server.start()


if __name__ == "__main__":
    main()
