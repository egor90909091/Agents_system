# delivery_system/model.py
import json
import csv
from datetime import datetime, timedelta
import random
from mesa import Model
from mesa.time import RandomActivation
from .agents import WarehouseAgent, StoreAgent, VehicleAgent
from .scheduler import DeliveryScheduler

# В model.py изменим класс DeliveryModel


# В model.py добавим метод сохранения лога и обновим step


class DeliveryModel(Model):
    def __init__(self, input_file: str):
        super().__init__()
        self.delivery_log = []

        # Добавляем модельное время
        self.current_time = datetime.strptime("09:00", "%H:%M")
        self.time_step = timedelta(minutes=15)

        # Загрузка данных
        with open(input_file, "r", encoding="utf-8") as f:
            self.data = json.load(f)

        # Инициализируем агентов
        self.init_agents()

        # Создаем планировщик
        self.scheduler = DeliveryScheduler(self)
        self.scheduler.generate_schedule()

        # Очищаем файл лога при старте
        with open("data/simulation_log.txt", "w", encoding="utf-8") as f:
            f.write("СИСТЕМА ДОСТАВКИ - ЛОГ РАБОТЫ\n")
            f.write("=" * 80 + "\n\n")

    def write_to_log(self):
        """Запись текущего состояния в файл лога"""
        with open("data/simulation_log.txt", "a", encoding="utf-8") as f:
            # Записываем временную метку
            f.write(f"\n🕒 ВРЕМЯ: {self.get_time_str()}\n")
            f.write("-" * 80 + "\n")

            # Записываем состояние магазинов
            f.write("\n📦 СОСТОЯНИЕ МАГАЗИНОВ:\n")
            for store in self.stores:
                f.write(f"\n  🏪 {store.name}:\n")
                # Запасы
                f.write("    Текущие запасы:\n")
                for product, amount in store.inventory.items():
                    required = store.product_requirements[product]
                    percentage = (amount / required * 100) if required > 0 else 0
                    status = (
                        "✅" if percentage >= 80 else "⚠️" if percentage >= 30 else "❗"
                    )
                    f.write(f"      • {product}: {amount}/{required} {status}\n")
                # Окна доставки
                f.write(
                    f"    Окна доставки: {', '.join(f'{start}:00-{end}:00' for start, end in store.delivery_windows)}\n"
                )

            # Записываем состояние транспорта
            f.write("\n🚚 СОСТОЯНИЕ ТРАНСПОРТА:\n")
            for vehicle in self.vehicles:
                status_text = {
                    "idle": "ожидает",
                    "en_route": "в пути",
                    "returning": "возвращается",
                }.get(vehicle.status, vehicle.status)

                load_info = (
                    ", ".join(
                        f"{product}: {amount}"
                        for product, amount in vehicle.current_load.items()
                    )
                    if vehicle.current_load
                    else "пусто"
                )

                destination_text = (
                    f" к {vehicle.destination.name}" if vehicle.destination else ""
                )
                f.write(
                    f"  • Машина #{vehicle.unique_id}: {status_text}{destination_text}\n"
                )
                f.write(f"    Загрузка: {load_info} (максимум: {vehicle.capacity})\n")

            # Записываем состояние склада
            f.write("\n📦 СОСТОЯНИЕ СКЛАДА:\n")
            for product, amount in self.warehouse.inventory.items():
                f.write(f"  • {product}: {amount}\n")

            # Активные заказы
            if self.warehouse.active_orders:
                f.write("\n📋 АКТИВНЫЕ ЗАКАЗЫ:\n")
                for store_name, orders in self.warehouse.active_orders.items():
                    f.write(f"  • {store_name}: {orders}\n")

            f.write("\n" + "=" * 80 + "\n")

    def step(self):
        """Один шаг симуляции"""
        # Продвигаем время на один шаг
        self.current_time += self.time_step

        # Если прошли сутки, начинаем новый день
        if self.current_time.hour >= 23 and self.current_time.minute >= 45:
            self.current_time = datetime.strptime("09:00", "%H:%M")

        print(f"\nМодельное время: {self.get_time_str()}")

        # Используем scheduler
        self.scheduler.step()
        self.simulate_events()

        # Записываем текущее состояние в лог
        self.write_to_log()

    def init_agents(self):
        """Инициализация всех агентов"""
        # Инициализация склада
        self.warehouse = WarehouseAgent(0, self, self.data["склад"]["inventory"])

        # Инициализация магазинов
        self.stores = []
        for store_data in self.data["stores"]:
            store = StoreAgent(
                store_data["id"],  # unique_id
                self,  # model
                store_data["delivery_windows"],  # delivery_windows
                store_data["product_requirements"],  # product_requirements
            )
            store.name = store_data["name"]
            self.stores.append(store)

            self.log_event(
                "store_status",
                store.name,
                "Новый магазин",
                f"Начальные требования: {store_data['product_requirements']}",
                "initialized",
            )

        # Инициализация транспорта
        self.vehicles = []
        for vehicle_data in self.data["vehicles"]:
            vehicle = VehicleAgent(vehicle_data["id"], self, vehicle_data["capacity"])
            self.vehicles.append(vehicle)

            self.log_event(
                "vehicle_status",
                f"vehicle_{vehicle_data['id']}",
                "Новая машина",
                f"Готов к работе. Вместимость: {vehicle_data['capacity']}",
                "idle",
            )

    def get_time_str(self) -> str:
        """Получение текущего времени в строковом формате"""
        return self.current_time.strftime("%H:%M")

    def simulate_events(self):
        """Симуляция различных событий в системе"""
        print(f"\nСимуляция в {self.get_time_str()}")

        # Сначала вызываем step() для всех магазинов
        for store in self.stores:
            store.step()

        # Проверяем и обрабатываем заказы от всех магазинов
        for store in self.stores:
            needed_products = store.check_inventory_and_make_order()
            if needed_products:
                print(f"Обработка заказа от {store.name}: {needed_products}")

                self.log_event(
                    "delivery_request",
                    store.name,
                    "Новый заказ",
                    f"Заказано: {needed_products}",
                    "pending",
                )

                # Обрабатываем заказ через склад
                self.warehouse.process_order(store, needed_products)

    def log_event(
        self, event_type: str, agent_id: str, event_desc: str, details: str, status: str
    ):
        """Логирование событий"""
        timestamp = self.get_time_str()
        self.delivery_log.append(
            {
                "timestamp": timestamp,
                "event_type": event_type,
                "agent_id": agent_id,
                "event_desc": event_desc,
                "details": details,
                "status": status,
            }
        )

    # В model.py добавим новый метод:

    def save_formatted_log(self, filename: str):
        """Сохранение отформатированного лога работы системы"""
        with open(filename, "w", encoding="utf-8") as f:
            f.write("СИСТЕМА ДОСТАВКИ - ЛОГ РАБОТЫ\n")
            f.write("=" * 80 + "\n\n")

            # Группируем события по времени
            events_by_time = {}
            for event in self.delivery_log:
                time = event["timestamp"]
                if time not in events_by_time:
                    events_by_time[time] = []
                events_by_time[time].append(event)

            # Выводим события в хронологическом порядке
            for time in sorted(events_by_time.keys()):
                f.write(f"\n🕒 ВРЕМЯ: {time}\n")
                f.write("-" * 80 + "\n")

                # Группируем события по типу
                store_events = []
                vehicle_events = []
                delivery_events = []
                other_events = []

                for event in events_by_time[time]:
                    if event["event_type"].startswith("store"):
                        store_events.append(event)
                    elif event["event_type"].startswith("vehicle"):
                        vehicle_events.append(event)
                    elif event["event_type"].startswith("delivery"):
                        delivery_events.append(event)
                    else:
                        other_events.append(event)

                # Выводим события магазинов
                if store_events:
                    f.write("\n📦 МАГАЗИНЫ:\n")
                    for event in store_events:
                        f.write(f"  • {event['agent_id']}: {event['event_desc']}\n")
                        f.write(f"    {event['details']}\n")

                # Выводим события транспорта
                if vehicle_events:
                    f.write("\n🚚 ТРАНСПОРТ:\n")
                    for event in vehicle_events:
                        f.write(
                            f"  • Машина {event['agent_id']}: {event['event_desc']}\n"
                        )
                        f.write(f"    {event['details']}\n")

                # Выводим события доставок
                if delivery_events:
                    f.write("\n🔄 ДОСТАВКИ:\n")
                    for event in delivery_events:
                        status_emoji = "✅" if event["status"] == "completed" else "⏳"
                        f.write(f"  • {status_emoji} {event['event_desc']}\n")
                        f.write(f"    {event['details']}\n")

                # Выводим остальные события
                if other_events:
                    f.write("\n📝 ПРОЧИЕ СОБЫТИЯ:\n")
                    for event in other_events:
                        f.write(f"  • {event['event_desc']}\n")
                        f.write(f"    {event['details']}\n")

                # Выводим текущее состояние системы
                f.write("\n📊 СОСТОЯНИЕ СИСТЕМЫ:\n")
                # Состояние магазинов
                for store in self.stores:
                    f.write(f"\n  🏪 {store.name}:\n")
                    f.write("    Запасы:\n")
                    for product, amount in store.inventory.items():
                        required = store.product_requirements[product]
                        percentage = (amount / required * 100) if required > 0 else 0
                        status = (
                            "✅"
                            if percentage >= 80
                            else "⚠️" if percentage >= 30 else "❗"
                        )
                        f.write(f"      • {product}: {amount}/{required} {status}\n")

                # Состояние транспорта
                f.write("\n  🚛 Транспорт:\n")
                for vehicle in self.vehicles:
                    status_text = {
                        "idle": "ожидает",
                        "en_route": "в пути",
                        "returning": "возвращается",
                    }.get(vehicle.status, vehicle.status)

                    destination = (
                        f" к {vehicle.destination.name}" if vehicle.destination else ""
                    )
                    load = (
                        f" (груз: {vehicle.current_load})"
                        if vehicle.current_load
                        else ""
                    )

                    f.write(
                        f"      • Машина {vehicle.unique_id}: {status_text}{destination}{load}\n"
                    )

                f.write("\n" + "-" * 80 + "\n")

            # Добавляем статистику в конец
            f.write("\n📈 ОБЩАЯ СТАТИСТИКА\n")
            f.write("=" * 80 + "\n")
            total_deliveries = len(
                [e for e in self.delivery_log if e["event_type"] == "delivery_complete"]
            )
            total_requests = len(
                [e for e in self.delivery_log if e["event_type"] == "delivery_request"]
            )
            f.write(f"Всего заказов: {total_requests}\n")
            f.write(f"Успешных доставок: {total_deliveries}\n")

    def get_formatted_state(self):
        """Получение текущего состояния системы в отформатированном виде"""
        state = []

        # Добавляем информацию о магазинах
        state.append("\nМАГАЗИНЫ:")
        for store in self.stores:
            store_info = [
                f"\nМагазин: {store.name}",
                f"Запасы/Требуемые: "
                + ", ".join(
                    f"{product}: {current}/{required}"
                    for product, current in store.inventory.items()
                    for required in [store.product_requirements[product]]
                ),
                f"Окна доставки: "
                + ", ".join(
                    f"{start}:00-{end}:00" for start, end in store.delivery_windows
                ),
            ]
            state.extend(store_info)

        # Добавляем информацию о транспорте
        state.append("\nТРАНСПОРТ:")
        for vehicle in self.vehicles:
            status_text = {
                "idle": "ожидает",
                "en_route": "в пути",
                "returning": "возвращается",
            }.get(vehicle.status, vehicle.status)

            load_info = (
                ", ".join(
                    f"{product}: {amount}"
                    for product, amount in vehicle.current_load.items()
                )
                if vehicle.current_load
                else "пусто"
            )

            destination_text = (
                f"к {vehicle.destination.name}" if vehicle.destination else ""
            )

            vehicle_info = [
                f"\nМашина #{vehicle.unique_id}",
                f"Статус: {status_text} {destination_text}",
                f"Загрузка: {load_info} (максимум: {vehicle.capacity})",
            ]
            state.extend(vehicle_info)

        return "\n".join(state)
