import os
from datetime import timedelta

from dotenv import load_dotenv

# Cargar variables del .env
load_dotenv()


def _entero_env(nombre, defecto):
    try:
        return int(os.environ.get(nombre, defecto))
    except (TypeError, ValueError):
        return int(defecto)


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or "pacha_2026_secret"
    DEBUG = os.environ.get("DEBUG", "true").lower() == "true"
    ES_PRODUCCION = os.environ.get("FLASK_ENV", "development").lower() == "production"

    # Base de datos
    DATABASE_URL = os.environ.get("DATABASE_URL")
    FALLBACK_SQLITE = os.environ.get("FALLBACK_SQLITE", "true").lower() == "true"

    # Ruta fallback SQLite
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    SQLITE_FALLBACK_URL = f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'pacha_fallback.db')}"

    # Sesiones
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = os.environ.get("SESSION_COOKIE_SAMESITE", "Lax")
    SESSION_COOKIE_SECURE = os.environ.get(
        "SESSION_COOKIE_SECURE", str(ES_PRODUCCION)
    ).lower() == "true"
    PERMANENT_SESSION_LIFETIME = timedelta(
        hours=_entero_env("SESSION_HORAS", 8)
    )
    SESSION_REFRESH_EACH_REQUEST = True

    # SQLAlchemy
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }
