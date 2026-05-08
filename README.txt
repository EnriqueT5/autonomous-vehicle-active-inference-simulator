Para ejecutar el proyecto hacer lo siguiente:

python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn backend.main:app --reload --port 8000