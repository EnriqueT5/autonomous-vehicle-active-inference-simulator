"""
beliefs.py — Sistema de creencias internas del agente (μ).

Responsabilidades:
- Mantener un mapa interno separado del mundo real
- Actualizar creencias basándose en observaciones parciales
- Calcular nivel de incertidumbre
- Registrar celdas exploradas vs desconocidas
- Permitir que las creencias sean temporalmente incorrectas
"""

import numpy as np
from typing import List, Tuple, Dict, Set

# Tipos de celda en el mapa de creencias
UNKNOWN = -1    # Celda no explorada (?)
FREE = 0        # Carretera libre
BLOCKED = 1     # Bloqueo
TRAFFIC = 2     # Tráfico
SEMAPHORE = 3   # Semáforo
ACCIDENT = 4    # Accidente
RAIN = 5        # Lluvia


class BeliefSystem:
    """
    Sistema de creencias internas μ del agente.
    
    Mantiene un mapa parcial que el agente construye gradualmente
    mediante exploración. El agente toma decisiones basándose en
    este mapa interno, NO en el mapa real completo.
    
    Las creencias pueden ser incorrectas temporalmente hasta que
    el agente vuelva a observar esa zona del entorno.
    """

    def __init__(self, rows: int, cols: int):
        """
        Inicializa el mapa de creencias completamente desconocido.
        
        Args:
            rows: Número de filas del mapa
            cols: Número de columnas del mapa
        """
        self.rows = rows
        self.cols = cols
        # Inicialmente todo es desconocido (-1)
        self.belief_map = np.full((rows, cols), UNKNOWN, dtype=int)
        # Conjunto de celdas exploradas (visitadas o observadas)
        self.explored_cells: Set[Tuple[int, int]] = set()
        # Historial de observaciones
        self.observation_history: List[Dict] = []
        # Contador de errores corregidos
        self.corrections: int = 0
        # Incertidumbre global (0 = todo conocido, 1 = todo desconocido)
        self.uncertainty: float = 1.0

    def reset(self, rows: int, cols: int):
        """Reinicia las creencias para un nuevo mapa."""
        self.rows = rows
        self.cols = cols
        self.belief_map = np.full((rows, cols), UNKNOWN, dtype=int)
        self.explored_cells = set()
        self.observation_history = []
        self.corrections = 0
        self.uncertainty = 1.0

    # ============================================================
    # ACTUALIZACIÓN DE CREENCIAS
    # ============================================================

    def update_from_observations(
        self,
        position: Tuple[int, int],
        observed_cells: Dict[str, int]
    ) -> bool:
        """
        Actualiza las creencias basándose en las observaciones de los sensores.
        
        El agente observa las celdas adyacentes y actualiza su mapa interno.
        Si una creencia anterior difiere de la nueva observación, se corrige.
        
        Args:
            position: Posición actual del agente (row, col)
            observed_cells: Dict de dirección -> tipo de celda observado
                           {"up": int, "down": int, "left": int, "right": int}
        
        Returns:
            True si alguna creencia fue actualizada/corregida
        """
        row, col = position
        beliefs_changed = False
        
        # Marcar la posición actual como explorada y libre
        if self.belief_map[row, col] != FREE:
            self.belief_map[row, col] = FREE
            beliefs_changed = True
        self.explored_cells.add((row, col))
        
        # Offsets para las 4 direcciones
        direction_offsets = {
            "up": (-1, 0),
            "down": (1, 0),
            "left": (0, -1),
            "right": (0, 1),
        }
        
        for dir_name, cell_type in observed_cells.items():
            if dir_name in direction_offsets:
                dr, dc = direction_offsets[dir_name]
                nr, nc = row + dr, col + dc
                
                if 0 <= nr < self.rows and 0 <= nc < self.cols:
                    old_belief = self.belief_map[nr, nc]
                    
                    # Actualizar la creencia con la nueva observación
                    if old_belief != cell_type:
                        self.belief_map[nr, nc] = cell_type
                        beliefs_changed = True
                        
                        # Si la creencia anterior no era UNKNOWN, es una corrección
                        if old_belief != UNKNOWN:
                            self.corrections += 1
                    
                    self.explored_cells.add((nr, nc))
        
        # Guardar en historial
        self.observation_history.append({
            "position": position,
            "observations": observed_cells,
            "changed": beliefs_changed,
        })
        
        # Recalcular incertidumbre
        self._update_uncertainty()
        
        return beliefs_changed

    def mark_cell(self, row: int, col: int, cell_type: int):
        """Marca una celda específica en el mapa de creencias."""
        if 0 <= row < self.rows and 0 <= col < self.cols:
            self.belief_map[row, col] = cell_type
            self.explored_cells.add((row, col))
            self._update_uncertainty()

    # ============================================================
    # CONSULTAS DE CREENCIAS
    # ============================================================

    def get_belief(self, row: int, col: int) -> int:
        """Obtiene la creencia sobre una celda específica."""
        if 0 <= row < self.rows and 0 <= col < self.cols:
            return int(self.belief_map[row, col])
        return BLOCKED  # Fuera de límites = bloqueado

    def is_explored(self, row: int, col: int) -> bool:
        """Verifica si una celda ha sido explorada."""
        return (row, col) in self.explored_cells

    def is_believed_walkable(self, row: int, col: int) -> bool:
        """
        Determina si el agente CREE que una celda es transitable.
        
        Celdas desconocidas se consideran potencialmente transitables
        (con costo de incertidumbre) para permitir la exploración.
        """
        belief = self.get_belief(row, col)
        # Bloqueado y accidente no son transitables
        if belief == BLOCKED or belief == ACCIDENT:
            return False
        # Desconocido, libre, tráfico, semáforo, lluvia = transitable
        return True

    def get_cell_cost(self, row: int, col: int) -> float:
        """
        Calcula el costo de moverse a una celda según las creencias.
        
        Costos:
        - Libre: 1.0 (bajo)
        - Tráfico: 3.0 (medio)
        - Lluvia: 2.5 (medio-alto)
        - Semáforo: 2.0 (posible espera)
        - Desconocido: 4.0 (costo de incertidumbre)
        - Bloqueado/Accidente: infinito
        """
        belief = self.get_belief(row, col)
        
        costs = {
            FREE: 1.0,
            TRAFFIC: 3.0,
            RAIN: 2.5,
            SEMAPHORE: 2.0,
            UNKNOWN: 4.0,
            BLOCKED: float('inf'),
            ACCIDENT: float('inf'),
        }
        
        return costs.get(belief, float('inf'))

    # ============================================================
    # INCERTIDUMBRE
    # ============================================================

    def _update_uncertainty(self):
        """
        Recalcula el nivel de incertidumbre global.
        
        Incertidumbre = proporción de celdas desconocidas.
        """
        total_cells = self.rows * self.cols
        unknown_cells = np.sum(self.belief_map == UNKNOWN)
        self.uncertainty = unknown_cells / total_cells if total_cells > 0 else 1.0

    def get_uncertainty(self) -> float:
        """Retorna el nivel de incertidumbre actual (0-1)."""
        return self.uncertainty

    def get_discovery_percentage(self) -> float:
        """Retorna el porcentaje del mapa descubierto."""
        return (1.0 - self.uncertainty) * 100.0

    def get_unknown_neighbors(self, position: Tuple[int, int]) -> List[Tuple[int, int]]:
        """
        Obtiene las celdas desconocidas adyacentes a una posición.
        Útil para decidir acciones epistémicas de exploración.
        """
        row, col = position
        unknown = []
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = row + dr, col + dc
            if (0 <= nr < self.rows and 0 <= nc < self.cols 
                and self.belief_map[nr, nc] == UNKNOWN):
                unknown.append((nr, nc))
        return unknown

    # ============================================================
    # SERIALIZACIÓN
    # ============================================================

    def get_belief_map_as_list(self) -> List[List[int]]:
        """Devuelve el mapa de creencias como lista de listas (para JSON)."""
        return self.belief_map.tolist()

    def get_explored_cells_as_list(self) -> List[List[int]]:
        """Devuelve las celdas exploradas como lista de pares [row, col]."""
        return [[r, c] for r, c in self.explored_cells]
