"""
Inicializa el sistema PACHA:
1. Crea todas las tablas.
2. Crea el usuario Administrador (Admin / 321).
3. Carga los simuladores base (Markestrated).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from infraestructura.database import inicializar_db, get_session, get_db_actual
from core.models import Usuario, Simulador
from werkzeug.security import generate_password_hash


def inicializar():
    print("\n" + "=" * 60)
    print(" INICIALIZACIÓN COMPLETA DEL SISTEMA PACHA")
    print("=" * 60)

    # 1. Crear tablas
    inicializar_db()
    db_actual = get_db_actual()
    print(f"📊 Motor de BD en uso: {db_actual.upper()}\n")

    session = get_session()

    try:
        # =========================================================
        # PASO 1: CREAR / VERIFICAR USUARIO ADMINISTRADOR
        # =========================================================
        admin_existente = session.query(Usuario).filter_by(
            username="Admin",
            rol="decano"
        ).first()

        if not admin_existente:
            password_admin = "321"
            admin = Usuario(
                username="Admin",
                password_hash=generate_password_hash(password_admin),
                rol="decano",
                nombre="Administrador General",
                activo=True
            )
            session.add(admin)
            session.commit()
            print("╔" + "═" * 58 + "╗")
            print("║" + "  ✅ USUARIO ADMIN CREADO".ljust(58) + "║")
            print("║" + "  Usuario:    Admin".ljust(58) + "║")
            print("║" + f"  Contraseña: {password_admin}".ljust(58) + "║")
            print("╚" + "═" * 58 + "╝\n")
        else:
            print("ℹ️  El usuario Admin ya existe.\n")

        # =========================================================
        # PASO 2: CARGAR SIMULADORES
        # =========================================================
        print("📦 Verificando simuladores base...")
        
        # Verificamos si Markestrated ya existe
        markestrated = session.query(Simulador).filter_by(codigo="markestrated").first()
        
        if not markestrated:
            # Creamos el simulador base
            nuevo_simulador = Simulador(
                codigo="markestrated",
                nombre="Markestrated - Estrategia de Marketing",
                descripcion="Simulador de marketing estratégico con 5 segmentos y 3 canales.",
                estado="activo",
                orden=1
            )
            session.add(nuevo_simulador)
            session.commit()
            print("✅ Simulador 'Markestrated' cargado exitosamente.")
        else:
            print("ℹ️  El simulador 'Markestrated' ya está registrado.")

        # (Si tuvieras más simuladores, los agregarías aquí de la misma forma)

        print("\n" + "=" * 60)
        print(" ✅ INICIALIZACIÓN FINALIZADA CON ÉXITO")
        print("=" * 60 + "\n")

    except Exception as e:
        session.rollback()
        print(f"\n❌ ERROR: {e}\n")
        raise

    finally:
        session.close()


if __name__ == "__main__":
    inicializar()