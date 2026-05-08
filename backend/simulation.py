"""
simulation.py — Control principal de la simulación.

Responsabilidades:
- Ciclo principal de simulación
- Control de pausa/reanudación
- Modo paso a paso
- Generación de eventos dinámicos
- Sincronización de estado
- Métricas de simulación
"""

import time
import random
from typing import Dict, Any, Optional, List

from backend.world import World, SCENARIO_DESCRIPTIONS
from backend.agent import Agent


class Simulation:
    """
    Controlador principal de la simulación de Active Inference.
    
    Gestiona el ciclo de decisión del agente, los eventos dinámicos,
    el control de velocidad y la sincronización con el frontend.
    """

    def __init__(self):
        """Inicializa la simulación con el mapa por defecto."""
        self.world = World(map_id=1)
        self.agent = Agent(self.world)
        
        # Control de simulación
        self.is_running: bool = False
        self.is_paused: bool = True
        self.speed_mode: str = "normal"  # paused, step, slow, normal, fast, turbo
        self.speed_ms: int = 3000
        
        # Estado del mapa actual
        self.current_map_id: int = 1
        
        # Eventos dinámicos
        self.dynamic_events_enabled: bool = True
        self.event_frequency: int = 5  # Cada N ciclos generar un evento
        self.cycle_count: int = 0
        
        # Tiempo
        self.start_time: float = 0.0
        self.total_time: float = 0.0
        
        # Semáforo toggle counter
        self.semaphore_toggle_counter: int = 0

    # ============================================================
    # CONTROL DE SIMULACIÓN
    # ============================================================

    def start(self):
        """Inicia la simulación."""
        self.is_running = True
        self.is_paused = False
        self.start_time = time.time()

    def pause(self):
        """Pausa la simulación."""
        self.is_paused = True

    def resume(self):
        """Reanuda la simulación."""
        self.is_paused = False

    def stop(self):
        """Detiene la simulación."""
        self.is_running = False
        self.is_paused = True

    def toggle_pause(self):
        """Alterna entre pausa y ejecución."""
        self.is_paused = not self.is_paused

    # ============================================================
    # VELOCIDAD
    # ============================================================

    def set_speed(self, speed_mode: str) -> int:
        """
        Cambia la velocidad de la simulación.
        
        Args:
            speed_mode: "paused", "step", "slow", "normal", "fast", "turbo"
            
        Returns:
            Intervalo en milisegundos
        """
        speed_map = {
            "paused": 0,
            "step": 0,
            "slow": 5000,
            "normal": 3000,
            "fast": 1000,
            "turbo": 500,
        }
        
        self.speed_mode = speed_mode
        self.speed_ms = speed_map.get(speed_mode, 3000)
        
        if speed_mode == "paused":
            self.is_paused = True
        elif speed_mode == "step":
            self.is_paused = True
        else:
            self.is_paused = False
        
        return self.speed_ms

    # ============================================================
    # CICLO DE DECISIÓN
    # ============================================================

    def step(self) -> Dict[str, Any]:
        """
        Ejecuta un paso de la simulación.
        
        1. Generar eventos dinámicos (si corresponde)
        2. Alternar semáforos periódicamente
        3. Ejecutar ciclo de decisión del agente
        4. Actualizar tiempo
        
        Returns:
            Estado completo para el frontend
        """
        self.cycle_count += 1
        
        # Alternar semáforos cada 4 ciclos
        self.semaphore_toggle_counter += 1
        if self.semaphore_toggle_counter >= 4:
            self.world.toggle_semaphores()
            self.semaphore_toggle_counter = 0
        
        # Eventos dinámicos automáticos (solo en escenario 3 o con frecuencia baja)
        event_msg = None
        if self.dynamic_events_enabled and self.cycle_count % self.event_frequency == 0:
            if self.current_map_id == 3 or random.random() < 0.3:
                event_msg = self.world.generate_random_event()
        
        # Ejecutar ciclo de decisión del agente
        result = self.agent.decision_cycle()

        # Si el agente llegó al punto B, detener la simulación
        if self.agent.state == "ARRIVED":
            self.is_running = False
            self.is_paused = True
        
        # Agregar evento dinámico al log si ocurrió
        if event_msg:
            result["log"] = event_msg + " | " + result["log"]
            self.agent.logs.append(event_msg)
        
        # Actualizar tiempo
        if self.start_time > 0:
            self.total_time = time.time() - self.start_time
        
        # Agregar info de simulación
        result["speed_mode"] = self.speed_mode
        result["speed_ms"] = self.speed_ms
        result["cycle"] = self.cycle_count
        result["total_time"] = round(self.total_time, 1)
        result["map_id"] = self.current_map_id
        result["is_paused"] = self.is_paused
        result["logs"] = self.agent.logs[-20:]  # Últimos 20 logs
        
        return result

    # ============================================================
    # GESTIÓN DE MAPAS
    # ============================================================

    def change_map(self, map_id: int) -> Dict[str, Any]:
        """
        Cambia a un mapa/escenario diferente.
        Reinicia todo el estado de la simulación.
        
        Args:
            map_id: ID del mapa (1-5)
            
        Returns:
            Estado inicial del nuevo mapa
        """
        self.current_map_id = map_id
        self.world.load_map(map_id)
        self.agent.reset(self.world)
        
        # Reiniciar contadores
        self.cycle_count = 0
        self.start_time = 0.0
        self.total_time = 0.0
        self.semaphore_toggle_counter = 0
        
        # Ajustar frecuencia de eventos según el mapa
        if map_id == 3:
            self.event_frequency = 3  # Más eventos en ciudad con accidentes
        elif map_id == 4:
            self.event_frequency = 6
        else:
            self.event_frequency = 8
        
        return self.get_full_state()

    def generate_random_map(self) -> Dict[str, Any]:
        """Genera un mapa aleatorio y reinicia la simulación."""
        self.current_map_id = 5
        self.world.generate_random_map()
        self.agent.reset(self.world)
        self.cycle_count = 0
        self.start_time = 0.0
        self.total_time = 0.0
        return self.get_full_state()

    # ============================================================
    # EDICIÓN DEL ENTORNO
    # ============================================================

    def edit_cell(self, row: int, col: int, cell_type: int) -> bool:
        """
        Edita una celda del mapa real.
        
        Args:
            row, col: Posición de la celda
            cell_type: Nuevo tipo de celda
            
        Returns:
            True si la edición fue exitosa
        """
        if (row, col) == tuple(self.agent.position):
            return False  # No editar la celda del agente
        
        self.world.set_cell(row, col, cell_type)
        return True

    def set_destination(self, row: int, col: int) -> bool:
        """Establece un nuevo destino B."""
        return self.agent.set_destination(row, col)

    def set_start(self, row: int, col: int) -> bool:
        """Establece un nuevo punto de inicio A."""
        return self.agent.set_start(row, col)

    # ============================================================
    # ESTADO COMPLETO
    # ============================================================

    def get_full_state(self) -> Dict[str, Any]:
        """
        Devuelve el estado completo de la simulación para sincronización.
        """
        observations = self.agent.sensors.observe(
            self.agent.position, self.agent.direction
        )
        
        return {
            "real_world": self.world.get_grid_as_list(),
            "belief_map": self.agent.beliefs.get_belief_map_as_list(),
            "agent_position": list(self.agent.position),
            "destination": list(self.agent.destination),
            "start": list(self.world.start),
            "agent_state": self.agent.state,
            "mode": self.agent.mode,
            "direction": self.agent.direction,
            "route": [list(p) for p in self.agent.route],
            "explored_cells": self.agent.beliefs.get_explored_cells_as_list(),
            "observations": observations,
            "homeostasis": self.agent.get_homeostasis(),
            "metrics": self.agent.get_metrics(),
            "logs": self.agent.logs[-20:],
            "speed_mode": self.speed_mode,
            "speed_ms": self.speed_ms,
            "map_id": self.current_map_id,
            "map_rows": self.world.rows,
            "map_cols": self.world.cols,
            "is_paused": self.is_paused,
            "cycle": self.cycle_count,
            "total_time": round(self.total_time, 1),
            "scenarios": SCENARIO_DESCRIPTIONS,
        }

    def get_scenarios(self) -> Dict:
        """Devuelve las descripciones de todos los escenarios disponibles."""
        return SCENARIO_DESCRIPTIONS
