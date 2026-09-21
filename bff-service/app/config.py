import os

URL_GESTION_TRABAJOS = os.getenv("URL_GESTION_TRABAJOS", "http://gestion-trabajos:8001")
URL_WALLET = os.getenv("URL_WALLET", "http://wallet:8000")
TIMEOUT_SEGUNDOS = float(os.getenv("BFF_TIMEOUT_SEGUNDOS", "10"))
