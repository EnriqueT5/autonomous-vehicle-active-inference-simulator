"""
schemas.py — Modelos Pydantic para la simulación de Active Inference.

Define las estructuras de datos para:
- Estado del agente
- Observaciones (sensores)
- Creencias internas (μ)
- Acciones
- Configuración de simulación
- Respuestas de la API
"""

from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from enum import Enum


# ============================================================
# ENUMERACIONES — Estados y tipos del sistema
# ============================================================

class AgentState(str, Enum):
    """Estados posibles de la máquina de estados del agente."""
    SEARCHING = "SEARCHING"
    MOVING = "MOVING"
    WAITING = "WAITING"
    ANALYZING = "ANALYZING"
    RECALCULATING = "RECALCULATING"
    EXPLORING = "EXPLORING"
    STOPPED = "STOPPED"
    ARRIVED = "ARRIVED"


class ActionMode(str, Enum):
    """Tipo de acción: pragmática (avanzar) o epistémica (explorar/analizar)."""
    PRAGMATIC = "PRAGMATIC"
    EPISTEMIC = "EPISTEMIC"


class CellType(int, Enum):
    """Tipos de celda en la matriz del mundo."""
    FREE = 0        # Carretera libre
    BLOCKED = 1     # Bloqueo / obstáculo
    TRAFFIC = 2     # Tráfico
    SEMAPHORE = 3   # Semáforo
    ACCIDENT = 4    # Accidente
    RAIN = 5        # Lluvia
    UNKNOWN = -1    # Desconocido para el agente (?)


class EditTool(str, Enum):
    """Herramientas de edición disponibles para el usuario."""
    FREE = "free"
    BLOCKED = "blocked"
    TRAFFIC = "traffic"
    SEMAPHORE = "semaphore"
    ACCIDENT = "accident"
    RAIN = "rain"
    SET_START = "set_start"
    SET_DESTINATION = "set_destination"
    ERASE = "erase"


class SpeedMode(str, Enum):
    """Modos de velocidad de la simulación."""
    PAUSED = "paused"
    STEP = "step"
    SLOW = "slow"         # 5000ms
    NORMAL = "normal"     # 3000ms
    FAST = "fast"         # 1000ms
    TURBO = "turbo"       # 500ms


# ============================================================
# MODELOS DE DATOS
# ============================================================

class Position(BaseModel):
    """Posición en la cuadrícula 2D."""
    row: int
    col: int


class Observations(BaseModel):
    """Observaciones del agente en las 4 direcciones cardinales."""
    front: str = "unknown"
    back: str = "unknown"
    left: str = "unknown"
    right: str = "unknown"


class HomeostasisMetrics(BaseModel):
    """Métricas de homeostasis del agente."""
    safety: float = 1.0          # 0-1, seguridad actual
    energy: float = 1.0          # 0-1, energía restante
    uncertainty: float = 1.0     # 0-1, nivel de incertidumbre
    progress: float = 0.0        # 0-1, progreso hacia el destino
    estimated_time: int = 0      # pasos estimados restantes
    risk_level: float = 0.0      # 0-1, nivel de riesgo actual


class SimulationMetrics(BaseModel):
    """Métricas acumuladas de la simulación."""
    steps_taken: int = 0
    total_time: float = 0.0
    blocks_detected: int = 0
    recalculations: int = 0
    map_discovered_pct: float = 0.0
    final_uncertainty: float = 1.0
    pragmatic_actions: int = 0
    epistemic_actions: int = 0


class AgentResponse(BaseModel):
    """Respuesta completa del ciclo de decisión del agente."""
    agent_state: str
    mode: str
    position: List[int]
    destination: List[int]
    direction: str = "right"
    action: str
    observations: Dict[str, str]
    beliefs_updated: bool
    uncertainty: float
    route: List[List[int]]
    log: str
    homeostasis: Dict[str, float]
    metrics: Dict[str, Any]
    real_world: List[List[int]]
    belief_map: List[List[int]]
    explored_cells: List[List[int]]


class EditCellRequest(BaseModel):
    """Solicitud para editar una celda del mapa."""
    row: int
    col: int
    cell_type: int


class SetPointRequest(BaseModel):
    """Solicitud para establecer punto A o punto B."""
    row: int
    col: int


class ChangeMapRequest(BaseModel):
    """Solicitud para cambiar de mapa/escenario."""
    map_id: int


class SpeedChangeRequest(BaseModel):
    """Solicitud para cambiar la velocidad de simulación."""
    speed: str


class SimulationState(BaseModel):
    """Estado completo de la simulación para sincronización."""
    real_world: List[List[int]]
    belief_map: List[List[int]]
    agent_position: List[int]
    destination: List[int]
    start: List[int]
    agent_state: str
    mode: str
    direction: str
    route: List[List[int]]
    explored_cells: List[List[int]]
    observations: Dict[str, str]
    homeostasis: Dict[str, float]
    metrics: Dict[str, Any]
    logs: List[str]
    speed_mode: str
    map_id: int
    map_rows: int
    map_cols: int
