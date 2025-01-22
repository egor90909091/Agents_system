# delivery_system/agents.py
from mesa import Agent
from datetime import datetime, time
import random

class WarehouseAgent(Agent):
    def __init__(self, unique_id, model, inventory):
        super().__init__(unique_id, model)
        self.inventory = inventory
        self.available_vehicles = []
        self.min_stock = 50
        self.pos = None
        
    def update_inventory(self):
        """Обновление запасов склада"""
        for product, amount in self.inventory.items():
            if amount < self.min_stock:
                restock_amount = random.randint(50, 100)
                self.inventory[product] += restock_amount
                self.model.log_event(
                    event_type="inventory_restock",
                    agent_id=f"warehouse_{self.unique_id}",
                    location=self.pos,
                    details=f"Пополнение {product}: +{restock_amount}",
                    status="restocked"
                )
    
    def coordinate_deliveries(self):
        """Координация доставок"""
        for store in self.model.stores:
            for product, required in store.product_requirements.items():
                if store.inventory.get(product, 0) < required:
                    if self.inventory.get(product, 0) >= required:
                        for vehicle in self.model.vehicles:
                            if vehicle.status == "idle":
                                amount_to_deliver = required - store.inventory.get(product, 0)
                                vehicle.load_delivery({product: amount_to_deliver}, store)
                                self.inventory[product] -= amount_to_deliver
                                break
    
    def step(self):
        self.update_inventory()
        self.coordinate_deliveries()

class StoreAgent(Agent):
    def __init__(self, unique_id, model, location, delivery_windows, product_requirements):
        super().__init__(unique_id, model)
        self.location = location  # Сохраняем желаемую локацию
        self.pos = None  # Текущая позиция изначально None
        self.delivery_windows = delivery_windows
        self.product_requirements = product_requirements
        self.inventory = {product: 0 for product in product_requirements}
        
    def can_accept_delivery(self) -> bool:
        """Проверка, может ли магазин принять доставку в текущее время"""
        current_hour = self.model.current_time.hour
        
        # Проверяем каждое окно доставки
        for start_hour, end_hour in self.delivery_windows:
            if start_hour <= current_hour < end_hour:
                self.model.log_event(
                    event_type="delivery_window",
                    agent_id=f"store_{self.unique_id}",
                    location=self.pos,
                    details=f"Доступно окно доставки {start_hour}:00-{end_hour}:00 (текущее время {self.model.get_time_str()})",
                    status="available"
                )
                return True
        
        self.model.log_event(
            event_type="delivery_window",
            agent_id=f"store_{self.unique_id}",
            location=self.pos,
            details=f"Нет доступного окна доставки (текущее время {self.model.get_time_str()})",
            status="unavailable"
        )
        return False
        
    def check_inventory(self):
        """Проверка текущих запасов"""
        for product, required in self.product_requirements.items():
            current = self.inventory.get(product, 0)
            if current < required:
                self.model.log_event(
                    event_type="low_stock",
                    agent_id=f"store_{self.unique_id}",
                    location=self.pos,
                    details=f"Низкий запас {product}: {current}/{required}",
                    status="need_restock"
                )
    
    def receive_delivery(self, products):
        """Прием доставки"""
        print(f"\nПрием доставки в {self.name}")
        print(f"Текущие запасы: {self.inventory}")
        print(f"Получено: {products}")
        
        for product, amount in products.items():
            self.inventory[product] = self.inventory.get(product, 0) + amount
        
        print(f"Новые запасы: {self.inventory}")
        def step(self):
            self.check_inventory()

class VehicleAgent(Agent):
    def __init__(self, unique_id, model, capacity):
        super().__init__(unique_id, model)
        self.capacity = capacity        # Общая вместимость
        self.current_load = {}         # Текущий груз
        self.destination = None        # Пункт назначения
        self.status = "idle"           # Статус машины (idle, en_route, returning)
        self.pos = None                # Текущая позиция
        
    def get_current_load_weight(self):
        """Получить общий вес текущего груза"""
        return sum(self.current_load.values())

    def can_add_load(self, products: dict) -> bool:
        """Проверка, можно ли добавить груз"""
        new_total_weight = self.get_current_load_weight() + sum(products.values())
        return new_total_weight <= self.capacity

    def optimize_load(self, requested_products: dict) -> dict:
        """Оптимизация загрузки с учетом вместимости"""
        available_capacity = self.capacity - self.get_current_load_weight()
        
        if available_capacity <= 0:
            return {}

        # Если все продукты помещаются
        if sum(requested_products.values()) <= available_capacity:
            return requested_products.copy()

        # Если не все помещаются, берем пропорционально
        optimized_load = {}
        total_requested = sum(requested_products.values())
        for product, amount in requested_products.items():
            # Вычисляем пропорциональное количество
            optimized_amount = int((amount / total_requested) * available_capacity)
            if optimized_amount > 0:
                optimized_load[product] = optimized_amount

        return optimized_load
        
    def load_delivery(self, products, destination_store):
        """Загрузка товаров для доставки"""
        print(f"Загрузка машины {self.unique_id} для {destination_store.name}")
        self.current_load = products
        self.destination = destination_store
        self.status = "en_route"
        
        self.model.log_event(
            event_type="vehicle_dispatch",
            agent_id=f"{destination_store.name}",
            location=self.pos,
            details=f"Машина {self.unique_id} загружена: {products}",
            status="en_route"
        )

    def step(self):
        """Один шаг симуляции для транспортного средства"""
        print(f"Шаг машины {self.unique_id}, статус: {self.status}")
        if self.status == "en_route":
            # Симулируем движение к месту назначения
            if random.random() < 0.3:  # 30% шанс завершить доставку на каждом шаге
                print(f"Пытаемся завершить доставку для {self.destination.name}")
                self.complete_delivery()
        elif self.status == "returning":
            # Симулируем возврат на склад
            if random.random() < 0.5:  # 50% шанс вернуться на склад на каждом шаге
                print(f"Машина {self.unique_id} вернулась на склад")
                self.status = "idle"
                self.model.log_event(
                    event_type="vehicle_return",
                    agent_id=f"vehicle_{self.unique_id}",
                    location=(0, 0),  # Позиция склада
                    details="Возврат на склад",
                    status="idle"
                )
    
    def complete_delivery(self):
        """Завершение доставки с учетом временных окон"""
        if self.destination and self.current_load:
            print(f"\nПопытка доставки в {self.destination.name}")
            print(f"Текущее время: {self.model.get_time_str()}")
            print(f"Груз: {self.current_load}")
            
            # Проверяем, может ли магазин принять доставку
            can_accept = self.destination.can_accept_delivery()
            print(f"Магазин может принять доставку: {can_accept}")
            
            if can_accept:
                # Выполняем доставку
                print("Выполняем доставку...")
                self.destination.receive_delivery(self.current_load)
                self.model.log_event(
                    event_type="delivery_complete",
                    agent_id=f"{self.destination.name}",
                    location=self.destination.pos,
                    details=f"Доставлено машиной #{self.unique_id}: {self.current_load}",
                    status="completed"
                )
                self.current_load = {}
                self.destination = None
                self.status = "returning"
                print("Доставка завершена")
            else:
                # Если магазин не может принять доставку, ждем
                print("Ожидаем доступное окно доставки")
                self.model.log_event(
                    event_type="delivery_waiting",
                    agent_id=f"{self.destination.name}",
                    location=self.destination.pos,
                    details=f"Машина #{self.unique_id} ожидает доступного окна доставки",
                    status="waiting"
                )
                return False
        return True
        