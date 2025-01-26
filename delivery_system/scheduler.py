

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
            self.route_graph.add_node(store.name, 
                                    delivery_windows=store.delivery_windows)
        
        # Добавляем рёбра с реальными расстояниями из матрицы
        distances = self.model.data['distances']
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

    def calculate_delivery_cost(self, distance: float, time_window: tuple, 
                              load_weight: float) -> float:
        """Расчет стоимости доставки на основе расстояния"""
        # Базовая стоимость
        base_cost = 100
        
        # Стоимость за километр
        km_cost = distance * 10
        
        # Надбавка за вес груза
        weight_factor = load_weight / 1000  # 1000 кг - базовый вес
        weight_cost = base_cost * weight_factor
        
        # Надбавка за время доставки
        start_hour = time_window[0]
        if start_hour < 10:  # Ранняя доставка
            time_cost = base_cost * 0.2
        elif start_hour > 16:  # Поздняя доставка
            time_cost = base_cost * 0.3
        else:
            time_cost = 0
            
        total_cost = base_cost + km_cost + weight_cost + time_cost
        return round(total_cost, 2)

    def generate_schedule(self):
        """Генерация расписания доставок"""
        current_time = datetime.strptime("09:00", "%H:%M")
        total_cost = 0
        
        # Для каждого магазина
        for store in self.model.stores:
            # Находим кратчайший путь от склада до магазина
            path = nx.shortest_path(self.route_graph, "склад", store.name, 
                                  weight="weight")
            distance = nx.shortest_path_length(self.route_graph, "склад", 
                                             store.name, weight="weight")
            
            # Оцениваем общий вес груза
            total_weight = sum(store.product_requirements.values())
            
            # Оцениваем время доставки (15 минут на единицу расстояния)
            delivery_time = timedelta(minutes=15 * distance)
            
            # Находим подходящее окно доставки
            for window_start, window_end in store.delivery_windows:
                window_start_time = datetime.strptime(f"{window_start}:00", "%H:%M")
                window_end_time = datetime.strptime(f"{window_end}:00", "%H:%M")
                
                if current_time + delivery_time <= window_end_time:
                    # Рассчитываем стоимость
                    cost = self.calculate_delivery_cost(
                        distance, 
                        (window_start, window_end),
                        total_weight
                    )
                    total_cost += cost
                    
                    # Добавляем доставку в расписание
                    delivery_slot = {
                        'store_id': store.name,
                        'departure_time': current_time.strftime("%H:%M"),
                        'arrival_time': (current_time + delivery_time).strftime("%H:%M"),
                        'products': store.product_requirements,
                        'distance': distance,
                        'cost': cost,
                        'route': " -> ".join(path)
                    }
                    self.schedule.append(delivery_slot)
                    
                    # Обновляем текущее время
                    current_time += delivery_time + timedelta(minutes=30)  # 30 минут на разгрузку
                    break
        
        return total_cost

    def save_schedule(self, filename: str):
        """Сохранение расписания в файл"""
        # Сохраняем в CSV
        with open(f"data/{filename}.csv", 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'store_id', 'departure_time', 'arrival_time', 
                'products', 'distance', 'cost', 'route'
            ])
            writer.writeheader()
            writer.writerows(self.schedule)
            
        # Создаем читаемый документ
        with open(f"data/{filename}.txt", 'w', encoding='utf-8') as f:
            f.write("РАСПИСАНИЕ ДОСТАВОК\n")
            f.write("=" * 50 + "\n\n")
            
            for slot in self.schedule:
                f.write(f"Магазин: {slot['store_id']}\n")
                f.write(f"Время выезда: {slot['departure_time']}\n")
                f.write(f"Время прибытия: {slot['arrival_time']}\n")
                f.write("Товары для доставки:\n")
                for product, amount in eval(str(slot['products'])).items():
                    f.write(f"  - {product}: {amount} шт.\n")
                f.write(f"Маршрут: {slot['route']}\n")
                f.write(f"Расстояние: {slot['distance']} км\n")
                f.write(f"Стоимость доставки: {slot['cost']} руб.\n")
                f.write("-" * 30 + "\n\n")
                
            # Общая статистика
            total_cost = sum(slot['cost'] for slot in self.schedule)
            total_distance = sum(slot['distance'] for slot in self.schedule)
            f.write("\nОБЩАЯ СТАТИСТИКА\n")
            f.write("=" * 50 + "\n")
            f.write(f"Общая стоимость доставок: {total_cost} руб.\n")
            f.write(f"Количество рейсов: {len(self.schedule)}\n")
            f.write(f"Общее расстояние: {total_distance} км\n")