# delivery_system/model.py
import json
import csv
from datetime import datetime, time, timedelta
import random
from mesa import Model
from mesa.time import RandomActivation
from mesa.space import MultiGrid
from .agents import WarehouseAgent, StoreAgent, VehicleAgent
from .scheduler import DeliveryScheduler

class DeliveryModel(Model):
    def __init__(self, input_file: str):
        super().__init__()
        self.schedule = RandomActivation(self)
        self.grid = MultiGrid(30, 30, True)
        self.delivery_log = []
        
        # Добавляем модельное время
        self.current_time = datetime.strptime("09:00", "%H:%M")  # Начинаем с 9 утра
        self.time_step = timedelta(minutes=15)  # Каждый шаг = 15 минут
        
        # Загрузка данных
        with open(input_file, 'r', encoding='utf-8') as f:
            self.data = json.load(f)
            
        # Инициализация агентов
        self.init_agents()
        
        # Добавляем планировщик
        self.scheduler = DeliveryScheduler(self)
        self.scheduler.generate_schedule()
        self.scheduler.save_schedule("delivery_schedule")
    
    
    def init_agents(self):
        """Инициализация всех агентов"""
        # Очищаем сетку перед инициализацией
        self.grid = MultiGrid(30, 30, True)

        # Инициализация склада
        warehouse_pos = tuple(self.data['склад']['location'])
        self.warehouse = WarehouseAgent(
            0,
            self,
            self.data['склад']['inventory']
        )
        self.warehouse.pos = None
        self.schedule.add(self.warehouse)
        self.grid.place_agent(self.warehouse, warehouse_pos)

        # Инициализация магазинов
        self.stores = []
        for store_data in self.data['stores']:
            store_pos = tuple(store_data['location'])
            store = StoreAgent(
                store_data['id'],
                self,
                None,
                store_data['delivery_windows'],
                store_data['product_requirements']
            )
            store.pos = None
            store.name = store_data['name']  # Добавляем имя магазина
            self.stores.append(store)
            self.schedule.add(store)
            self.grid.place_agent(store, store_pos)

            self.log_event(
                "store_status",
                f"{store.name}",  # Используем имя магазина вместо ID
                store_pos,
                f"Начальные требования: {store_data['product_requirements']}",
                "initialized"
            )

        # Инициализация транспорта
        self.vehicles = []
        for vehicle_data in self.data['vehicles']:
            vehicle = VehicleAgent(
                vehicle_data['id'],
                self,
                vehicle_data['capacity']
            )
            vehicle.pos = None
            self.vehicles.append(vehicle)
            self.schedule.add(vehicle)
            self.grid.place_agent(vehicle, warehouse_pos)

            self.log_event(
                "vehicle_status",
                f"vehicle_{vehicle_data['id']}",
                warehouse_pos,
                f"Готов к работе. Вместимость: {vehicle_data['capacity']}",
                "idle"
            )

    # В классе DeliveryModel добавьте этот метод
    def save_system_log(self, filename: str):
        """Сохранение подробного лога работы системы"""
        try:
            with open(f"data/{filename}.txt", 'w', encoding='utf-8') as f:
                f.write("ПОДРОБНЫЙ ЛОГ РАБОТЫ СИСТЕМЫ ДОСТАВКИ\n")
                f.write("=" * 50 + "\n\n")

                prev_time = None
                for event in self.delivery_log:
                    time = event['timestamp']
                    
                    # Добавляем разделитель между разными временными отметками
                    if time != prev_time:
                        f.write(f"\nМодельное время: {time}\n")
                        f.write("-" * 30 + "\n")
                        prev_time = time

                    # Записываем событие
                    f.write(f"{event['event_type']}: {event['details']}\n")
                    
                    # Если это последнее событие для данного времени, добавляем состояние системы
                    next_event_time = next((e['timestamp'] for e in self.delivery_log[self.delivery_log.index(event)+1:]), None)
                    if next_event_time != time:
                        # Состояние магазинов
                        f.write("\nСостояние магазинов:\n")
                        for store in self.stores:
                            f.write(f"{store.name} - Запасы: {store.inventory}\n")
                        
                        # Состояние машин
                        f.write("\nСостояние машин:\n")
                        for vehicle in self.vehicles:
                            status_text = {
                                "en_route": "в пути",
                                "returning": "возвращается",
                                "idle": "ожидает"
                            }.get(vehicle.status, vehicle.status)
                            
                            destination = f" к {vehicle.destination.name}" if vehicle.destination else ""
                            f.write(f"Машина {vehicle.unique_id}: {status_text}{destination}\n")
                        
                        f.write("=" * 30 + "\n")

                # Общая статистика
                f.write("\nОБЩАЯ СТАТИСТИКА\n")
                f.write("=" * 30 + "\n")
                total_deliveries = len([e for e in self.delivery_log if e['event_type'] == 'delivery_complete'])
                total_requests = len([e for e in self.delivery_log if e['event_type'] == 'delivery_request'])
                f.write(f"Всего заказов: {total_requests}\n")
                f.write(f"Успешных доставок: {total_deliveries}\n")

        except Exception as e:
            print(f"Ошибка при сохранении лога: {e}")
            
    def get_time_str(self) -> str:
        """Получение текущего времени в строковом формате"""
        return self.current_time.strftime("%H:%M")

    # В классе DeliveryModel
    def simulate_events(self):
        """Симуляция различных событий в системе"""
        print(f"Симуляция в {self.get_time_str()}")
        
        # Случайный магазин делает заказ
        if random.random() < 0.3:  # 30% шанс на каждом шаге
            store = random.choice(self.stores)
            products = {
                'молоко': random.randint(10, 50),
                'хлеб': random.randint(10, 50),
                'вода': random.randint(10, 50)
            }
            print(f"Создан заказ для {store.name}: {products}")
            
            self.log_event(
                "delivery_request",
                store.name,
                store.pos,
                f"Заказано: {products}",
                "pending"
            )
            
            # Находим свободную машину
            for vehicle in self.vehicles:
                if vehicle.status == "idle":
                    # Отправляем машину
                    print(f"Машина {vehicle.unique_id} отправлена с заказом")
                    vehicle.load_delivery(products, store)  # Используем метод load_delivery
                    break
            else:
                print("Нет свободных машин")
                
        # Обновление состояния склада
        if random.random() < 0.2:  # 20% шанс
            self.log_event(
                "warehouse_status",
                "Склад",
                self.warehouse.pos,
                f"Текущие запасы: {self.warehouse.inventory}",
                "updated"
            )
    def step(self):
        """Один шаг симуляции"""
        # Продвигаем время на один шаг
        self.current_time += self.time_step
        
        # Если прошли сутки, начинаем новый день
        if self.current_time.hour >= 23 and self.current_time.minute >= 45:
            self.current_time = datetime.strptime("09:00", "%H:%M")
            
        print(f"\nМодельное время: {self.get_time_str()}")
        print("Выполняем шаг симуляции...")
        
        # Показываем состояние машин
        for vehicle in self.vehicles:
            if vehicle.status != "idle":
                print(f"Машина {vehicle.unique_id}: {vehicle.status}, " +
                    (f"направляется в {vehicle.destination.name}" if vehicle.destination else "возвращается"))
        
        self.schedule.step()
        self.simulate_events()
        
        # Показываем состояние магазинов
        for store in self.stores:
            print(f"{store.name} - Запасы: {store.inventory}")



    def log_event(self, event_type: str, agent_id: str, location: tuple, 
                  details: str, status: str):
        """Логирование событий"""
        timestamp = self.get_time_str()
        self.delivery_log.append({
            'timestamp': timestamp,
            'event_type': event_type,
            'agent_id': agent_id,
            'location': str(location),
            'details': details,
            'status': status
        })
        
    def save_results(self, output_file: str):
        """Сохранение результатов"""
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'timestamp', 'event_type', 'agent_id', 'location', 
                'details', 'status'
            ])
            writer.writeheader()
            for event in self.delivery_log:
                writer.writerow(event)
                
    def save_real_deliveries(self, filename: str):
        """Сохранение реальных результатов доставок"""
        # Фильтруем логи, оставляем только события доставки
        delivery_events = [
            event for event in self.delivery_log 
            if event['event_type'] in ['delivery_complete', 'delivery_waiting', 'delivery_rejected']
        ]
        
        print(f"\nВсего событий в логе: {len(self.delivery_log)}")
        print(f"Из них события доставки: {len(delivery_events)}")
        print("\nТипы событий в логе:")
        event_types = set(event['event_type'] for event in self.delivery_log)
        for event_type in event_types:
            count = len([e for e in self.delivery_log if e['event_type'] == event_type])
            print(f"- {event_type}: {count}")
        
        with open(f"data/{filename}.txt", 'w', encoding='utf-8') as f:
            f.write("РЕАЛЬНЫЕ РЕЗУЛЬТАТЫ ДОСТАВОК\n")
            f.write("=" * 50 + "\n\n")
            
            if delivery_events:
                f.write(f"Период симуляции: {delivery_events[0]['timestamp']} - {delivery_events[-1]['timestamp']}\n\n")
            else:
                f.write("Доставок пока не было\n\n")
            
            # Группируем события по магазинам
            for store in self.stores:
                store_events = [
                    event for event in delivery_events 
                    if store.name in event['agent_id']
                ]
                
                f.write(f"Магазин: {store.name}\n")
                f.write("-" * 30 + "\n")
                f.write(f"Временные окна доставки: {store.delivery_windows}\n")
                f.write(f"Требуемые товары: {store.product_requirements}\n")
                f.write(f"Текущий запас: {store.inventory}\n")
                f.write("\nИстория доставок:\n")
                
                for event in store_events:
                    f.write(f"\nВремя: {event['timestamp']}\n")
                    f.write(f"Статус: {event['status']}\n")
                    f.write(f"Детали: {event['details']}\n")
                    
                f.write("\n" + "=" * 30 + "\n\n")
                
            # Общая статистика
            successful_deliveries = len([e for e in delivery_events if e['status'] == 'completed'])
            rejected_deliveries = len([e for e in delivery_events if e['status'] == 'rejected'])
            waiting_deliveries = len([e for e in delivery_events if e['status'] == 'waiting'])
            
            f.write("\nОБЩАЯ СТАТИСТИКА\n")
            f.write("=" * 50 + "\n")
            f.write(f"Успешных доставок: {successful_deliveries}\n")
            f.write(f"Отклоненных доставок: {rejected_deliveries}\n")
            f.write(f"Ожидающих доставок: {waiting_deliveries}\n")