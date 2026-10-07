"""
Conexión a base de datos con fallback automático:
1. Intenta PostgreSQL (DATABASE_URL)
2. Si falla → SQLite local (FALLBACK_SQLITE)
"""
import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, scoped_session
from core.models import Base
from config import Config

# Variables globales
engine = None
SessionLocal = None
DB_ACTUAL = None  # "postgresql" o "sqlite"


def _intentar_postgresql():
    """Intenta conectar a PostgreSQL."""
    if not Config.DATABASE_URL:
        return None, "No hay DATABASE_URL definida"

    try:
        eng = create_engine(
            Config.DATABASE_URL,
            echo=False,
            pool_pre_ping=True,
            pool_recycle=300,
            pool_size=10,
            max_overflow=20,
        )
        # Test de conexión
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        return eng, None
    except Exception as e:
        return None, str(e)


def _crear_sqlite_fallback():
    """Crea engine SQLite de fallback."""
    # Asegurar carpeta instance
    INSTANCE_DIR = os.path.join(Config.BASE_DIR, "instance")
    os.makedirs(INSTANCE_DIR, exist_ok=True)

    eng = create_engine(
        Config.SQLITE_FALLBACK_URL,
        echo=False,
        connect_args={"check_same_thread": False}
    )
    return eng


def inicializar_db():
    """Inicializa la conexión a BD con fallback."""
    global engine, SessionLocal, DB_ACTUAL

    print("\n" + "=" * 60)
    print(" INICIALIZANDO BASE DE DATOS")
    print("=" * 60)

    # 1. Intentar PostgreSQL
    print("🔌 Intentando conectar a PostgreSQL...")
    eng_pg, error_pg = _intentar_postgresql()

    if eng_pg:
        engine = eng_pg
        DB_ACTUAL = "postgresql"
        print("✅ Conectado a PostgreSQL")
        print(f"   URL: {Config.DATABASE_URL}")
    else:
        print(f"⚠️  PostgreSQL no disponible: {error_pg}")

        # 2. Fallback SQLite
        if Config.FALLBACK_SQLITE:
            print("🔄 Usando fallback SQLite...")
            engine = _crear_sqlite_fallback()
            DB_ACTUAL = "sqlite"
            print(f"✅ SQLite activado: {Config.SQLITE_FALLBACK_URL}")
        else:
            print("❌ No hay BD disponible y fallback deshabilitado")
            sys.exit(1)

    # 3. Crear sesión
    SessionLocal = scoped_session(sessionmaker(bind=engine, autoflush=False, autocommit=False))

    # 4. Crear tablas
    print("📋 Creando tablas (si no existen)...")
    Base.metadata.create_all(engine)
    print(f"✅ Tablas verificadas en {DB_ACTUAL}")

    print("=" * 60 + "\n")


def init_db():
    """Compatibilidad con código antiguo."""
    if engine is None:
        inicializar_db()


def get_session():
    """Devuelve una sesión de base de datos."""
    if SessionLocal is None:
        inicializar_db()
    return SessionLocal()


def close_session():
    """Cierra la sesión actual."""
    if SessionLocal:
        SessionLocal.remove()


def get_db_actual():
    """Devuelve el motor de BD en uso."""
    return DB_ACTUAL