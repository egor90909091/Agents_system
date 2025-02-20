import networkx as nx
from datetime import datetime, timedelta
import random
import csv


class DeliveryScheduler:
    def __init__(self, model):
        self.model = model
        self.schedule = []
        self.route_graph = nx.Graph()
        self._agents = {}
        self._build_graph()
        self._add_all_agents()

    def _build_graph(self):
        """Создание графа маршрутов с использованием матрицы расстояний"""
        # Добавляем склад
        self.route_graph.add_node("склад")

        # Добавляем магазины
        for store in self.model.stores:
            self.route_graph.add_node(
                store.name, delivery_windows=store.delivery_windows
            )

        # Добавляем рёбра с реальными расстояниями из матрицы
        distances = self.model.data["distances"]
        for from_node, to_nodes in distances.items():
            for to_node, distance in to_nodes.items():
                self.route_graph.add_edge(from_node, to_node, weight=distance)

    def _add_all_agents(self):
        """Добавление всех агентов в планировщик"""
        # Добавляем склад
        self.add(self.model.warehouse)

        # Добавляем магазины
        for store in self.model.stores:
            self.add(store)

        # Добавляем транспорт
        for vehicle in self.model.vehicles:
            self.add(vehicle)

    def add(self, agent):
        """Добавление агента в планировщик"""
        self._agents[agent.unique_id] = agent

    def step(self):
        """Выполняем один шаг для всех агентов в случайном порядке."""
        agent_keys = list(self._agents.keys())
        random.shuffle(agent_keys)
        for agent_key in agent_keys:
            self._agents[agent_key].step()

    def generate_schedule(self):
        """Генерация расписания доставок"""
        current_time = datetime.strptime("09:00", "%H:%M")

        # Для каждого магазина
        for store in self.model.stores:
            # Находим кратчайший путь от склада до магазина
            path = nx.shortest_path(
                self.route_graph, "склад", store.name, weight="weight"
            )
            distance = nx.shortest_path_length(
                self.route_graph, "склад", store.name, weight="weight"
            )

            # Оцениваем общий вес груза
            total_weight = sum(store.product_requirements.values())

            # Оцениваем время доставки (15 минут на единицу расстояния)
            delivery_time = timedelta(minutes=15 * distance)

            # Находим подходящее окно доставки
            for window_start, window_end in store.delivery_windows:
                window_start_time = datetime.strptime(f"{window_start}:00", "%H:%M")
                window_end_time = datetime.strptime(f"{window_end}:00", "%H:%M")

                if current_time + delivery_time <= window_end_time:
                    # Добавляем доставку в расписание
                    delivery_slot = {
                        "store_id": store.name,
                        "departure_time": current_time.strftime("%H:%M"),
                        "arrival_time": (current_time + delivery_time).strftime(
                            "%H:%M"
                        ),
                        "products": store.product_requirements,
                        "distance": distance,
                        "route": " -> ".join(path),
                    }
                    self.schedule.append(delivery_slot)

                    # Обновляем текущее время
                    current_time += delivery_time + timedelta(
                        minutes=30
                    )  # 30 минут на разгрузку
                    break

    def save_schedule(self, filename: str):
        """Метод теперь только выводит информацию в консоль"""
        print("\nРАСПИСАНИЕ ДОСТАВОК")
        print("=" * 50 + "\n")

        for slot in self.schedule:
            print(f"Магазин: {slot['store_id']}")
            print(f"Время выезда: {slot['departure_time']}")
            print(f"Время прибытия: {slot['arrival_time']}")
            print("Товары для доставки:")
            for product, amount in eval(str(slot["products"])).items():
                print(f"  - {product}: {amount} шт.")
            print(f"Маршрут: {slot['route']}")
            print(f"Расстояние: {slot['distance']} км")
            print(f"Стоимость доставки: {slot['cost']} руб.")
            print("-" * 30 + "\n")

        # Общая статистика
        total_cost = sum(slot["cost"] for slot in self.schedule)
        total_distance = sum(slot["distance"] for slot in self.schedule)
        print("\nОБЩАЯ СТАТИСТИКА")
        print("=" * 50)
        print(f"Общая стоимость доставок: {total_cost} руб.")
        print(f"Количество рейсов: {len(self.schedule)}")
        print(f"Общее расстояние: {total_distance} км")
