"""
Resetea la contraseña del decano a una conocida.
Ejecutar: python resetear_decano.py
"""
import sys
import os

# Esto le dice a Python que suba un nivel desde 'scripts/' hasta la raíz del proyecto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) 

from werkzeug.security import generate_password_hash
from infraestructura.database import inicializar_db, get_session
from core.models import Usuario


NUEVA_PASSWORD = "123"  # 👈 Contraseña exacta solicitada


def resetear():
    print("\n" + "=" * 60)
    print(" RESETEAR CONTRASEÑA DEL DECANO")
    print("=" * 60 + "\n")

    inicializar_db()
    session = get_session()

    try:
        # Buscamos al usuario decano (por username 'admin' o rol 'decano')
        decano = session.query(Usuario).filter(Usuario.username == "admin").first()

        if not decano:
            print("⚠️  No existe el usuario 'admin'. Creando...")
            decano = Usuario(
                username="admin", # Usuario para iniciar sesión
                password_hash=generate_password_hash(NUEVA_PASSWORD),
                rol="decano",     # Le ponemos el rol 'decano' para que el login lo reconozca
                nombre="Decano (Administrador)",
            )
            session.add(decano)
            session.commit()
            print(f"✅ Usuario admin creado con contraseña: {NUEVA_PASSWORD}")
        else:
            decano.password_hash = generate_password_hash(NUEVA_PASSWORD)
            # Por si acaso estaba con el rol 'admin' viejo, lo corregimos a 'decano'
            if decano.rol == "admin":
                decano.rol = "decano" 
            session.commit()
            print(f"✅ Contraseña del usuario admin reseteada a: {NUEVA_PASSWORD}")

        print("\n" + "=" * 60)
        print(f"  Usuario:    {decano.username}")
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