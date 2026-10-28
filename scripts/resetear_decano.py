"""
Genera una contraseña temporal nueva para la cuenta de decano.

Uso:
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/resetear_decano.py

La contraseña se muestra una sola vez en la consola. No se escribe en logs
ni en la base de datos en texto plano.
"""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from infraestructura.database import inicializar_db, get_session
from infraestructura.seguridad import generar_password_temporal, hashear_password
from core.models import Usuario


def resetear():
    print("\n" + "=" * 60)
    print(" RESETEAR CONTRASEÑA DEL DECANO")
    print("=" * 60 + "\n")

    inicializar_db()
    session = get_session()

    try:
        decano = session.query(Usuario).filter_by(rol="decano").order_by(Usuario.id).first()

        password_temporal = generar_password_temporal()

        if not decano:
            print("⚠️  No existe una cuenta de decano. Creando...")
            decano = Usuario(
                username="Admin",
                password_hash=hashear_password(password_temporal),
                debe_cambiar_password=True,
                password_actualizada=datetime.now(),
                rol="decano",
                nombre="Decano (Administrador)",
                activo=True,
            )
            session.add(decano)
            session.commit()
            print("✅ Usuario decano creado.")
        else:
            decano.password_hash = hashear_password(password_temporal)
            decano.debe_cambiar_password = True
            decano.password_actualizada = datetime.now()
            session.commit()
            print("✅ Contraseña del decano reseteada.")

        print("\n" + "=" * 60)
        print(f"  Usuario:    {decano.username}")
        print(f"  Contraseña: {password_temporal}")
        print("  Cambio obligatorio en el primer inicio de sesión.")
        print("=" * 60 + "\n")

    except Exception as e:
        session.rollback()
        print(f"\n❌ Error: {e}\n")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    resetear()
