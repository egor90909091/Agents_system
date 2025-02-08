# scripts/run_client.py
from delivery_system.networking.client import DeliveryClient
import argparse
import time


def format_store_status(response):
    """Форматирование статуса магазина"""
    if response["status"] != "success":
        return f"Ошибка: {response.get('message', 'Неизвестная ошибка')}"

    data = response["data"]
    store_name = data["name"]
    inventory = data["inventory"]
    requirements = data["requirements"]

    # Формируем строки для каждого продукта
    products_info = []
    for product in inventory:
        current = inventory[product]
        required = requirements[product]
        products_info.append(f"{product}: {current}/{required}")

    # Форматируем временные окна
    windows = [f"{start}:00-{end}:00" for start, end in data["delivery_windows"]]

    return (
        f"\nМагазин: {store_name}\n"
        f"Запасы/Требуемые: {', '.join(products_info)}\n"
        f"Окна доставки: {', '.join(windows)}"
    )


def format_vehicle_status(response):
    """Форматирование статуса машины"""
    if response["status"] != "success":
        return f"Ошибка: {response.get('message', 'Неизвестная ошибка')}"

    data = response["data"]
    vehicle_id = data["vehicle_id"]
    status = data["status"]
    load = data["current_load"]
    destination = data["destination"]
    capacity = data["capacity"]

    # Переводим статусы на русский
    status_names = {
        "idle": "ожидает",
        "en_route": "в пути",
        "returning": "возвращается",
        "waiting_for_window": "ожидает окно доставки",
    }

    # Форматируем информацию о грузе
    load_info = (
        ", ".join(f"{product}: {amount}" for product, amount in load.items())
        if load
        else "пусто"
    )

    status_text = status_names.get(status, status)
    destination_text = f"к {destination}" if destination else ""

    return (
        f"\nМашина #{vehicle_id}\n"
        f"Статус: {status_text} {destination_text}\n"
        f"Загрузка: {load_info} (максимум: {capacity})"
    )


def main():
    parser = argparse.ArgumentParser(description="Клиент системы доставки")
    parser.add_argument(
        "--server",
        type=str,
        default="localhost",
        help="IP-адрес сервера (по умолчанию: localhost)",
    )
    parser.add_argument(
        "--port", type=int, default=5001, help="Порт сервера (по умолчанию: 5001)"
    )

    args = parser.parse_args()
    client = DeliveryClient(host=args.server, port=args.port)

    print(f"Подключение к серверу {args.server}:{args.port}")

    try:
        client.connect()
        print("Успешное подключение к серверу!")

        while True:
            print("\nСТАТУС СИСТЕМЫ")
            print("=" * 50)

            # Запрашиваем статус магазинов
            print("\nМАГАЗИНЫ:")
            for store_id in [1, 2]:
                request = {"type": "get_store_status", "store_id": store_id}
                response = client.send_message(request)
                print(format_store_status(response))

            # Запрашиваем статус машин
            print("\nТРАНСПОРТ:")
            for vehicle_id in [1, 2]:  # Предполагаем, что у нас две машины
                request = {"type": "get_vehicle_status", "vehicle_id": vehicle_id}
                response = client.send_message(request)
                print(format_vehicle_status(response))

            print("\n" + "=" * 50)
            time.sleep(5)  # Пауза между обновлениями

    except ConnectionRefusedError:
        print(f"Ошибка: Не удалось подключиться к серверу {args.server}:{args.port}")
    except KeyboardInterrupt:
        print("\nЗавершение работы клиента...")
    finally:
        client.disconnect()
        print("Клиент остановлен")


if __name__ == "__main__":
    main()
