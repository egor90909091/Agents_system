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
        print(f"\nОбработка заказа от {store.name}")
        print(f"Запрошено: {needed_products}")
        print(f"Текущие активные заказы: {self.active_orders}")

        # Рассчитываем, сколько уже едет в этот магазин
        in_delivery = {}
        if store.name in self.active_orders:
            in_delivery = self.active_orders[store.name]
            print(f"Уже в пути: {in_delivery}")

        # Вычисляем, сколько еще реально нужно доставить
        remaining_needs = {}
        for product, needed_total in needed_products.items():
            # Вычитаем то, что уже едет
            already_in_delivery = in_delivery.get(product, 0)
            still_needed = needed_total - already_in_delivery
            
            if still_needed > 0:
                remaining_needs[product] = still_needed

        if not remaining_needs:
            print("Нужное количество товаров уже в пути")
            return None

        print(f"Ещё требуется доставить: {remaining_needs}")

        if not store.can_accept_delivery():
            print(f"{store.name} сейчас не может принять доставку")
            return False

        # Ищем свободную машину
        for vehicle in self.model.vehicles:
            if vehicle.status == "idle":
                available_products = {}
                total_weight = 0

                # Сортируем продукты по количеству
                sorted_needs = sorted(remaining_needs.items(), key=lambda x: x[1], reverse=True)

                for product, needed in sorted_needs:
                    if total_weight >= vehicle.capacity:
                        break

                    # Проверяем наличие на складе
                    stock_available = self.inventory.get(product, 0)
                    if stock_available <= 0:
                        continue

                    # Считаем сколько можем взять
                    space_left = vehicle.capacity - total_weight
                    can_take = min(needed, stock_available, space_left)

                    if can_take > 0:
                        available_products[product] = can_take
                        total_weight += can_take

                if available_products:
                    print(f"Загружаем в машину {vehicle.unique_id}: {available_products}")
                    if vehicle.load_delivery(available_products, store):
                        # Обновляем активные заказы
                        if store.name not in self.active_orders:
                            self.active_orders[store.name] = {}
                        for product, amount in available_products.items():
                            current = self.active_orders[store.name].get(product, 0)
                            self.active_orders[store.name][product] = current + amount
                            self.inventory[product] -= amount

                        # Проверяем, остались ли еще незаказанные товары
                        still_needed = {}
                        for product, needed in remaining_needs.items():
                            delivered = available_products.get(product, 0)
                            if needed > delivered:
                                still_needed[product] = needed - delivered

                        print(f"Активные заказы после загрузки: {self.active_orders}")
                        if still_needed:
                            print(f"Ещё требуется доставить: {still_needed}")
                        else:
                            print("Весь заказ распределен по машинам")

                        return True

        print("Нет свободных машин")
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
        self.product_requirements = product_requirements  # Максимальные уровни запасов
        self.inventory = {product: 0 for product in product_requirements}

    def receive_delivery(self, products):
        """Прием доставки"""
        print(f"\nПрием доставки в {self.name}")
        
        # Проверяем, не превысим ли максимальные уровни
        proposed_inventory = self.inventory.copy()
        for product, amount in products.items():
            proposed_inventory[product] = proposed_inventory.get(product, 0) + amount
            
            # Если после доставки будет больше требуемого - отказываемся
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
            
        print(f"Новые запасы: {self.inventory}")
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
        needed_products = {}
        print(f"\nПроверка запасов в {self.name}")
        print(f"Требуемые уровни: {self.product_requirements}")
        print(f"Текущие запасы: {self.inventory}")
        
        for product, required in self.product_requirements.items():
            current = self.inventory.get(product, 0)
            if current < required:
                needed_amount = required - current
                needed_products[product] = needed_amount
                print(f"Не хватает {product}: {needed_amount}")
        
        if needed_products:
            print(f"Формируем заказ: {needed_products}")
            return needed_products
            
        print("Все запасы в норме")
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
        """Получить общий вес текущего груза"""
        return sum(self.current_load.values())

    def get_available_capacity(self):
        """Получить доступную вместимость"""
        return self.capacity - self.get_current_load_weight()

    def optimize_load(self, requested_products: dict) -> dict:
        """Оптимизация загрузки с учетом вместимости"""
        print(f"\nОптимизация загрузки для машины {self.unique_id}")
        print(f"Запрошено: {requested_products}")
        print(f"Доступная вместимость: {self.get_available_capacity()}")

        available_capacity = self.get_available_capacity()
        if available_capacity <= 0:
            print("Нет доступной вместимости")
            return {}

        optimized_load = {}
        remaining_capacity = available_capacity

        # Сортируем продукты по важности (можно настроить приоритеты)
        for product, amount in requested_products.items():
            # Если есть место хотя бы для части продукта
            if remaining_capacity > 0:
                # Берём максимально возможное количество
                can_take = min(amount, remaining_capacity)
                optimized_load[product] = can_take
                remaining_capacity -= can_take
                print(f"Добавлено {product}: {can_take}, осталось места: {remaining_capacity}")

        print(f"Итоговая загрузка: {optimized_load}")
        return optimized_load

    def load_delivery(self, products, destination_store):
        """Загрузка товаров для доставки"""
        print(f"\nЗагрузка машины {self.unique_id} для {destination_store.name}")
        print(f"Запрошено: {products}")
        print(f"Доступная вместимость: {self.get_available_capacity()}")

        optimized_load = self.optimize_load(products)
        print(f"Оптимизированная загрузка: {optimized_load}")

        if optimized_load:
            self.current_load = optimized_load
            self.destination = destination_store
            self.status = "en_route"

            # Записываем в лог информацию о частичной/полной загрузке
            is_partial = optimized_load != products
            status_text = "частичная загрузка" if is_partial else "полная загрузка"
            
            self.model.log_event(
                event_type="vehicle_dispatch",
                agent_id=f"{destination_store.name}",
                location=self.pos,
                details=(f"Машина {self.unique_id} загружена ({status_text}): {optimized_load}. " +
                        f"Использовано {self.get_current_load_weight()}/{self.capacity}"),
                status="en_route"
            )
            return True
        else:
            print("Загрузка невозможна - нет места")
            return False

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
    def step(self):
        """Один шаг симуляции для транспортного средства"""
        if self.status == "en_route":
            # Симулируем движение к месту назначения
            if random.random() < 0.3:  # 30% шанс завершить доставку на каждом шаге
                self.complete_delivery()
        elif self.status == "returning":
            # Симулируем возврат на склад
            if random.random() < 0.5:  # 50% шанс вернуться на склад на каждом шаге
                self.status = "idle"
                self.model.log_event(
                    event_type="vehicle_return",
                    agent_id=f"vehicle_{self.unique_id}",
                    location=(0, 0),  # Позиция склада
                    details="Возврат на склад",
                    status="idle"
                )