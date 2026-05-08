"""
main.py — Servidor FastAPI para la simulación de Active Inference.

Responsabilidades:
- Inicialización del servidor FastAPI
- Endpoints REST para control de simulación
- WebSocket para comunicación en tiempo real
- Servir archivos estáticos del frontend
- Gestión de CORS
"""

import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from backend.simulation import Simulation
from backend.schemas import (
    EditCellRequest, SetPointRequest, ChangeMapRequest, SpeedChangeRequest
)

# ============================================================
# INICIALIZACIÓN
# ============================================================

app = FastAPI(
    title="Active Inference — Simulación de Vehículo Autónomo",
    description="Simulador cognitivo interactivo de un vehículo autónomo "
                "usando conceptos de Active Inference, percepción parcial "
                "y navegación bajo incertidumbre.",
    version="1.0.0",
)

# CORS para desarrollo local
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instancia global de la simulación
simulation = Simulation()

# Ruta al frontend
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"


# ============================================================
# SERVIR FRONTEND
# ============================================================

@app.get("/")
async def serve_index():
    """Sirve la página principal del frontend."""
    return FileResponse(FRONTEND_DIR / "index.html")


# Montar archivos estáticos
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


# ============================================================
# ENDPOINTS REST
# ============================================================

@app.get("/api/state")
async def get_state():
    """Obtiene el estado completo de la simulación."""
    return JSONResponse(content=simulation.get_full_state())


@app.get("/api/scenarios")
async def get_scenarios():
    """Obtiene las descripciones de los escenarios disponibles."""
    return JSONResponse(content=simulation.get_scenarios())


@app.post("/api/step")
async def execute_step():
    """Ejecuta un paso de la simulación (modo paso a paso)."""
    result = simulation.step()
    return JSONResponse(content=result)


@app.post("/api/start")
async def start_simulation():
    """Inicia la simulación automática."""
    simulation.start()
    return JSONResponse(content={"status": "started"})


@app.post("/api/pause")
async def pause_simulation():
    """Pausa la simulación."""
    simulation.pause()
    return JSONResponse(content={"status": "paused"})


@app.post("/api/resume")
async def resume_simulation():
    """Reanuda la simulación."""
    simulation.resume()
    return JSONResponse(content={"status": "resumed"})


@app.post("/api/reset")
async def reset_simulation():
    """Reinicia la simulación con el mapa actual."""
    result = simulation.change_map(simulation.current_map_id)
    return JSONResponse(content=result)


@app.post("/api/speed")
async def change_speed(request: SpeedChangeRequest):
    """Cambia la velocidad de la simulación."""
    ms = simulation.set_speed(request.speed)
    return JSONResponse(content={"speed_mode": request.speed, "speed_ms": ms})


@app.post("/api/map")
async def change_map(request: ChangeMapRequest):
    """Cambia a un mapa/escenario diferente."""
    result = simulation.change_map(request.map_id)
    return JSONResponse(content=result)


@app.post("/api/random-map")
async def random_map():
    """Genera un mapa aleatorio."""
    result = simulation.generate_random_map()
    return JSONResponse(content=result)


@app.post("/api/edit-cell")
async def edit_cell(request: EditCellRequest):
    """Edita una celda del mapa."""
    success = simulation.edit_cell(request.row, request.col, request.cell_type)
    return JSONResponse(content={"success": success})


@app.post("/api/set-destination")
async def set_destination(request: SetPointRequest):
    """Establece un nuevo destino B."""
    success = simulation.set_destination(request.row, request.col)
    if not success:
        return JSONResponse(
            content={"success": False, "message": "Destino no disponible. Seleccione otra celda válida."},
            status_code=400,
        )
    return JSONResponse(content={"success": True})


@app.post("/api/set-start")
async def set_start(request: SetPointRequest):
    """Establece un nuevo punto de inicio A."""
    success = simulation.set_start(request.row, request.col)
    if not success:
        return JSONResponse(
            content={"success": False, "message": "Punto de inicio no válido."},
            status_code=400,
        )
    return JSONResponse(content={"success": True})


# ============================================================
# WEBSOCKET — Comunicación en tiempo real
# ============================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket para comunicación en tiempo real con el frontend.
    
    Envía el estado actualizado del agente cada ciclo de decisión.
    Recibe comandos de control del frontend.
    """
    await websocket.accept()
    
    # Enviar estado inicial
    state = simulation.get_full_state()
    await websocket.send_json(state)
    
    try:
        while True:
            # Verificar si hay mensajes del frontend (no bloqueante)
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(), timeout=0.05
                )
                await _handle_ws_message(websocket, data)
            except asyncio.TimeoutError:
                pass
            
            # Si la simulación está corriendo y no pausada, ejecutar paso
            if simulation.is_running and not simulation.is_paused:
                result = simulation.step()
                await websocket.send_json(result)
                
                # Esperar según la velocidad configurada
                wait_time = simulation.speed_ms / 1000.0
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
            else:
                # Cuando está pausada, solo esperar un poco
                await asyncio.sleep(0.1)
    
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WebSocket error: {e}")


async def _handle_ws_message(websocket: WebSocket, data: str):
    """
    Procesa mensajes recibidos del frontend vía WebSocket.
    
    Comandos soportados:
    - start, pause, resume, reset
    - step (ejecutar un paso)
    - speed (cambiar velocidad)
    - map (cambiar mapa)
    - edit_cell (editar celda)
    - set_destination (cambiar destino)
    - set_start (cambiar inicio)
    - random_map (generar mapa aleatorio)
    """
    try:
        msg = json.loads(data)
        cmd = msg.get("command", "")
        
        if cmd == "start":
            simulation.start()
            await websocket.send_json({"status": "started"})
        
        elif cmd == "pause":
            simulation.pause()
            await websocket.send_json({"status": "paused"})
        
        elif cmd == "resume":
            simulation.resume()
            await websocket.send_json({"status": "resumed"})
        
        elif cmd == "reset":
            result = simulation.change_map(simulation.current_map_id)
            await websocket.send_json(result)
        
        elif cmd == "step":
            result = simulation.step()
            await websocket.send_json(result)
        
        elif cmd == "speed":
            speed = msg.get("speed", "normal")
            simulation.set_speed(speed)
            state = simulation.get_full_state()
            await websocket.send_json(state)
        
        elif cmd == "map":
            map_id = msg.get("map_id", 1)
            result = simulation.change_map(map_id)
            await websocket.send_json(result)
        
        elif cmd == "edit_cell":
            row = msg.get("row", 0)
            col = msg.get("col", 0)
            cell_type = msg.get("cell_type", 0)
            simulation.edit_cell(row, col, cell_type)
            state = simulation.get_full_state()
            await websocket.send_json(state)
        
        elif cmd == "set_destination":
            row = msg.get("row", 0)
            col = msg.get("col", 0)
            success = simulation.set_destination(row, col)
            state = simulation.get_full_state()
            state["destination_set"] = success
            await websocket.send_json(state)
        
        elif cmd == "set_start":
            row = msg.get("row", 0)
            col = msg.get("col", 0)
            success = simulation.set_start(row, col)
            state = simulation.get_full_state()
            state["start_set"] = success
            await websocket.send_json(state)
        
        elif cmd == "random_map":
            result = simulation.generate_random_map()
            await websocket.send_json(result)
        
        elif cmd == "get_state":
            state = simulation.get_full_state()
            await websocket.send_json(state)
    
    except json.JSONDecodeError:
        await websocket.send_json({"error": "Invalid JSON"})
    except Exception as e:
        await websocket.send_json({"error": str(e)})


# ============================================================
# ARRANQUE
# ============================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
