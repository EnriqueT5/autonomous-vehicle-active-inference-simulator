"""
pathfinding.py — Algoritmos de búsqueda de rutas.

Responsabilidades:
- Implementar A* sobre el mapa de creencias (NO sobre el mapa real)
- Calcular rutas considerando costos por tipo de celda
- Recalcular dinámicamente cuando cambian las creencias
- Manejar celdas desconocidas con costo de incertidumbre
"""

import heapq
from typing import List, Tuple, Optional, Dict
from backend.beliefs import BeliefSystem, FREE, BLOCKED, TRAFFIC, SEMAPHORE, ACCIDENT, RAIN, UNKNOWN


def heuristic(a: Tuple[int, int], b: Tuple[int, int]) -> float:
    """
    Heurística Manhattan para A*.
    Estima la distancia mínima entre dos puntos en una cuadrícula.
    """
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def a_star(
    beliefs: BeliefSystem,
    start: Tuple[int, int],
    goal: Tuple[int, int],
    allow_unknown: bool = True
) -> Optional[List[Tuple[int, int]]]:
    """
    Algoritmo A* sobre el mapa de creencias del agente.
    
    IMPORTANTE: Opera sobre las creencias internas μ, NO sobre el mundo real η.
    El agente puede cometer errores si sus creencias son incorrectas.
    
    Args:
        beliefs: Sistema de creencias del agente
        start: Posición inicial (row, col)
        goal: Posición objetivo (row, col)
        allow_unknown: Si True, permite transitar por celdas desconocidas (con mayor costo)
        
    Returns:
        Lista de posiciones [(row, col), ...] desde start hasta goal,
        o None si no se encuentra ruta.
    """
    rows, cols = beliefs.rows, beliefs.cols
    
    # Validar posiciones
    if not (0 <= start[0] < rows and 0 <= start[1] < cols):
        return None
    if not (0 <= goal[0] < rows and 0 <= goal[1] < cols):
        return None
    
    # Cola de prioridad: (f_score, counter, posición)
    counter = 0
    open_set = []
    heapq.heappush(open_set, (0, counter, start))
    
    came_from: Dict[Tuple[int, int], Tuple[int, int]] = {}
    g_score: Dict[Tuple[int, int], float] = {start: 0}
    f_score: Dict[Tuple[int, int], float] = {start: heuristic(start, goal)}
    
    closed_set = set()
    
    while open_set:
        current_f, _, current = heapq.heappop(open_set)
        
        if current == goal:
            # Reconstruir camino
            path = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            path.reverse()
            return path
        
        if current in closed_set:
            continue
        closed_set.add(current)
        
        # Explorar vecinos (4 direcciones)
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            neighbor = (current[0] + dr, current[1] + dc)
            nr, nc = neighbor
            
            if nr < 0 or nr >= rows or nc < 0 or nc >= cols:
                continue
            if neighbor in closed_set:
                continue
            
            # Verificar si la celda es transitable según las creencias
            belief = beliefs.get_belief(nr, nc)
            
            if belief == BLOCKED or belief == ACCIDENT:
                continue
            if belief == UNKNOWN and not allow_unknown:
                continue
            
            # Calcular costo de movimiento
            move_cost = beliefs.get_cell_cost(nr, nc)
            
            tentative_g = g_score[current] + move_cost
            
            if tentative_g < g_score.get(neighbor, float('inf')):
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                f = tentative_g + heuristic(neighbor, goal)
                f_score[neighbor] = f
                counter += 1
                heapq.heappush(open_set, (f, counter, neighbor))
    
    return None  # No se encontró ruta


def find_nearest_unknown(
    beliefs: BeliefSystem,
    position: Tuple[int, int]
) -> Optional[Tuple[int, int]]:
    """
    Encuentra la celda desconocida más cercana accesible.
    Útil para decidir hacia dónde explorar cuando no hay ruta conocida.
    
    Usa BFS para encontrar la celda desconocida más cercana.
    
    Args:
        beliefs: Sistema de creencias del agente
        position: Posición actual del agente
        
    Returns:
        Posición de la celda desconocida más cercana, o None
    """
    from collections import deque
    
    rows, cols = beliefs.rows, beliefs.cols
    visited = set()
    queue = deque([position])
    visited.add(position)
    
    while queue:
        current = queue.popleft()
        
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = current[0] + dr, current[1] + dc
            neighbor = (nr, nc)
            
            if nr < 0 or nr >= rows or nc < 0 or nc >= cols:
                continue
            if neighbor in visited:
                continue
            visited.add(neighbor)
            
            belief = beliefs.get_belief(nr, nc)
            
            # Si encontramos una celda desconocida adyacente a una explorada
            if belief == UNKNOWN:
                # Retornar la celda explorada desde donde se puede alcanzar
                return neighbor
            
            # Solo avanzar por celdas transitables
            if belief != BLOCKED and belief != ACCIDENT:
                queue.append(neighbor)
    
    return None


def find_exploration_target(
    beliefs: BeliefSystem,
    position: Tuple[int, int],
    goal: Tuple[int, int]
) -> Optional[List[Tuple[int, int]]]:
    """
    Encuentra una ruta de exploración cuando no hay ruta directa al objetivo.
    
    Busca la celda desconocida más cercana en la dirección general del objetivo
    y calcula una ruta hacia ella.
    
    Args:
        beliefs: Sistema de creencias
        position: Posición actual
        goal: Destino deseado
        
    Returns:
        Ruta hacia la celda de exploración, o None
    """
    nearest = find_nearest_unknown(beliefs, position)
    if nearest is None:
        return None
    
    # Intentar calcular ruta hacia la celda desconocida
    route = a_star(beliefs, position, nearest, allow_unknown=True)
    return route


def get_route_cost(beliefs: BeliefSystem, route: List[Tuple[int, int]]) -> float:
    """
    Calcula el costo total de una ruta según las creencias actuales.
    
    Args:
        beliefs: Sistema de creencias
        route: Lista de posiciones de la ruta
        
    Returns:
        Costo total acumulado
    """
    if not route:
        return float('inf')
    
    total_cost = 0.0
    for pos in route[1:]:  # Saltar la posición inicial
        total_cost += beliefs.get_cell_cost(pos[0], pos[1])
    
    return total_cost
