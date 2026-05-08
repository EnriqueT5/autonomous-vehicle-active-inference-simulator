"""
agent.py — Lógica del agente autónomo con Active Inference.

Responsabilidades:
- Máquina de estados (SEARCHING, MOVING, WAITING, ANALYZING, etc.)
- Ciclo de decisión completo
- Selección entre acción pragmática y epistémica
- Gestión de destino y ruta
- Homeostasis (seguridad, energía, incertidumbre, progreso)
"""

import random
from typing import List, Tuple, Optional, Dict, Any

from backend.world import World, FREE, BLOCKED, TRAFFIC, SEMAPHORE, ACCIDENT, RAIN
from backend.beliefs import BeliefSystem, UNKNOWN
from backend.sensors import Sensors
from backend.pathfinding import a_star, find_exploration_target, find_nearest_unknown


class Agent:
    """
    Agente autónomo basado en Active Inference.
    
    El agente mantiene creencias internas (μ), recibe observaciones parciales (o)
    del entorno real (η), y ejecuta acciones (a) para:
    - Navegar hacia el destino B
    - Explorar zonas desconocidas
    - Reducir incertidumbre
    - Evitar peligros
    - Mantener homeostasis
    """

    # Estados de la máquina de estados
    SEARCHING = "SEARCHING"
    MOVING = "MOVING"
    WAITING = "WAITING"
    ANALYZING = "ANALYZING"
    RECALCULATING = "RECALCULATING"
    EXPLORING = "EXPLORING"
    STOPPED = "STOPPED"
    ARRIVED = "ARRIVED"

    def __init__(self, world: World):
        """
        Inicializa el agente conectado a un mundo.
        
        Args:
            world: El entorno real η (el agente no accede directamente a él,
                   solo a través de los sensores)
        """
        self.world = world
        self.sensors = Sensors(world)
        self.beliefs = BeliefSystem(world.rows, world.cols)
        
        # Posición y dirección
        self.position: Tuple[int, int] = world.start
        self.direction: str = "right"  # up, down, left, right
        
        # Destino
        self.destination: Tuple[int, int] = world.destination
        
        # Estado de la máquina de estados
        self.state: str = self.SEARCHING
        
        # Modo de acción actual
        self.mode: str = "PRAGMATIC"  # PRAGMATIC o EPISTEMIC
        
        # Ruta planificada
        self.route: List[Tuple[int, int]] = []
        self.route_index: int = 0
        
        # Última acción ejecutada
        self.last_action: str = "initialized"
        self.last_log: str = "Agente inicializado. Listo para navegar."
        
        # Métricas de homeostasis
        self.safety: float = 1.0
        self.energy: float = 1.0
        self.progress: float = 0.0
        self.risk_level: float = 0.0
        
        # Métricas acumuladas
        self.steps_taken: int = 0
        self.blocks_detected: int = 0
        self.recalculations: int = 0
        self.pragmatic_actions: int = 0
        self.epistemic_actions: int = 0
        self.wait_counter: int = 0
        
        # Logs
        self.logs: List[str] = ["🚗 Agente inicializado. Esperando inicio de simulación."]
        
        # Observación inicial
        self._initial_observe()

    def _initial_observe(self):
        """Realiza la observación inicial desde la posición de inicio."""
        observed = self.sensors.get_observable_cell_types(self.position)
        self.beliefs.update_from_observations(self.position, observed)

    def reset(self, world: World):
        """Reinicia el agente para un nuevo mapa/simulación."""
        self.world = world
        self.sensors = Sensors(world)
        self.beliefs.reset(world.rows, world.cols)
        self.position = world.start
        self.direction = "right"
        self.destination = world.destination
        self.state = self.SEARCHING
        self.mode = "PRAGMATIC"
        self.route = []
        self.route_index = 0
        self.last_action = "reset"
        self.last_log = "Agente reiniciado."
        self.safety = 1.0
        self.energy = 1.0
        self.progress = 0.0
        self.risk_level = 0.0
        self.steps_taken = 0
        self.blocks_detected = 0
        self.recalculations = 0
        self.pragmatic_actions = 0
        self.epistemic_actions = 0
        self.wait_counter = 0
        self.logs = ["🔄 Agente reiniciado. Nueva simulación."]
        self._initial_observe()

    # ============================================================
    # CICLO DE DECISIÓN PRINCIPAL
    # ============================================================

    def decision_cycle(self) -> Dict[str, Any]:
        """
        Ejecuta un ciclo completo de decisión del agente.
        
        Pasos:
        1. Leer posición actual
        2. Observar entorno (4 direcciones)
        3. Actualizar creencias μ
        4. Evaluar riesgos
        5. Verificar si la ruta sigue siendo válida
        6. Decidir acción (pragmática o epistémica)
        7. Ejecutar acción
        8. Actualizar métricas
        9. Generar respuesta para el frontend
        
        Returns:
            Dict con el estado completo del agente para el frontend
        """
        # Si ya llegó al destino, no hacer nada
        if self.state == self.ARRIVED:
            return self._build_response()

        # 1. Posición actual
        row, col = self.position

        # 2. Observar entorno
        observations = self.sensors.observe(self.position, self.direction)
        observed_types = self.sensors.get_observable_cell_types(self.position)

        # 3. Actualizar creencias
        beliefs_changed = self.beliefs.update_from_observations(self.position, observed_types)

        # 4. Evaluar riesgos
        self._evaluate_risks(observations)

        # 5. Verificar destino alcanzado
        if self.position == self.destination:
            self.state = self.ARRIVED
            self.last_action = "arrived"
            self.last_log = (
                f"🏁 ¡Destino alcanzado! El vehículo llegó del punto A al punto B. "
                f"Ruta completada con éxito."
            )
            self.logs.append(self.last_log)
            self.progress = 1.0
            return self._build_response()

        # 6. Verificar validez de la ruta actual
        route_valid = self._check_route_validity()

        # 7. Decidir y ejecutar acción
        if not route_valid or not self.route:
            # Necesita calcular o recalcular ruta
            self._recalculate_route()
        
        if self.route and self.route_index < len(self.route):
            # Tiene ruta: intentar avanzar
            self._execute_pragmatic_action(observations)
        else:
            # Sin ruta: explorar
            self._execute_epistemic_action(observations)

        # 8. Actualizar métricas
        self._update_metrics()

        # 9. Generar respuesta
        return self._build_response()

    # ============================================================
    # ACCIONES PRAGMÁTICAS — Avanzar hacia el objetivo
    # ============================================================

    def _execute_pragmatic_action(self, observations: Dict[str, str]):
        """
        Ejecuta una acción pragmática: seguir la ruta conocida hacia el destino.
        El agente usa conocimiento útil para avanzar.
        """
        self.mode = "PRAGMATIC"
        
        if self.route_index >= len(self.route):
            self._recalculate_route()
            if not self.route:
                self._execute_epistemic_action(observations)
                return

        next_pos = self.route[self.route_index]
        
        # Verificar si la siguiente celda es transitable en el mundo real
        nr, nc = next_pos
        real_cell = self.world.get_cell(nr, nc)
        
        # Manejar semáforo rojo
        if real_cell == SEMAPHORE:
            sem_state = self.world.get_semaphore_state(nr, nc)
            if sem_state == "red":
                self.state = self.WAITING
                self.last_action = "wait_semaphore"
                self.last_log = "🔴 Semáforo rojo detectado. Esperando..."
                self.logs.append(self.last_log)
                self.wait_counter += 1
                # Después de esperar 2 ciclos, intentar de nuevo
                if self.wait_counter >= 2:
                    self.wait_counter = 0
                    self.world.toggle_semaphores()
                return

        # Si la celda real está bloqueada o tiene accidente (pero el agente no lo sabía)
        if real_cell == BLOCKED or real_cell == ACCIDENT:
            self.blocks_detected += 1
            self.beliefs.mark_cell(nr, nc, real_cell)
            self.state = self.RECALCULATING
            self.last_action = "route_blocked"
            self.last_log = (
                f"🚧 Ruta bloqueada en ({nr},{nc}). "
                f"Creencia incorrecta corregida. Recalculando ruta..."
            )
            self.logs.append(self.last_log)
            self.recalculations += 1
            self._recalculate_route()
            return

        # Avanzar a la siguiente celda
        self.wait_counter = 0
        self._move_to(next_pos)
        self.route_index += 1
        self.state = self.MOVING
        self.pragmatic_actions += 1
        
        # Determinar la acción específica
        dr = next_pos[0] - self.position[0] if next_pos != self.position else 0
        dc = next_pos[1] - self.position[1] if next_pos != self.position else 0
        
        action_name = "avanzar"
        if real_cell == TRAFFIC:
            self.last_log = f"🚗 Acción pragmática: avanzando por zona de tráfico hacia ({nr},{nc})."
        elif real_cell == RAIN:
            self.last_log = f"🌧️ Acción pragmática: avanzando bajo lluvia hacia ({nr},{nc})."
        else:
            self.last_log = f"➡️ Acción pragmática: avanzando por ruta conocida hacia ({nr},{nc})."
        
        self.last_action = action_name
        self.logs.append(self.last_log)

    # ============================================================
    # ACCIONES EPISTÉMICAS — Explorar y reducir incertidumbre
    # ============================================================

    def _execute_epistemic_action(self, observations: Dict[str, str]):
        """
        Ejecuta una acción epistémica: explorar, analizar, reducir incertidumbre.
        El agente busca información nueva cuando no tiene ruta segura.
        """
        self.mode = "EPISTEMIC"
        self.epistemic_actions += 1
        
        # Buscar celda desconocida cercana para explorar
        unknown_neighbors = self.beliefs.get_unknown_neighbors(self.position)
        
        if unknown_neighbors:
            # Explorar una celda desconocida adyacente
            target = unknown_neighbors[0]
            real_cell = self.world.get_cell(target[0], target[1])
            
            if real_cell != BLOCKED and real_cell != ACCIDENT:
                self._move_to(target)
                self.state = self.EXPLORING
                self.last_action = "explore"
                self.last_log = (
                    f"🔍 Acción epistémica: explorando celda desconocida ({target[0]},{target[1]}). "
                    f"Reduciendo incertidumbre."
                )
            else:
                # La celda desconocida resultó ser un bloqueo
                self.beliefs.mark_cell(target[0], target[1], real_cell)
                self.state = self.ANALYZING
                self.last_action = "analyze"
                self.last_log = (
                    f"🔬 Acción epistémica: analizando entorno. "
                    f"Celda ({target[0]},{target[1]}) descubierta como "
                    f"{self.world.get_cell_name(real_cell)}."
                )
                self.blocks_detected += 1
        else:
            # Sin celdas desconocidas adyacentes — buscar ruta de exploración
            exploration_route = find_exploration_target(
                self.beliefs, self.position, self.destination
            )
            
            if exploration_route and len(exploration_route) > 1:
                next_pos = exploration_route[1]
                real_cell = self.world.get_cell(next_pos[0], next_pos[1])
                
                if real_cell != BLOCKED and real_cell != ACCIDENT:
                    self._move_to(next_pos)
                    self.state = self.EXPLORING
                    self.last_action = "explore_move"
                    self.last_log = (
                        f"🧭 Acción epistémica: moviéndose hacia zona desconocida "
                        f"({next_pos[0]},{next_pos[1]})."
                    )
                else:
                    self.beliefs.mark_cell(next_pos[0], next_pos[1], real_cell)
                    self.state = self.ANALYZING
                    self.last_action = "blocked_exploration"
                    self.last_log = "🔬 Exploración bloqueada. Analizando alternativas..."
            else:
                # No hay a donde ir — detenerse
                self.state = self.STOPPED
                self.last_action = "stopped"
                self.last_log = "⛔ No se encontró ruta ni destino de exploración. Detenido."
        
        self.logs.append(self.last_log)
        
        # Después de explorar, intentar recalcular ruta al destino
        self._recalculate_route()

    # ============================================================
    # MOVIMIENTO
    # ============================================================

    def _move_to(self, new_pos: Tuple[int, int]):
        """
        Mueve el agente a una nueva posición y actualiza la dirección.
        
        Args:
            new_pos: Nueva posición (row, col)
        """
        old_pos = self.position
        dr = new_pos[0] - old_pos[0]
        dc = new_pos[1] - old_pos[1]
        
        # Actualizar dirección
        if dr < 0:
            self.direction = "up"
        elif dr > 0:
            self.direction = "down"
        elif dc < 0:
            self.direction = "left"
        elif dc > 0:
            self.direction = "right"
        
        self.position = new_pos
        self.steps_taken += 1
        self.energy = max(0, self.energy - 0.005)
        
        # Observar desde la nueva posición
        observed = self.sensors.get_observable_cell_types(self.position)
        self.beliefs.update_from_observations(self.position, observed)

    # ============================================================
    # RUTA
    # ============================================================

    def _recalculate_route(self):
        """Recalcula la ruta desde la posición actual hasta el destino usando A*."""
        route = a_star(self.beliefs, self.position, self.destination, allow_unknown=True)
        
        if route:
            self.route = route
            self.route_index = 1  # Saltar la posición actual
            if self.state == self.RECALCULATING:
                self.last_log += " Nueva ruta calculada."
        else:
            self.route = []
            self.route_index = 0

    def _check_route_validity(self) -> bool:
        """
        Verifica si la ruta actual sigue siendo válida según las creencias.
        
        Returns:
            True si la ruta es válida, False si necesita recalculación
        """
        if not self.route or self.route_index >= len(self.route):
            return False
        
        # Verificar que las celdas restantes de la ruta son transitables
        for i in range(self.route_index, len(self.route)):
            pos = self.route[i]
            if not self.beliefs.is_believed_walkable(pos[0], pos[1]):
                return False
        
        return True

    # ============================================================
    # EVALUACIÓN DE RIESGOS
    # ============================================================

    def _evaluate_risks(self, observations: Dict[str, str]):
        """
        Evalúa los riesgos en el entorno cercano.
        Actualiza los indicadores de seguridad y riesgo.
        """
        risk = 0.0
        safety = 1.0
        
        for direction, obs in observations.items():
            if obs == "accident":
                risk += 0.3
                safety -= 0.2
            elif obs == "blocked":
                risk += 0.1
            elif obs == "traffic":
                risk += 0.15
                safety -= 0.05
            elif obs.startswith("semaphore_red"):
                risk += 0.05
            elif obs == "rain":
                risk += 0.1
                safety -= 0.05
        
        self.risk_level = min(1.0, risk)
        self.safety = max(0.0, safety)

    # ============================================================
    # MÉTRICAS
    # ============================================================

    def _update_metrics(self):
        """Actualiza las métricas de progreso y homeostasis."""
        if self.destination:
            # Calcular progreso como inverso de la distancia Manhattan
            total_dist = abs(self.world.start[0] - self.destination[0]) + \
                        abs(self.world.start[1] - self.destination[1])
            current_dist = abs(self.position[0] - self.destination[0]) + \
                          abs(self.position[1] - self.destination[1])
            
            if total_dist > 0:
                self.progress = max(0, 1.0 - (current_dist / total_dist))
            else:
                self.progress = 1.0

    def get_homeostasis(self) -> Dict[str, float]:
        """Retorna las métricas de homeostasis actuales."""
        return {
            "safety": round(self.safety, 2),
            "energy": round(self.energy, 2),
            "uncertainty": round(self.beliefs.get_uncertainty(), 2),
            "progress": round(self.progress, 2),
            "estimated_time": len(self.route) - self.route_index if self.route else 0,
            "risk_level": round(self.risk_level, 2),
        }

    def get_metrics(self) -> Dict[str, Any]:
        """Retorna las métricas acumuladas de la simulación."""
        return {
            "steps_taken": self.steps_taken,
            "blocks_detected": self.blocks_detected,
            "recalculations": self.recalculations,
            "map_discovered_pct": round(self.beliefs.get_discovery_percentage(), 1),
            "final_uncertainty": round(self.beliefs.get_uncertainty(), 2),
            "pragmatic_actions": self.pragmatic_actions,
            "epistemic_actions": self.epistemic_actions,
            "corrections": self.beliefs.corrections,
        }

    # ============================================================
    # CAMBIO DE DESTINO
    # ============================================================

    def set_destination(self, row: int, col: int) -> bool:
        """
        Establece un nuevo destino y recalcula la ruta.
        
        Args:
            row, col: Nueva posición del destino
            
        Returns:
            True si el destino es válido, False si no
        """
        if not self.world.is_valid_position(row, col):
            return False
        
        self.destination = (row, col)
        self.world.set_destination(row, col)
        self.state = self.RECALCULATING
        self.route = []
        self.route_index = 0
        
        self._recalculate_route()
        
        if self.route:
            self.last_log = f"🎯 Nuevo destino B establecido en ({row},{col}). Ruta recalculada."
        else:
            self.last_log = f"⚠️ Nuevo destino en ({row},{col}) pero no se encontró ruta accesible."
        
        self.logs.append(self.last_log)
        if self.state == self.ARRIVED:
            self.state = self.SEARCHING
        return True

    def set_start(self, row: int, col: int) -> bool:
        """Establece un nuevo punto de inicio."""
        if not self.world.is_valid_position(row, col) or not self.world.is_walkable(row, col):
            return False
        
        self.world.set_start(row, col)
        self.position = (row, col)
        self.state = self.SEARCHING
        self.route = []
        self.route_index = 0
        self.beliefs.reset(self.world.rows, self.world.cols)
        self._initial_observe()
        self._recalculate_route()
        
        self.last_log = f"📍 Nuevo punto A establecido en ({row},{col})."
        self.logs.append(self.last_log)
        return True

    # ============================================================
    # RESPUESTA
    # ============================================================

    def _build_response(self) -> Dict[str, Any]:
        """Construye la respuesta completa del ciclo de decisión."""
        observations = self.sensors.observe(self.position, self.direction)
        
        return {
            "agent_state": self.state,
            "mode": self.mode,
            "position": list(self.position),
            "agent_position": list(self.position),
            "destination": list(self.destination),
            "direction": self.direction,
            "action": self.last_action,
            "observations": observations,
            "beliefs_updated": True,
            "uncertainty": round(self.beliefs.get_uncertainty(), 2),
            "route": [list(p) for p in self.route],
            "log": self.last_log,
            "homeostasis": self.get_homeostasis(),
            "metrics": self.get_metrics(),
            "real_world": self.world.get_grid_as_list(),
            "belief_map": self.beliefs.get_belief_map_as_list(),
            "explored_cells": self.beliefs.get_explored_cells_as_list(),
            "start": list(self.world.start),
        }
