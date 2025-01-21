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
        
    def get_time_str(self) -> str:
        """Получение текущего времени в строковом формате"""
        return self.current_time.strftime("%H:%M")


    def init_agents(self):
        """Инициализация всех агентов"""
        # Очищаем сетку перед инициализацией
        self.grid = MultiGrid(30, 30, True)  

        # Инициализация склада
        warehouse_pos = tuple(self.data['warehouse']['location'])
        self.warehouse = WarehouseAgent(
            0, 
            self, 
            self.data['warehouse']['inventory']
        )
        self.warehouse.pos = None  # Явно устанавливаем позицию в None
        self.schedule.add(self.warehouse)
        self.grid.place_agent(self.warehouse, warehouse_pos)
        
        # Инициализация магазинов
        self.stores = []
        for store_data in self.data['stores']:
            store_pos = tuple(store_data['location'])
            store = StoreAgent(
                store_data['id'],
                self,
                None,  # Позиция будет установлена позже через place_agent
                store_data['delivery_windows'],
                store_data['product_requirements']
            )
            store.pos = None  # Явно устанавливаем позицию в None
            self.stores.append(store)
            self.schedule.add(store)
            self.grid.place_agent(store, store_pos)
            
            self.log_event(
                "store_status",
                f"store_{store_data['id']}",
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
            vehicle.pos = None  # Явно устанавливаем позицию в None
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
    def simulate_events(self):
        """Симуляция различных событий в системе"""
        # Случайный магазин делает заказ
        if random.random() < 0.3:  # 30% шанс на каждом шаге
            store = random.choice(self.stores)
            products = {
                'product1': random.randint(10, 50),
                'product2': random.randint(10, 50),
                'product3': random.randint(10, 50)
            }
            self.log_event(
                "delivery_request",
                f"store_{store.unique_id}",
                store.pos,
                f"Заказано: {products}",
                "pending"
            )
            
            # Находим свободную машину
            for vehicle in self.vehicles:
                if vehicle.status == "idle":
                    # Отправляем машину
                    vehicle.status = "en_route"
                    self.log_event(
                        "vehicle_dispatch",
                        f"vehicle_{vehicle.unique_id}",
                        vehicle.pos,
                        f"Отправлен с заказом {products} в магазин {store.unique_id}",
                        "en_route"
                    )
                    break
                    
        # Обновление состояния склада
        if random.random() < 0.2:  # 20% шанс
            self.log_event(
                "warehouse_status",
                "warehouse_0",
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
            
        print(f"Модельное время: {self.get_time_str()}")
        
        self.schedule.step()
        self.simulate_events()
        
    def log_event(self, event_type: str, agent_id: str, location: tuple, 
                  details: str, status: str):
        """Логирование событий"""
        timestamp = self.get_time_str()  # Используем модельное время
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
        
        with open(f"data/{filename}.txt", 'w', encoding='utf-8') as f:
            f.write("РЕАЛЬНЫЕ РЕЗУЛЬТАТЫ ДОСТАВОК\n")
            f.write("=" * 50 + "\n\n")
            
            if delivery_events:  # Проверяем, есть ли события
                f.write(f"Период симуляции: {delivery_events[0]['timestamp']} - {delivery_events[-1]['timestamp']}\n\n")
            else:
                f.write("Доставок пока не было\n\n")
            
            # Группируем события по магазинам
            for store in self.stores:
                store_events = [
                    event for event in delivery_events 
                    if f"store_{store.unique_id}" in event['agent_id']
                ]
                
                f.write(f"Магазин #{store.unique_id}\n")
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