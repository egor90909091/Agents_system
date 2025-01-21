# delivery_system/scheduler.py
from datetime import datetime, timedelta
import csv
import networkx as nx

class DeliveryScheduler:
    def __init__(self, model):
        self.model = model
        self.schedule = []
        self.route_graph = nx.Graph()
        self._build_graph()
        
    def _build_graph(self):
        """Создание графа маршрутов с использованием матрицы расстояний"""
        # Добавляем склад
        self.route_graph.add_node("warehouse", pos=self.model.warehouse.pos)
        
        # Добавляем магазины
        for store in self.model.stores:
            self.route_graph.add_node(f"store_{store.unique_id}", 
                                    pos=store.pos,
                                    windows=store.delivery_windows)
        
        # Добавляем рёбра с реальными расстояниями из матрицы
        distances = self.model.data['distances']
        for from_node, to_nodes in distances.items():
            for to_node, distance in to_nodes.items():
                # Преобразуем имена узлов в формат графа
                from_id = from_node if from_node == 'warehouse' else f"store_{from_node.split('_')[1]}"
                to_id = to_node if to_node == 'warehouse' else f"store_{to_node.split('_')[1]}"
                
                self.route_graph.add_edge(from_id, to_id, weight=distance)
    
    def calculate_delivery_cost(self, distance: float) -> float:
        """Расчет стоимости доставки на основе расстояния"""
        # Простая формула расчета стоимости: базовая ставка + стоимость за км
        base_cost = 100  # Базовая стоимость доставки
        per_km_cost = 10  # Стоимость за километр
        return base_cost + (distance * per_km_cost)
    
    def generate_schedule(self):
        """Генерация расписания доставок"""
        current_time = datetime.strptime("09:00", "%H:%M")
        total_cost = 0
        
        # Для каждого магазина
        for store in self.model.stores:
            store_node = f"store_{store.unique_id}"
            
            # Находим кратчайший путь от склада до магазина
            path = nx.shortest_path(self.route_graph, "warehouse", store_node, 
                                  weight="weight")
            distance = nx.shortest_path_length(self.route_graph, "warehouse", 
                                             store_node, weight="weight")
            
            # Рассчитываем стоимость доставки
            delivery_cost = self.calculate_delivery_cost(distance)
            total_cost += delivery_cost
            
            # Оцениваем время доставки (предполагаем 15 минут на единицу расстояния)
            delivery_time = timedelta(minutes=15 * distance)
            
            # Находим подходящее окно доставки
            for window_start, window_end in store.delivery_windows:
                window_start_time = datetime.strptime(f"{window_start}:00", "%H:%M")
                window_end_time = datetime.strptime(f"{window_end}:00", "%H:%M")
                
                if current_time + delivery_time <= window_end_time:
                    # Добавляем доставку в расписание
                    delivery_slot = {
                        'store_id': store.unique_id,
                        'departure_time': current_time.strftime("%H:%M"),
                        'arrival_time': (current_time + delivery_time).strftime("%H:%M"),
                        'products': store.product_requirements,
                        'distance': distance,
                        'cost': delivery_cost,
                        'route': " -> ".join(path)
                    }
                    self.schedule.append(delivery_slot)
                    
                    # Обновляем текущее время
                    current_time += delivery_time + timedelta(minutes=30)  # 30 минут на разгрузку
                    break
        
        return total_cost
    
    def save_schedule(self, filename: str):
        """Сохранение расписания в файл"""
        total_cost = sum(slot['cost'] for slot in self.schedule)
        
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
                f.write(f"Магазин #{slot['store_id']}\n")
                f.write(f"Время выезда: {slot['departure_time']}\n")
                f.write(f"Время прибытия: {slot['arrival_time']}\n")
                f.write("Товары для доставки:\n")
                for product, amount in eval(str(slot['products'])).items():
                    f.write(f"  - {product}: {amount} шт.\n")
                f.write(f"Маршрут: {slot['route']}\n")
                f.write(f"Расстояние: {slot['distance']} км\n")
                f.write(f"Стоимость доставки: {slot['cost']} руб.\n")
                f.write("-" * 30 + "\n\n")
                
            f.write("\nОБЩАЯ СТАТИСТИКА\n")
            f.write("=" * 50 + "\n")
            f.write(f"Общая стоимость доставок: {total_cost} руб.\n")
            f.write(f"Количество рейсов: {len(self.schedule)}\n")
            total_distance = sum(slot['distance'] for slot in self.schedule)
            f.write(f"Общее расстояние: {total_distance} км\n")