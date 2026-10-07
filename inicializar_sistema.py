"""
Inicializa el sistema PACHA:
- Crea el usuario DECANO (único dato hardcodeado)
- Crea 3 profesores de prueba (con simulador Markestrated)
"""
import os
import sys
import secrets
import string

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from infraestructura.database import inicializar_db, get_session, get_db_actual
from core.models import Usuario, Simulador, AsignacionSimulador
from werkzeug.security import generate_password_hash


def generar_password_segura(longitud=12):
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(longitud))


def inicializar():
    print("\n" + "=" * 60)
    print(" INICIALIZACIÓN DEL SISTEMA PACHA")
    print("=" * 60)

    inicializar_db()
    db_actual = get_db_actual()
    print(f"📊 Motor de BD en uso: {db_actual.upper()}\n")

    session = get_session()

    try:
        # =========================================================
        # 1. CREAR / VERIFICAR USUARIO DECANO
        # =========================================================
        decano_existente = session.query(Usuario).filter_by(
            username="decano",
            rol="decano"
        ).first()

        if not decano_existente:
            password_decano = generar_password_segura(12)

            decano = Usuario(
                username="decano",
                password_hash=generate_password_hash(password_decano),
                rol="decano",
                nombre="Decano (Administrador)",
            )

            session.add(decano)
            session.commit()

            print("╔" + "═" * 58 + "╗")
            print("║" + "  ✅ USUARIO DECANO CREADO".ljust(58) + "║")
            print("╠" + "═" * 58 + "╣")
            print("║" + "  Usuario:    decano".ljust(58) + "║")
            print("║" + f"  Contraseña: {password_decano}".ljust(58) + "║")
            print("║" + "  ⚠️  GUARDA ESTA CONTRASEÑA.".ljust(58) + "║")
            print("╚" + "═" * 58 + "╝\n")
        else:
            print("ℹ️  El usuario decano ya existe.\n")

        # =========================================================
        # 2. OBTENER SIMULADOR MARKESTRATED
        # =========================================================
        markestrated = session.query(Simulador).filter_by(
            codigo="markestrated"
        ).first()

        if not markestrated:
            print("⚠️  No se encontró el simulador 'markestrated'.")
            print("    Los profesores serán creados, pero no se asignará simulador.\n")

        # =========================================================
        # 3. CREAR / VERIFICAR PROFESORES
        # =========================================================
        profesores_prueba = [
            {"username": "profesor1", "nombre": "Diego Curiel"},
            {"username": "profesor2", "nombre": "María López"},
            {"username": "profesor3", "nombre": "Carlos Rojas"},
        ]

        for datos in profesores_prueba:

            # -----------------------------------------------------
            # Buscar si el profesor ya existe
            # -----------------------------------------------------
            profe = session.query(Usuario).filter_by(
                username=datos["username"]
            ).first()

            if profe:
                print(f"ℹ️  Profesor '{datos['username']}' ya existe")
            else:
                password = "profesor123"

                profe = Usuario(
                    username=datos["username"],
                    password_hash=generate_password_hash(password),
                    rol="profesor",
                    nombre=datos["nombre"],
                    activo=True,
                    bloqueado=False,
                )

                session.add(profe)
                session.commit()
                session.refresh(profe)

                print(
                    f"✅ Profesor '{datos['username']}' creado "
                    f"(pass: {password})"
                )

            # -----------------------------------------------------
            # Asignar Markestrated SOLO si no existe la asignación
            # -----------------------------------------------------
            if markestrated:

                asignacion_existente = session.query(
                    AsignacionSimulador
                ).filter_by(
                    usuario_id=profe.id,
                    simulador_id=markestrated.id
                ).first()

                if asignacion_existente:
                    print(
                        f"   ℹ️  Markestrated ya está asignado a "
                        f"'{profe.username}'"
                    )
                else:
                    asig = AsignacionSimulador(
                        usuario_id=profe.id,
                        simulador_id=markestrated.id
                    )

                    session.add(asig)
                    session.commit()

                    print(
                        f"   ✅ Markestrated asignado a "
                        f"'{profe.username}'"
                    )

        print("\n" + "=" * 60)
        print(" ✅ INICIALIZACIÓN FINALIZADA")
        print("=" * 60 + "\n")

    except Exception as e:
        session.rollback()
        print(f"\n❌ ERROR: {e}\n")
        raise

    finally:
        session.close()


if __name__ == "__main__":
    inicializar()