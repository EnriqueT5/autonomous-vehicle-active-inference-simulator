"""
world.py — Definición del entorno real η (eta).

Responsabilidades:
- Almacenar el estado verdadero del mundo (matriz 2D)
- Definir las 4 matrices/escenarios predefinidos + mapa personalizado
- Manejar eventos dinámicos (accidentes, tráfico, semáforos, lluvia)
- Permitir edición del mapa por parte del usuario
- Validar celdas y posiciones
"""

import numpy as np
import random
from typing import List, Tuple, Optional, Dict

# ============================================================
# TIPOS DE CELDA
# ============================================================
FREE = 0        # Carretera libre
BLOCKED = 1     # Bloqueo / obstáculo
TRAFFIC = 2     # Tráfico
SEMAPHORE = 3   # Semáforo
ACCIDENT = 4    # Accidente
RAIN = 5        # Lluvia


class World:
    """
    Representa el entorno real η — el mundo verdadero oculto.
    
    El agente NO tiene acceso directo a este estado completo.
    Solo puede percibir las celdas adyacentes mediante sensores.
    """

    def __init__(self, map_id: int = 1):
        """Inicializa el mundo con el mapa seleccionado."""
        self.map_id = map_id
        self.grid: np.ndarray = None
        self.rows: int = 0
        self.cols: int = 0
        self.start: Tuple[int, int] = (0, 0)
        self.destination: Tuple[int, int] = (0, 0)
        self.semaphore_states: Dict[Tuple[int, int], str] = {}  # "red" o "green"
        self.event_log: List[str] = []
        
        self.load_map(map_id)

    # ============================================================
    # CARGA DE MAPAS / ESCENARIOS
    # ============================================================

    def load_map(self, map_id: int):
        """Carga un mapa predefinido por su ID."""
        self.map_id = map_id
        self.semaphore_states = {}
        self.event_log = []

        if map_id == 1:
            self._load_simple_city()
        elif map_id == 2:
            self._load_traffic_city()
        elif map_id == 3:
            self._load_accident_city()
        elif map_id == 4:
            self._load_complex_city()
        elif map_id == 5:
            self._load_custom_city()
        else:
            self._load_simple_city()

        self.rows, self.cols = self.grid.shape
        self._init_semaphores()

    def _load_simple_city(self):
        """
        Escenario 1: Ciudad simple.
        Matriz pequeña (10x12) con pocas calles y algunos obstáculos.
        Objetivo educativo: explicar navegación básica de A a B.
        """
        self.grid = np.array([
            [1, 1, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1],
            [1, 1, 0, 1, 1, 0, 0, 0, 0, 0, 1, 1],
            [0, 0, 0, 1, 1, 0, 1, 1, 1, 0, 1, 1],
            [0, 1, 1, 1, 0, 0, 0, 1, 1, 0, 0, 0],
            [0, 0, 0, 0, 0, 1, 0, 0, 1, 1, 1, 0],
            [1, 1, 0, 1, 0, 1, 1, 0, 0, 0, 0, 0],
            [1, 1, 0, 1, 0, 0, 0, 0, 1, 1, 1, 0],
            [0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0],
            [0, 1, 1, 1, 0, 0, 0, 0, 1, 0, 1, 1],
            [0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0],
        ])
        self.start = (0, 2)
        self.destination = (9, 11)

    def _load_traffic_city(self):
        """
        Escenario 2: Ciudad con tráfico.
        Matriz mediana (12x15) con semáforos, tráfico y rutas alternativas.
        Objetivo educativo: decisión entre ruta rápida, segura o incierta.
        """
        self.grid = np.array([
            [0, 0, 0, 1, 0, 0, 0, 2, 0, 0, 0, 1, 0, 0, 0],
            [1, 1, 0, 1, 0, 1, 0, 2, 0, 1, 0, 1, 0, 1, 0],
            [0, 0, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0, 0],
            [0, 1, 3, 1, 0, 0, 0, 1, 3, 1, 0, 1, 1, 1, 0],
            [0, 0, 0, 0, 2, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [1, 0, 1, 0, 2, 1, 1, 0, 1, 1, 0, 1, 0, 1, 0],
            [0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 3, 0, 0, 0, 0],
            [0, 1, 0, 0, 1, 0, 1, 2, 1, 0, 0, 0, 1, 1, 0],
            [0, 0, 0, 3, 1, 0, 0, 2, 0, 0, 1, 0, 0, 0, 0],
            [1, 1, 0, 0, 0, 0, 1, 0, 0, 1, 1, 0, 1, 0, 0],
            [0, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 1, 0, 0, 0, 0, 1, 0, 1, 0, 1, 0, 0, 0, 0],
        ])
        self.start = (0, 0)
        self.destination = (11, 14)

    def _load_accident_city(self):
        """
        Escenario 3: Ciudad con accidentes dinámicos.
        Eventos inesperados que ocurren durante la simulación.
        Objetivo educativo: recalculación dinámica y acción epistémica.
        """
        self.grid = np.array([
            [0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0],
            [0, 1, 1, 1, 0, 1, 0, 1, 1, 0, 1, 1, 0],
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [1, 0, 1, 0, 1, 1, 0, 1, 0, 1, 0, 1, 0],
            [0, 0, 1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0],
            [0, 1, 0, 0, 1, 0, 3, 0, 1, 0, 0, 1, 0],
            [0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [1, 0, 1, 1, 0, 1, 0, 1, 1, 0, 1, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 1, 1, 0, 1, 0, 1, 0, 1, 1, 0, 1, 0],
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        ])
        self.start = (0, 0)
        self.destination = (10, 12)

    def _load_complex_city(self):
        """
        Escenario 4: Ciudad compleja tipo red vial grande.
        Múltiples caminos, avenidas, intersecciones y zonas desconocidas.
        Objetivo educativo: aprendizaje gradual y navegación bajo incertidumbre.
        """
        self.grid = np.array([
            [0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0],
            [0, 1, 0, 1, 0, 1, 1, 0, 1, 0, 1, 1, 0, 1, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [1, 0, 1, 0, 1, 0, 1, 3, 1, 0, 1, 0, 1, 0, 1, 0],
            [0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0],
            [0, 1, 0, 0, 1, 2, 1, 0, 1, 2, 1, 0, 0, 1, 0, 0],
            [0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0],
            [1, 0, 1, 0, 0, 1, 0, 3, 0, 1, 0, 0, 1, 0, 1, 0],
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 1, 1, 0, 1, 0, 1, 0, 1, 0, 1, 1, 0, 1, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [1, 0, 1, 0, 1, 0, 0, 0, 0, 0, 1, 0, 1, 0, 1, 0],
            [0, 0, 0, 0, 0, 0, 0, 5, 0, 0, 0, 0, 0, 0, 0, 0],
        ])
        self.start = (0, 0)
        self.destination = (14, 15)

    def _load_custom_city(self):
        """
        Escenario 5: Mapa personalizado vacío.
        El usuario puede dibujar su propio entorno urbano.
        """
        self.grid = np.zeros((12, 15), dtype=int)
        # Bordes bloqueados para dar forma
        self.grid[0, :] = 0
        self.grid[-1, :] = 0
        self.grid[:, 0] = 0
        self.grid[:, -1] = 0
        self.start = (0, 0)
        self.destination = (11, 14)

    # ============================================================
    # SEMÁFOROS
    # ============================================================

    def _init_semaphores(self):
        """Inicializa el estado de todos los semáforos en el mapa."""
        for r in range(self.rows):
            for c in range(self.cols):
                if self.grid[r, c] == SEMAPHORE:
                    # Alternamos entre rojo y verde aleatoriamente
                    self.semaphore_states[(r, c)] = random.choice(["red", "green"])

    def toggle_semaphores(self):
        """Cambia el estado de todos los semáforos (rojo <-> verde)."""
        for pos in self.semaphore_states:
            if self.semaphore_states[pos] == "red":
                self.semaphore_states[pos] = "green"
            else:
                self.semaphore_states[pos] = "red"

    def get_semaphore_state(self, row: int, col: int) -> str:
        """Obtiene el estado de un semáforo específico."""
        return self.semaphore_states.get((row, col), "green")

    # ============================================================
    # CONSULTAS DEL MUNDO
    # ============================================================

    def get_cell(self, row: int, col: int) -> int:
        """Obtiene el tipo de celda en una posición."""
        if 0 <= row < self.rows and 0 <= col < self.cols:
            return int(self.grid[row, col])
        return BLOCKED  # Fuera de límites = bloqueado

    def is_walkable(self, row: int, col: int) -> bool:
        """Determina si una celda es transitable (no bloqueada ni accidente)."""
        cell = self.get_cell(row, col)
        return cell != BLOCKED and cell != ACCIDENT

    def is_valid_position(self, row: int, col: int) -> bool:
        """Verifica si una posición está dentro de los límites del mapa."""
        return 0 <= row < self.rows and 0 <= col < self.cols

    def get_cell_name(self, cell_type: int) -> str:
        """Devuelve el nombre legible de un tipo de celda."""
        names = {
            FREE: "free",
            BLOCKED: "blocked",
            TRAFFIC: "traffic",
            SEMAPHORE: "semaphore",
            ACCIDENT: "accident",
            RAIN: "rain",
        }
        return names.get(cell_type, "unknown")

    # ============================================================
    # EDICIÓN DEL MAPA
    # ============================================================

    def set_cell(self, row: int, col: int, cell_type: int):
        """Establece el tipo de una celda en el mapa real."""
        if self.is_valid_position(row, col):
            old_type = int(self.grid[row, col])
            self.grid[row, col] = cell_type
            
            # Gestionar semáforos
            if cell_type == SEMAPHORE:
                self.semaphore_states[(row, col)] = "green"
            elif (row, col) in self.semaphore_states and cell_type != SEMAPHORE:
                del self.semaphore_states[(row, col)]
            
            self.event_log.append(
                f"Celda ({row},{col}) cambiada de {self.get_cell_name(old_type)} "
                f"a {self.get_cell_name(cell_type)}"
            )

    def set_start(self, row: int, col: int) -> bool:
        """Establece el punto inicial A."""
        if self.is_valid_position(row, col) and self.is_walkable(row, col):
            self.start = (row, col)
            self.event_log.append(f"Nuevo punto A establecido en ({row},{col})")
            return True
        return False

    def set_destination(self, row: int, col: int) -> bool:
        """Establece el destino B."""
        if self.is_valid_position(row, col) and self.is_walkable(row, col):
            self.destination = (row, col)
            self.event_log.append(f"Nuevo destino B establecido en ({row},{col})")
            return True
        return False

    # ============================================================
    # EVENTOS DINÁMICOS
    # ============================================================

    def generate_random_event(self) -> Optional[str]:
        """
        Genera un evento dinámico aleatorio en el mapa.
        Puede crear accidentes, tráfico, lluvia o liberar calles.
        Retorna una descripción del evento o None.
        """
        event_type = random.choice(["accident", "traffic", "rain", "block", "clear", "none", "none"])
        
        if event_type == "none":
            return None

        # Buscar una celda libre aleatoria (no sobre inicio ni destino)
        attempts = 0
        while attempts < 50:
            r = random.randint(0, self.rows - 1)
            c = random.randint(0, self.cols - 1)
            if (r, c) != self.start and (r, c) != self.destination:
                if event_type == "clear":
                    # Liberar una celda bloqueada
                    if self.grid[r, c] in [BLOCKED, ACCIDENT, TRAFFIC]:
                        self.grid[r, c] = FREE
                        msg = f"⚡ Calle ({r},{c}) liberada"
                        self.event_log.append(msg)
                        return msg
                elif event_type == "accident" and self.grid[r, c] == FREE:
                    self.grid[r, c] = ACCIDENT
                    msg = f"🚨 Accidente en ({r},{c})"
                    self.event_log.append(msg)
                    return msg
                elif event_type == "traffic" and self.grid[r, c] == FREE:
                    self.grid[r, c] = TRAFFIC
                    msg = f"🚗 Tráfico en ({r},{c})"
                    self.event_log.append(msg)
                    return msg
                elif event_type == "rain" and self.grid[r, c] == FREE:
                    self.grid[r, c] = RAIN
                    msg = f"🌧️ Lluvia en ({r},{c})"
                    self.event_log.append(msg)
                    return msg
                elif event_type == "block" and self.grid[r, c] == FREE:
                    self.grid[r, c] = BLOCKED
                    msg = f"🚧 Calle ({r},{c}) bloqueada"
                    self.event_log.append(msg)
                    return msg
            attempts += 1
        
        return None

    def get_grid_as_list(self) -> List[List[int]]:
        """Devuelve la matriz del mundo como lista de listas (para JSON)."""
        return self.grid.tolist()

    def generate_random_map(self, rows: int = 12, cols: int = 15):
        """Genera un mapa aleatorio con calles y obstáculos."""
        self.grid = np.zeros((rows, cols), dtype=int)
        self.rows = rows
        self.cols = cols
        
        # Crear una estructura de carreteras con patrón de cuadrícula
        for r in range(rows):
            for c in range(cols):
                # Avenidas cada 3 filas/columnas
                if r % 3 == 0 or c % 3 == 0:
                    self.grid[r, c] = FREE
                else:
                    self.grid[r, c] = BLOCKED
        
        # Añadir elementos aleatorios
        for _ in range(int(rows * cols * 0.05)):
            r, c = random.randint(0, rows-1), random.randint(0, cols-1)
            if self.grid[r, c] == FREE:
                self.grid[r, c] = random.choice([TRAFFIC, SEMAPHORE, RAIN])
        
        # Establecer inicio y destino
        self.start = (0, 0)
        self.grid[0, 0] = FREE
        self.destination = (rows - 1, cols - 1)
        self.grid[rows-1, cols-1] = FREE
        
        self._init_semaphores()
        self.event_log.append("Mapa aleatorio generado")


# ============================================================
# DESCRIPCIONES DE ESCENARIOS (para el frontend)
# ============================================================

SCENARIO_DESCRIPTIONS = {
    1: {
        "name": "Ciudad Simple",
        "description": "Una matriz pequeña para explicar el funcionamiento básico. "
                       "Pocas calles, algunos obstáculos, ruta relativamente sencilla. "
                       "Ideal para entender cómo el carro pasa del punto A al punto B.",
        "difficulty": "Fácil"
    },
    2: {
        "name": "Ciudad con Tráfico",
        "description": "Matriz mediana con semáforos, tráfico moderado y múltiples "
                       "rutas alternativas. Muestra cómo el agente decide entre "
                       "ruta rápida, ruta segura y ruta incierta.",
        "difficulty": "Medio"
    },
    3: {
        "name": "Ciudad con Accidentes Dinámicos",
        "description": "Eventos inesperados que ocurren durante la simulación: "
                       "accidentes, calles bloqueadas, tráfico cambiante. "
                       "Demuestra recalculación dinámica y acción epistémica.",
        "difficulty": "Difícil"
    },
    4: {
        "name": "Ciudad Compleja — Red Vial",
        "description": "Matriz grande con avenidas, vías secundarias, intersecciones "
                       "y zonas desconocidas. Demuestra cómo el agente aprende el mapa "
                       "gradualmente y navega bajo incertidumbre.",
        "difficulty": "Experto"
    },
    5: {
        "name": "Mapa Personalizado",
        "description": "Crea tu propio mapa urbano. Dibuja carreteras, obstáculos, "
                       "tráfico, semáforos y más. Experimenta con diferentes "
                       "configuraciones y observa cómo reacciona el agente.",
        "difficulty": "Personalizado"
    }
}
