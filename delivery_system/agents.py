# delivery_system/agents.py
from mesa import Agent
from datetime import datetime, time
import random

class WarehouseAgent(Agent):
    def __init__(self, unique_id, model, inventory):
        super().__init__(unique_id, model)
        self.inventory = inventory.copy()
        self.active_orders = {}  # {store_name: {product: amount}}
        self.pending_stores = {}  # {store_name: needed_products}

    def update_active_orders(self, store, products, add=True):
        """Обновление активных заказов"""
        if add:
            # Добавляем новый заказ
            if store.name not in self.active_orders:
                self.active_orders[store.name] = {}
            for product, amount in products.items():
                current = self.active_orders[store.name].get(product, 0)
                self.active_orders[store.name][product] = current + amount
        else:
            # Удаляем выполненный заказ
            if store.name in self.active_orders:
                for product in products:
                    if product in self.active_orders[store.name]:
                        del self.active_orders[store.name][product]
                if not self.active_orders[store.name]:
                    del self.active_orders[store.name]

    def find_best_store_for_delivery(self):
        """Поиск магазина, который может принять доставку"""
        available_stores = []
        for store_name, needed_products in self.pending_stores.items():
            store = next(s for s in self.model.stores if s.name == store_name)
            if store.can_accept_delivery():
                total_need = sum(needed_products.values())
                available_stores.append((store, total_need))

        if available_stores:
            available_stores.sort(key=lambda x: x[1], reverse=True)
            return available_stores[0][0]
        return None

    def get_remaining_needs(self, store, needed_products):
        """Получить реальные потребности с учетом активных заказов"""
        remaining_needs = needed_products.copy()
        total_ordered = {}

        if store.name in self.active_orders:
            for product, amount in self.active_orders[store.name].items():
                total_ordered[product] = total_ordered.get(product, 0) + amount

        for product, needed in needed_products.items():
            already_ordered = total_ordered.get(product, 0)
            remaining = max(0, needed - already_ordered)
            if remaining == 0:
                del remaining_needs[product]
            else:
                remaining_needs[product] = remaining

        return remaining_needs

    def process_order(self, store, needed_products):
        """Обработка заказа от магазина"""
        print(f"\n[Склад] Заказ от {store.name}: {needed_products}")
        
        # Проверяем, есть ли уже машина в пути к этому магазину
        if store.awaiting_vehicle is not None:
            print(f"-> Ожидается машина {store.awaiting_vehicle}: {store.expected_deliveries}")
            return None

        # Считаем, сколько уже едет в этот магазин
        in_delivery = {}
        if store.name in self.active_orders:
            in_delivery = self.active_orders[store.name]
            print(f"-> Уже в пути: {in_delivery}")

        # Вычисляем, сколько еще нужно довезти с учетом уже отправленного
        remaining_needs = {}
        for product, needed_total in needed_products.items():
            already_in_delivery = in_delivery.get(product, 0)
            max_can_deliver = store.product_requirements[product]
            still_needed = min(needed_total, max_can_deliver) - already_in_delivery
            
            if still_needed > 0:
                remaining_needs[product] = still_needed
                print(f"-> {product}: требуется {needed_total}, в пути {already_in_delivery}")

        if not remaining_needs:
            print("-> Нужное количество товаров уже в пути")
            return None

        if not store.can_accept_delivery():
            print(f"-> {store.name} сейчас не может принять доставку")
            return False

        # Ищем свободную машину
        for vehicle in self.model.vehicles:
            if vehicle.status == "idle":
                available_products = {}
                total_weight = 0
                current_remaining = remaining_needs.copy()

                # Сортируем продукты по количеству
                sorted_needs = sorted(remaining_needs.items(), 
                                    key=lambda x: x[1], reverse=True)

                for product, needed in sorted_needs:
                    if total_weight >= vehicle.capacity:
                        break

                    stock_available = self.inventory.get(product, 0)
                    if stock_available <= 0:
                        continue

                    # Считаем сколько можем взять
                    space_left = vehicle.capacity - total_weight
                    can_take = min(needed, stock_available, space_left)

                    if can_take > 0:
                        available_products[product] = can_take
                        total_weight += can_take
                        self.inventory[product] -= can_take
                        current_remaining[product] -= can_take
                        if current_remaining[product] <= 0:
                            del current_remaining[product]

                if available_products:
                    print(f"-> Загружаем в машину {vehicle.unique_id}: {available_products}")
                    
                    # Проверяем, не превысим ли максимальную вместимость магазина
                    can_deliver = True
                    proposed_deliveries = {}
                    
                    for product, amount in available_products.items():
                        current_in_delivery = self.active_orders.get(store.name, {}).get(product, 0)
                        total_would_be = current_in_delivery + amount
                        
                        if total_would_be > store.product_requirements[product]:
                            print(f"-> Нельзя отправить {product}: превышение вместимости")
                            print(f"   В пути: {current_in_delivery}")
                            print(f"   Пытаемся добавить: {amount}")
                            print(f"   Максимум: {store.product_requirements[product]}")
                            can_deliver = False
                            break
                        proposed_deliveries[product] = amount
                    
                    if can_deliver and vehicle.load_delivery(proposed_deliveries, store):
                        # Обновляем активные заказы
                        if store.name not in self.active_orders:
                            self.active_orders[store.name] = {}
                        for product, amount in proposed_deliveries.items():
                            current = self.active_orders[store.name].get(product, 0)
                            self.active_orders[store.name][product] = current + amount

                        if current_remaining:
                            print(f"-> Осталось доставить: {current_remaining}")
                        
                        print(f"-> Активные заказы для {store.name}: {self.active_orders.get(store.name, {})}")
                        return True

        print("-> Нет свободных машин")
        return False

    def complete_delivery(self, store, products):
        """Завершение доставки"""
        print(f"\nЗавершение доставки для {store.name}")
        print(f"Доставлено: {products}")
        
        # Удаляем из активных заказов
        self.update_active_orders(store, products, add=False)
        
        # Удаляем из ожидающих если все доставлено
        if store.name in self.pending_stores:
            remaining = self.pending_stores[store.name].copy()
            for product, amount in products.items():
                if product in remaining:
                    remaining[product] = max(0, remaining[product] - amount)
                    if remaining[product] == 0:
                        del remaining[product]
            
            if remaining:
                self.pending_stores[store.name] = remaining
            else:
                del self.pending_stores[store.name]














class StoreAgent(Agent):
    def __init__(self, unique_id, model, delivery_windows, product_requirements):
        super().__init__(unique_id, model)
        self.name = None
        self.delivery_windows = delivery_windows
        self.product_requirements = product_requirements
        self.inventory = {product: 0 for product in product_requirements}
        self.expected_deliveries = {}  # Добавляем отслеживание ожидаемых поставок
        self.awaiting_vehicle = None   # Добавляем отслеживание машины

    def add_expected_delivery(self, products, vehicle_id):
        """Добавление информации об ожидаемой поставке"""
        self.expected_deliveries.update(products)
        self.awaiting_vehicle = vehicle_id
        self.model.log_event(
            "delivery_waiting",
            self.name,
            f"Ожидание поставки",
            f"Ожидается машина {vehicle_id} с товарами: {products}",
            "waiting"
        )

    def receive_delivery(self, products):
        """Прием доставки"""
        print(f"\nПрием доставки в {self.name}")
        
        # Получаем warehouse для обновления активных заказов
        warehouse = next(agent for agent in self.model.schedule.agents 
                        if isinstance(agent, WarehouseAgent))
        
        # Проверяем, не превысим ли максимальные уровни
        proposed_inventory = self.inventory.copy()
        for product, amount in products.items():
            proposed_inventory[product] = proposed_inventory.get(product, 0) + amount
            
            if proposed_inventory[product] > self.product_requirements[product]:
                print(f"Отказ в приеме доставки: превышение требуемого количества {product}")
                print(f"Текущий запас: {self.inventory[product]}")
                print(f"Пытаемся добавить: {amount}")
                print(f"Максимальный уровень: {self.product_requirements[product]}")
                return False

        # Если все проверки пройдены - принимаем доставку
        print(f"Текущие запасы: {self.inventory}")
        print(f"Получено: {products}")
        
        for product, amount in products.items():
            self.inventory[product] = proposed_inventory[product]
            # Уменьшаем ожидаемые поставки
            if product in self.expected_deliveries:
                self.expected_deliveries[product] = max(0, 
                    self.expected_deliveries[product] - amount)
                if self.expected_deliveries[product] == 0:
                    del self.expected_deliveries[product]
                    
            # Уменьшаем активные заказы
            if self.name in warehouse.active_orders and product in warehouse.active_orders[self.name]:
                warehouse.active_orders[self.name][product] = max(0, 
                    warehouse.active_orders[self.name][product] - amount)
                if warehouse.active_orders[self.name][product] == 0:
                    del warehouse.active_orders[self.name][product]
                    
        # Если все активные заказы выполнены, удаляем запись о магазине
        if self.name in warehouse.active_orders and not warehouse.active_orders[self.name]:
            del warehouse.active_orders[self.name]
        
        # Если все доставлено, очищаем информацию об ожидании
        if not self.expected_deliveries:
            self.awaiting_vehicle = None
            
        print(f"Новые запасы: {self.inventory}")
        print(f"Обновленные активные заказы: {warehouse.active_orders}")
        return True

    def can_accept_delivery(self) -> bool:
        """Проверка возможности приема доставки"""
        # Проверяем временное окно
        current_hour = self.model.current_time.hour
        for start_hour, end_hour in self.delivery_windows:
            if start_hour <= current_hour < end_hour:
                print(f"{self.name} может принять доставку (окно {start_hour}:00-{end_hour}:00)")
                return True
        
        print(f"{self.name} не может принять доставку - нет подходящего окна")
        return False

    def consume_products(self):
        """Расход товаров"""
        consumption_happened = False
        used_products = []
        
        for product in list(self.inventory.keys()):
            current_amount = self.inventory[product]
            if current_amount > 0:  # Расход только если есть что расходовать
                if random.random() < 0.5:  # 50% шанс расхода товара
                    # Расходуем 20% от текущего количества, но минимум 1 единицу
                    consumption = max(1, int(current_amount * 0.2))
                    if consumption > current_amount:
                        consumption = current_amount  # Не позволяем уйти в минус
                        
                    self.inventory[product] = current_amount - consumption
                    used_products.append(f"{product}: -{consumption} (было: {current_amount}, стало: {self.inventory[product]})")
                    consumption_happened = True
                    
                    self.model.log_event(
                        "product_consumption",
                        self.name,
                        "Расход товаров",
                        f"Расход {product}: {consumption} (осталось: {self.inventory[product]})",
                        "consumed"
                    )
        
        # Выводим информацию только если был расход
        if consumption_happened:
            print(f"\nРасход товаров в {self.name}")
            for msg in used_products:
                print(msg)
            print(f"Запасы после расхода: {self.inventory}")

    def check_inventory_and_make_order(self):
        """Проверка запасов и формирование заказа"""
        # Получаем warehouse для проверки активных заказов
        warehouse = next(agent for agent in self.model.schedule.agents 
                        if isinstance(agent, WarehouseAgent))
        
        active_orders = warehouse.active_orders.get(self.name, {})
        
        print(f"\n[{self.name}] Запасы: {self.inventory}")
        
        # Проверяем активные заказы
        if active_orders:
            print(f"-> В обработке: {active_orders}")
            return None
            
        # Проверяем ожидание машины
        if self.awaiting_vehicle:
            print(f"-> Ожидается машина {self.awaiting_vehicle}: {self.expected_deliveries}")
            return None

        needed_products = {}
        
        # Проверяем каждый продукт
        for product, required in self.product_requirements.items():
            current = self.inventory.get(product, 0)
            expected = self.expected_deliveries.get(product, 0)
            in_active_orders = active_orders.get(product, 0)
            total_available = current + expected + in_active_orders
            
            # Если общее количество меньше требуемого
            if total_available < required:
                needed_amount = required - total_available
                needed_products[product] = needed_amount
        
        # Формируем заказ если что-то требуется
        if needed_products:
            print(f"-> Требуется пополнить: {', '.join(f'{p}:{q}' for p, q in needed_products.items())}")
            return needed_products
            
        print("-> Все запасы в норме")
        return None


    def step(self):
        """Один шаг симуляции для магазина"""
        # Сначала расходуем товары
        self.consume_products()
        
        # Затем проверяем запасы и формируем заказ если нужно
        needed_products = self.check_inventory_and_make_order()
        
        if needed_products:
            self.model.log_event(
                "store_needs",
                self.name,
                "Требуется доставка",
                f"Требуется доставка: {needed_products}",
                "pending"
            )
















class VehicleAgent(Agent):
    def __init__(self, unique_id, model, capacity):
        super().__init__(unique_id, model)
        self.capacity = capacity        # Общая вместимость
        self.current_load = {}         # Текущий груз
        self.destination = None        # Пункт назначения
        self.status = "idle"
        self.pos = None

    def get_current_load_weight(self):
        """Получить текущий вес груза"""
        return sum(self.current_load.values())

    
    def load_delivery(self, products, destination_store):
        """Загрузка товаров для доставки"""
        print(f"[Машина {self.unique_id}] Загрузка для {destination_store.name}")
        print(f"-> Заказано: {products}")
        print(f"-> Доступная вместимость: {self.capacity - self.get_current_load_weight()}")

        self.destination = destination_store
        optimized_load = self.optimize_load(products)

        if optimized_load:
            self.current_load = optimized_load
            self.status = "en_route"
            
            # Уведомляем магазин о предстоящей доставке
            destination_store.add_expected_delivery(optimized_load, self.unique_id)
            print(f"-> Загружено и отправлено: {optimized_load}")
            
            return True
        return False

    def optimize_load(self, requested_products):
        """Оптимизация загрузки с учетом вместимости"""
        if self.capacity <= 0:
            return {}

        total_requested = sum(requested_products.values())
        optimized_load = {}
        
        if total_requested <= self.capacity:
            return requested_products.copy()
        else:
            remaining_capacity = self.capacity
            sorted_products = sorted(requested_products.items(), 
                                   key=lambda x: x[1], reverse=True)
            
            for product, amount in sorted_products:
                if remaining_capacity <= 0:
                    break
                    
                can_take = min(amount, remaining_capacity)
                optimized_load[product] = can_take
                remaining_capacity -= can_take

        return optimized_load

    def step(self):
        """Один шаг симуляции для транспортного средства"""
        if self.status == "en_route":
            # Симулируем движение к месту назначения
            if random.random() < 0.3:  # 30% шанс завершить доставку
                if self.destination.can_accept_delivery():
                    print(f"[Машина {self.unique_id}] Прибыла к {self.destination.name}")
                    if self.destination.receive_delivery(self.current_load):
                        print(f"-> Доставка выполнена: {self.current_load}")
                        self.current_load = {}
                        self.destination = None
                        self.status = "returning"
                        print(f"-> Возвращается на склад")
                    else:
                        print(f"-> Доставка отклонена")
                else:
                    print(f"[Машина {self.unique_id}] Ожидает окно доставки у {self.destination.name}")
        
        elif self.status == "returning":
            # Симулируем возврат на склад
            if random.random() < 0.4:  # 40% шанс вернуться
                self.status = "idle"
                print(f"[Машина {self.unique_id}] Вернулась на склад, готова к новым заказам")
        
        elif self.status == "idle":
            if random.random() < 0.1:  # Периодически сообщаем о готовности

                print(f"[Машина {self.unique_id}] Готова к новым заказам")





    def complete_delivery(self):
        """Завершение доставки с учетом временных окон"""
        if self.destination and self.current_load:
            # Проверяем, может ли магазин принять доставку
            if self.destination.can_accept_delivery():
                # Выполняем доставку
                delivered_products = self.current_load.copy()
                self.destination.receive_delivery(self.current_load)
                
                # Обновляем информацию о выполненном заказе на складе
                warehouse = next(agent for agent in self.model.grid.get_cell_list_contents((0, 0))
                            if isinstance(agent, WarehouseAgent))
                warehouse.complete_delivery(self.destination, delivered_products)
                
                self.model.log_event(
                    event_type="delivery_complete",
                    agent_id=f"{self.destination.name}",
                    location=self.destination.pos,
                    details=f"Доставлено машиной #{self.unique_id}: {delivered_products}",
                    status="completed"
                )
                
                self.current_load = {}
                self.destination = None
                self.status = "returning"
                return True
            else:
                # Если магазин не может принять доставку, ждем
                self.model.log_event(
                    event_type="delivery_waiting",
                    agent_id=f"{self.destination.name}",
                    location=self.destination.pos,
                    details=f"Машина #{self.unique_id} ожидает доступного окна доставки",
                    status="waiting"
                )
                return False
        return True
    