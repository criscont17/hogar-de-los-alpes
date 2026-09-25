FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /servicio

# Primero las dependencias: la capa se reutiliza mientras requirements.txt no cambie.
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app

RUN useradd --create-home --uid 10001 wallet
USER wallet

EXPOSE 8000

# WalletBC no tiene una ruta de listado: se comprueba que la API responda.
HEALTHCHECK --interval=10s --timeout=5s --start-period=20s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/openapi.json', timeout=4)"

CMD ["uvicorn", "app.infraestructura.adaptadores.entrada.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
