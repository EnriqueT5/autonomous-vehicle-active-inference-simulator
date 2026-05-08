"""
sensors.py — Sistema de percepción parcial del agente.

Responsabilidades:
- Lectura de sensores en las 4 direcciones (adelante, atrás, izquierda, derecha)
- Generación de observaciones parciales (o)
- El agente SOLO puede ver las celdas adyacentes, NO el mapa completo
- Detección de obstáculos, tráfico, semáforos, accidentes, lluvia
"""

from typing import Dict, Tuple
from backend.world import World, FREE, BLOCKED, TRAFFIC, SEMAPHORE, ACCIDENT, RAIN


class Sensors:
    """
    Sistema de sensores del vehículo autónomo.
    
    Simula percepción parcial: el agente solo puede observar
    las celdas inmediatamente adyacentes en 4 direcciones.
    """

    # Mapeo de dirección del agente a offsets de observación
    # (front, back, left, right) relativo a la dirección actual
    DIRECTION_OFFSETS = {
        "up": {
            "front": (-1, 0),
            "back": (1, 0),
            "left": (0, -1),
            "right": (0, 1),
        },
        "down": {
            "front": (1, 0),
            "back": (-1, 0),
            "left": (0, 1),
            "right": (0, -1),
        },
        "left": {
            "front": (0, -1),
            "back": (0, 1),
            "left": (1, 0),
            "right": (-1, 0),
        },
        "right": {
            "front": (0, 1),
            "back": (0, -1),
            "left": (-1, 0),
            "right": (1, 0),
        },
    }

    def __init__(self, world: World):
        """
        Inicializa los sensores conectados al mundo real.
        
        Args:
            world: Referencia al entorno real η
        """
        self.world = world

    def observe(self, position: Tuple[int, int], direction: str = "right") -> Dict[str, str]:
        """
        Genera observaciones parciales desde la posición actual del agente.
        
        El agente solo puede ver las 4 celdas adyacentes.
        
        Args:
            position: Posición actual (row, col)
            direction: Dirección actual del agente ("up", "down", "left", "right")
            
        Returns:
            Dict con las observaciones: {"front": ..., "back": ..., "left": ..., "right": ...}
        """
        row, col = position
        offsets = self.DIRECTION_OFFSETS.get(direction, self.DIRECTION_OFFSETS["right"])
        
        observations = {}
        for sensor_dir, (dr, dc) in offsets.items():
            nr, nc = row + dr, col + dc
            observations[sensor_dir] = self._read_cell(nr, nc)
        
        return observations

    def _read_cell(self, row: int, col: int) -> str:
        """
        Lee una celda individual y devuelve su estado como string.
        
        Args:
            row, col: Posición de la celda a leer
            
        Returns:
            String describiendo el estado de la celda
        """
        if not self.world.is_valid_position(row, col):
            return "wall"  # Fuera de límites

        cell = self.world.get_cell(row, col)
        
        if cell == FREE:
            return "free"
        elif cell == BLOCKED:
            return "blocked"
        elif cell == TRAFFIC:
            return "traffic"
        elif cell == SEMAPHORE:
            state = self.world.get_semaphore_state(row, col)
            return f"semaphore_{state}"
        elif cell == ACCIDENT:
            return "accident"
        elif cell == RAIN:
            return "rain"
        else:
            return "unknown"

    def get_adjacent_cells(self, position: Tuple[int, int]) -> Dict[str, Tuple[int, int]]:
        """
        Obtiene las posiciones de las celdas adyacentes (arriba, abajo, izq, der).
        
        Args:
            position: Posición actual (row, col)
            
        Returns:
            Dict con las posiciones adyacentes
        """
        row, col = position
        return {
            "up": (row - 1, col),
            "down": (row + 1, col),
            "left": (row, col - 1),
            "right": (row, col + 1),
        }

    def get_observable_cell_types(self, position: Tuple[int, int]) -> Dict[str, int]:
        """
        Obtiene los tipos de celda numéricos para las 4 celdas adyacentes.
        Usado para actualizar las creencias del agente.
        
        Args:
            position: Posición actual (row, col)
            
        Returns:
            Dict con tipos de celda: {"up": int, "down": int, "left": int, "right": int}
        """
        row, col = position
        result = {}
        directions = {
            "up": (-1, 0),
            "down": (1, 0),
            "left": (0, -1),
            "right": (0, 1),
        }
        
        for dir_name, (dr, dc) in directions.items():
            nr, nc = row + dr, col + dc
            if self.world.is_valid_position(nr, nc):
                result[dir_name] = int(self.world.get_cell(nr, nc))
            else:
                result[dir_name] = BLOCKED  # Fuera de límites = bloqueado
        
        return result

    def scan_radius(self, position: Tuple[int, int], radius: int = 1) -> Dict[Tuple[int, int], int]:
        """
        Escanea un radio alrededor de la posición actual.
        Por defecto radio = 1 (solo adyacentes).
        
        Args:
            position: Posición central
            radius: Radio de escaneo
            
        Returns:
            Dict de posiciones -> tipo de celda
        """
        row, col = position
        scanned = {}
        
        for dr in range(-radius, radius + 1):
            for dc in range(-radius, radius + 1):
                if dr == 0 and dc == 0:
                    continue  # Saltar la posición actual
                nr, nc = row + dr, col + dc
                if self.world.is_valid_position(nr, nc):
                    scanned[(nr, nc)] = int(self.world.get_cell(nr, nc))
        
        return scanned
