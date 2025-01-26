# delivery_system/agents.py
from mesa import Agent
from datetime import datetime, time, timedelta
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
        """Поиск подходящего магазина для доставки"""
        available_stores = []
        current_time = self.model.current_time

        for store_name, needed_products in self.pending_stores.items():
            store = next(s for s in self.model.stores if s.name == store_name)
            
            # Проверяем есть ли уже машина в пути к этому магазину
            if store.awaiting_vehicle:
                continue

            # Получаем расстояние до магазина
            distance = self.model.data['distances']['склад'][store.name]
            arrival_time = self.calculate_arrival_time(store, distance)
            
            # Проверяем, будет ли магазин доступен при прибытии
            if self.will_store_be_available(store, arrival_time):
                total_need = sum(needed_products.values())
                available_stores.append((store, total_need, distance, arrival_time))

        if available_stores:
            # Сортируем по приоритету (сначала по количеству needed_products, потом по расстоянию)
            available_stores.sort(key=lambda x: (-x[1], x[2]))
            chosen_store = available_stores[0]
            print(f"\n[Склад] Выбран магазин {chosen_store[0].name}")
            print(f"-> Расстояние: {chosen_store[2]} км")
            print(f"-> Время прибытия: {chosen_store[3].strftime('%H:%M')}")
            return chosen_store[0]
            
        return None

    def calculate_arrival_time(self, store, distance):
        """Расчет времени прибытия в магазин"""
        travel_minutes = distance * 3  # 3 минуты на километр
        arrival_time = self.model.current_time + timedelta(minutes=travel_minutes)
        return arrival_time

    def will_store_be_available(self, store, arrival_time):
        """Проверка, будет ли магазин доступен во время прибытия"""
        arrival_hour = arrival_time.hour
        
        for start_hour, end_hour in store.delivery_windows:
            # Если прибываем во время окна доставки
            if start_hour <= arrival_hour < end_hour:
                return True
            # Если прибываем менее чем за 15 минут до открытия окна
            elif arrival_hour == start_hour - 1 and arrival_time.minute >= 45:
                return True
        return False

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

        # Считаем, сколько уже едет в этот магазин
        in_delivery = self.active_orders.get(store.name, {})
        if in_delivery:
            print(f"-> Уже в пути: {in_delivery}")

        # Вычисляем, сколько еще нужно довезти
        remaining_needs = {}
        for product, needed_total in needed_products.items():
            already_in_delivery = in_delivery.get(product, 0)
            max_can_deliver = store.product_requirements[product]
            still_needed = min(needed_total, max_can_deliver) - already_in_delivery
            
            if still_needed > 0:
                remaining_needs[product] = still_needed

        if not remaining_needs:
            print("-> Нужное количество товаров уже в пути")
            return None

        # Получаем расстояние до магазина
        distance = self.model.data['distances']['склад'][store.name]
        arrival_time = self.calculate_arrival_time(store, distance)

        # Проверяем, будет ли магазин доступен при прибытии
        if not self.will_store_be_available(store, arrival_time):
            print(f"-> Магазин будет закрыт при прибытии ({arrival_time.strftime('%H:%M')})")
            print(f"-> Заказ будет обработан позже")
            if store.name not in self.pending_stores:
                self.pending_stores[store.name] = {}
            for product, amount in remaining_needs.items():
                current = self.pending_stores[store.name].get(product, 0)
                self.pending_stores[store.name][product] = current + amount
            return False

        # Распределяем заказ между свободными машинами
        deliveries_made = False
        for vehicle in self.model.vehicles:
            if vehicle.status == "idle":
                available_products = {}
                total_weight = 0
                current_needs = remaining_needs.copy()  # Копируем оставшиеся потребности

                # Проверяем каждый продукт
                for product, needed in list(current_needs.items()):
                    if total_weight >= vehicle.capacity:
                        break

                    stock_available = self.inventory.get(product, 0)
                    if stock_available <= 0:
                        continue

                    # Определяем, сколько можем загрузить
                    space_left = vehicle.capacity - total_weight
                    can_take = min(needed, stock_available, space_left)

                    if can_take > 0:
                        available_products[product] = can_take
                        total_weight += can_take
                        self.inventory[product] -= can_take
                        
                        # Обновляем оставшиеся потребности
                        remaining_needs[product] -= can_take
                        if remaining_needs[product] <= 0:
                            del remaining_needs[product]

                # Если есть что везти - отправляем машину
                if available_products:
                    if vehicle.load_delivery(available_products, store):
                        deliveries_made = True
                        print(f"-> Машина {vehicle.unique_id} загружена: {available_products}")
                        
                        # Обновляем активные заказы
                        if store.name not in self.active_orders:
                            self.active_orders[store.name] = {}
                        for product, amount in available_products.items():
                            current = self.active_orders[store.name].get(product, 0)
                            self.active_orders[store.name][product] = current + amount

        if deliveries_made:
            # Если остались невыполненные потребности - сохраняем их
            if remaining_needs:
                print(f"-> Осталось доставить: {remaining_needs}")
                if store.name not in self.pending_stores:
                    self.pending_stores[store.name] = {}
                for product, amount in remaining_needs.items():
                    current = self.pending_stores[store.name].get(product, 0)
                    self.pending_stores[store.name][product] = current + amount
            return True
        else:
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
        self.expected_deliveries = {}
        self.awaiting_vehicle = None

    def step(self):
        """Один шаг симуляции для магазина"""
        # Сначала расходуем товары
        self.consume_products()
        
        # Затем проверяем запасы и формируем заказ если нужно
        print(f"\n[{self.name}] Запасы: {self.inventory}")
        needed_products = self.check_inventory_and_make_order()
        
        if needed_products:
            print(f"-> Требуется пополнить: {', '.join(f'{p}:{q}' for p, q in needed_products.items())}")
            # Пытаемся сделать заказ
            self.model.warehouse.process_order(self, needed_products)
            self.model.log_event(
                "store_needs",
                self.name,
                "Требуется доставка",
                f"Требуется доставка: {needed_products}",
                "pending"
            )

    def check_inventory_and_make_order(self):
        """Проверка запасов и формирование заказа"""
        # Получаем актуальную информацию об активных заказах
        active_orders = {}
        if hasattr(self.model, 'warehouse'):
            active_orders = self.model.warehouse.active_orders.get(self.name, {})
        
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
        
        return needed_products if needed_products else None

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
        
        # Если все доставлено, очищаем информацию об ожидании
        if not self.expected_deliveries:
            self.awaiting_vehicle = None
            
        print(f"Новые запасы: {self.inventory}")
        return True















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

        # Получаем расстояние из матрицы расстояний
        distance = self.model.data['distances']['склад'][destination_store.name]
        
        self.current_load = products
        self.destination = destination_store
        self.status = "en_route"
        self.start_time = self.model.current_time
        
        # Рассчитываем время прибытия (3 минуты на километр)
        travel_minutes = distance * 3
        self.arrival_time = self.start_time + timedelta(minutes=travel_minutes)
        
        print(f"-> Загружено и отправлено: {products}")
        print(f"-> Расстояние: {distance} км")
        print(f"-> Расчетное время в пути: {travel_minutes} минут")
        print(f"-> Время выезда: {self.start_time.strftime('%H:%M')}")
        print(f"-> Ожидаемое прибытие: {self.arrival_time.strftime('%H:%M')}")
        
        # Уведомляем магазин о предстоящей доставке
        destination_store.add_expected_delivery(products, self.unique_id)
        return True

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
        current_time = self.model.current_time
        
        if self.status == "en_route":
            # Проверяем, прибыли ли мы по времени
            if self.arrival_time and current_time >= self.arrival_time:
                print(f"\n[Машина {self.unique_id}] Прибыла к {self.destination.name}")
                
                # Пытаемся разгрузиться
                if self.destination.receive_delivery(self.current_load):
                    print(f"-> Доставка выполнена: {self.current_load}")
                    
                    # Получаем расстояние до склада из матрицы расстояний
                    return_distance = self.model.data['distances'][self.destination.name]['склад']
                    return_minutes = return_distance * 3  # 3 минуты на километр
                    
                    self.current_load = {}
                    self.status = "returning"
                    self.start_time = current_time
                    self.arrival_time = current_time + timedelta(minutes=return_minutes)
                    
                    print(f"-> Возвращается на склад")
                    print(f"-> Расстояние до склада: {return_distance} км")
                    print(f"-> Расчетное время возвращения: {self.arrival_time.strftime('%H:%M')}")
                else:
                    print(f"-> Доставка отклонена")
            else:
                # Находимся в процессе движения
                remaining_minutes = int((self.arrival_time - current_time).total_seconds() / 60)
                total_trip_minutes = int((self.arrival_time - self.start_time).total_seconds() / 60)
                progress = int(((total_trip_minutes - remaining_minutes) / total_trip_minutes) * 100)
                
                print(f"\n[Машина {self.unique_id}] В пути к {self.destination.name}")
                print(f"-> Груз: {self.current_load}")
                print(f"-> Прогресс: {progress}%")
                print(f"-> Осталось: {remaining_minutes} минут")
                print(f"-> Прибытие в {self.arrival_time.strftime('%H:%M')}")
        
        elif self.status == "returning":
            if current_time >= self.arrival_time:
                print(f"\n[Машина {self.unique_id}] Вернулась на склад")
                self.status = "idle"
                self.destination = None
                self.start_time = None
                self.arrival_time = None
            else:
                remaining_minutes = int((self.arrival_time - current_time).total_seconds() / 60)
                print(f"\n[Машина {self.unique_id}] Возвращается на склад")
                print(f"-> Прибытие через {remaining_minutes} минут")
        
        elif self.status == "idle":
            if random.random() < 0.1:
                print(f"\n[Машина {self.unique_id}] Готова к новым заказам")



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
    