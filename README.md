# autonomous-vehicle-active-inference-simulator
Interactive autonomous vehicle simulator using Active Inference, FastAPI, WebSockets, and a visual decision-making interface.

Para ejecutar el proyecto hacer lo siguiente:

python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn backend.main:app --reload --port 8000
