"""
Conexión a base de datos con fallback automático:
1. Intenta PostgreSQL (DATABASE_URL)
2. Si falla -> SQLite local (FALLBACK_SQLITE)

El motor activo se informa de forma explícita y las credenciales
se enmascaran en los mensajes de consola.
"""
import os
import sys

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import scoped_session, sessionmaker

from config import Config
from core.models import Base

# Variables globales
engine = None
SessionLocal = None
DB_ACTUAL = None          # "postgresql" o "sqlite"
DB_ES_FALLBACK = False    # True solo cuando se usa el respaldo SQLite


def enmascarar_url(url):
    """Devuelve una URL segura para logs, sin contraseña."""
    if not url:
        return "(sin URL)"
    try:
        parsed = make_url(str(url))
        if parsed.password:
            # hide_password=True evita el URL-encoding de los asteriscos.
            return parsed.render_as_string(hide_password=True)
        return parsed.render_as_string(hide_password=False)
    except Exception:
        return "(URL no válida)"


def _activar_fk_sqlite(eng):
    """Activa la integridad referencial en cada conexión SQLite."""
    @event.listens_for(eng, "connect")
    def _fk_on_connect(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()


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


def _crear_sqlite_fallback(url=None):
    """Crea engine SQLite de fallback con claves foráneas activas."""
    INSTANCE_DIR = os.path.join(Config.BASE_DIR, "instance")
    os.makedirs(INSTANCE_DIR, exist_ok=True)

    eng = create_engine(
        url or Config.SQLITE_FALLBACK_URL,
        echo=False,
        connect_args={"check_same_thread": False},
    )
    _activar_fk_sqlite(eng)
    return eng


def inicializar_db():
    """Inicializa la conexión a BD con fallback."""
    global engine, SessionLocal, DB_ACTUAL, DB_ES_FALLBACK

    print("\n" + "=" * 60)
    print(" INICIALIZANDO BASE DE DATOS")
    print("=" * 60)

    # 1. Intentar PostgreSQL
    print("🔌 Intentando conectar a PostgreSQL...")
    eng_pg, error_pg = _intentar_postgresql()

    if eng_pg:
        engine = eng_pg
        DB_ACTUAL = "postgresql"
        DB_ES_FALLBACK = False
        print("✅ Conectado a PostgreSQL")
        print(f"   URL: {enmascarar_url(Config.DATABASE_URL)}")
    else:
        print(f"⚠️  PostgreSQL no disponible: {error_pg}")

        # 2. Fallback SQLite
        if Config.FALLBACK_SQLITE:
            print("🔄 Usando fallback SQLite...")
            engine = _crear_sqlite_fallback()
            DB_ACTUAL = "sqlite"
            DB_ES_FALLBACK = True
            print("=" * 60)
            print(" ⚠️  MODO RESPALDO: SQLite")
            print(" Los datos NO son los de PostgreSQL.")
            print(f" Archivo: {Config.SQLITE_FALLBACK_URL}")
            print("=" * 60)
        else:
            print("❌ No hay BD disponible y fallback deshabilitado")
            sys.exit(1)

    # 3. Crear sesión
    SessionLocal = scoped_session(
        sessionmaker(bind=engine, autoflush=False, autocommit=False)
    )

    # 4. Crear tablas
    print("📋 Creando tablas (si no existen)...")
    Base.metadata.create_all(engine)
    print(f"✅ Tablas verificadas en {DB_ACTUAL}")
    print(f"🔎 MOTOR ACTIVO: {DB_ACTUAL.upper()}")
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
    """Cierra y libera la sesión actual."""
    if SessionLocal:
        SessionLocal.remove()


def get_db_actual():
    """Devuelve el motor de BD en uso."""
    return DB_ACTUAL


def get_db_info():
    """Información segura del motor activo, apta para plantillas y /health."""
    if DB_ACTUAL == "postgresql":
        url = enmascarar_url(Config.DATABASE_URL)
    elif DB_ACTUAL == "sqlite":
        url = Config.SQLITE_FALLBACK_URL
    else:
        url = ""

    return {
        "motor": (DB_ACTUAL or "sin_inicializar").upper(),
        "es_fallback": bool(DB_ES_FALLBACK),
        "url": url,
        "inicializada": DB_ACTUAL is not None,
    }
