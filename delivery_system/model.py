# delivery_system/model.py
import json
import csv
from datetime import datetime, timedelta
import random
from mesa import Model
from mesa.time import RandomActivation
from .agents import WarehouseAgent, StoreAgent, VehicleAgent
from .scheduler import DeliveryScheduler

class DeliveryModel(Model):
    def __init__(self, input_file: str):
        super().__init__()
        self.delivery_log = []
        
        # Добавляем модельное время
        self.current_time = datetime.strptime("09:00", "%H:%M")  
        self.time_step = timedelta(minutes=15)  
        
        # Загрузка данных
        with open(input_file, 'r', encoding='utf-8') as f:
            self.data = json.load(f)
            
        # Сначала инициализируем агентов
        self.init_agents()
        
        # Затем создаем планировщик, когда все агенты уже созданы
        self.scheduler = DeliveryScheduler(self)
        self.scheduler.generate_schedule()
        self.scheduler.save_schedule("delivery_schedule")

    def init_agents(self):
        """Инициализация всех агентов"""
        # Инициализация склада
        self.warehouse = WarehouseAgent(0, self, self.data['склад']['inventory'])
        
        # Инициализация магазинов
        self.stores = []
        for store_data in self.data['stores']:
            store = StoreAgent(
                store_data['id'],  # unique_id
                self,              # model
                store_data['delivery_windows'],      # delivery_windows
                store_data['product_requirements']   # product_requirements
            )
            store.name = store_data['name']
            self.stores.append(store)
            
            self.log_event(
                "store_status",
                store.name,
                "Новый магазин",
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
            self.vehicles.append(vehicle)
            
            self.log_event(
                "vehicle_status",
                f"vehicle_{vehicle_data['id']}",
                "Новая машина",
                f"Готов к работе. Вместимость: {vehicle_data['capacity']}",
                "idle"
            )
    def get_time_str(self) -> str:
        """Получение текущего времени в строковом формате"""
        return self.current_time.strftime("%H:%M")

    
    def simulate_events(self):
        """Симуляция различных событий в системе"""
        print(f"\nСимуляция в {self.get_time_str()}")
        
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
                    "pending"
                )
                
                # Обрабатываем заказ через склад
                self.warehouse.process_order(store, needed_products)
                    
        # Обновление состояния склада
        if random.random() < 0.2:  # 20% шанс
            self.log_event(
                "warehouse_status",
                "Склад",
                "Обновление статуса",
                f"Текущие запасы: {self.warehouse.inventory}\nАктивные заказы: {self.warehouse.active_orders}",
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
        
        # Используем scheduler вместо schedule
        self.scheduler.step()
        self.simulate_events()
        
    def log_event(self, event_type: str, agent_id: str, event_desc: str, 
                  details: str, status: str):
        """Логирование событий"""
        timestamp = self.get_time_str()
        self.delivery_log.append({
            'timestamp': timestamp,
            'event_type': event_type,
            'agent_id': agent_id,
            'event_desc': event_desc,
            'details': details,
            'status': status
        })
        
    def save_results(self, output_file: str):
        """Сохранение результатов"""
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'timestamp', 'event_type', 'agent_id', 'event_desc', 
                'details', 'status'
            ])
            writer.writeheader()
            for event in self.delivery_log:
                writer.writerow(event)
                
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
                    f.write(f"{event['event_type']} - {event['event_desc']}: {event['details']}\n")
                    
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
            
    def save_real_deliveries(self, filename: str):
        """Сохранение реальных результатов доставок"""
        delivery_events = [
            event for event in self.delivery_log 
            if event['event_type'] in ['delivery_complete', 'delivery_waiting', 'delivery_rejected']
        ]
        
        with open(f"data/{filename}.txt", 'w', encoding='utf-8') as f:
            f.write("РЕАЛЬНЫЕ РЕЗУЛЬТАТЫ ДОСТАВОК\n")
            f.write("=" * 50 + "\n\n")
            
            if delivery_events:
                f.write(f"Период симуляции: {delivery_events[0]['timestamp']} - {delivery_events[-1]['timestamp']}\n\n")
            else:
                f.write("Доставок пока не было\n\n")
            
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
                
            successful_deliveries = len([e for e in delivery_events if e['status'] == 'completed'])
            rejected_deliveries = len([e for e in delivery_events if e['status'] == 'rejected'])
            waiting_deliveries = len([e for e in delivery_events if e['status'] == 'waiting'])
            
            f.write("\nОБЩАЯ СТАТИСТИКА\n")
            f.write("=" * 50 + "\n")
            f.write(f"Успешных доставок: {successful_deliveries}\n")
            f.write(f"Отклоненных доставок: {rejected_deliveries}\n")
            f.write(f"Ожидающих доставок: {waiting_deliveries}\n")