"""
Resetea la contraseña del decano a una conocida.
Ejecutar: python resetear_decano.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from werkzeug.security import generate_password_hash
from infraestructura.database import inicializar_db, get_session
from core.models import Usuario


NUEVA_PASSWORD = "pacha2026"  # ← Cambia esto si quieres otra


def resetear():
    print("\n" + "=" * 60)
    print(" RESETEAR CONTRASEÑA DEL DECANO")
    print("=" * 60 + "\n")

    inicializar_db()
    session = get_session()

    try:
        decano = session.query(Usuario).filter_by(username="decano", rol="decano").first()

        if not decano:
            print("⚠️  No existe el usuario 'decano'. Creando...")
            decano = Usuario(
                username="decano",
                password_hash=generate_password_hash(NUEVA_PASSWORD),
                rol="decano",
                nombre="Decano (Administrador)",
            )
            session.add(decano)
            session.commit()
            print(f"✅ Usuario decano creado con contraseña: {NUEVA_PASSWORD}")
        else:
            decano.password_hash = generate_password_hash(NUEVA_PASSWORD)
            session.commit()
            print(f"✅ Contraseña del decano reseteada a: {NUEVA_PASSWORD}")

        print("\n" + "=" * 60)
        print(f"  Usuario:    decano")
        print(f"  Contraseña: {NUEVA_PASSWORD}")
        print("=" * 60 + "\n")

    except Exception as e:
        session.rollback()
        print(f"\n❌ Error: {e}\n")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    resetear()