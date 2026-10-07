import os
from dotenv import load_dotenv

# Cargar variables del .env
load_dotenv()

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "pacha_2026_secret")
    DEBUG = os.environ.get("DEBUG", "true").lower() == "true"

    # Base de datos
    DATABASE_URL = os.environ.get("DATABASE_URL")
    FALLBACK_SQLITE = os.environ.get("FALLBACK_SQLITE", "true").lower() == "true"

    # Ruta fallback SQLite
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    SQLITE_FALLBACK_URL = f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'pacha_fallback.db')}"

    # SQLAlchemy
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }