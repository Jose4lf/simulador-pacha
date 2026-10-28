"""
Rota las contraseñas de TODAS las cuentas a claves temporales aleatorias.

Uso:
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/rotar_credenciales.py --confirmar

Seguridad:
- No imprime contraseñas en consola ni en logs.
- Escribe un archivo local FUERA del repositorio con las credenciales.
- Marca debe_cambiar_password=True en todas las cuentas rotadas.
- Ordena la escritura del archivo antes del commit: si el commit falla,
  el archivo se elimina para no dejar claves que no funcionan.
"""
import argparse
import os
import sys
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from core.models import Usuario
from infraestructura.database import get_db_info, get_session
from infraestructura.seguridad import (
    generar_password_temporal, hashear_password, verificar_password,
)

# Por defecto, la carpeta hermana de respaldos. Se puede sobreescribir.
DIR_POR_DEFECTO = os.path.join(
    os.path.dirname(BASE_DIR),
    os.path.basename(BASE_DIR) + "_BACKUPS",
)


def _ruta_segura(directorio):
    """Rechaza escribir credenciales dentro del repositorio."""
    destino = os.path.abspath(directorio)
    if destino == BASE_DIR or destino.startswith(BASE_DIR + os.sep):
        raise SystemExit(
            "❌ El archivo de credenciales no puede quedar dentro del repositorio."
        )
    os.makedirs(destino, exist_ok=True)
    return destino


def _restringir_permisos(ruta):
    """Mejor esfuerzo: limita el archivo al usuario actual en Windows."""
    if os.name != "nt":
        try:
            os.chmod(ruta, 0o600)
        except OSError:
            pass
        return
    usuario = os.environ.get("USERNAME")
    if not usuario:
        return
    try:
        import subprocess

        subprocess.run(
            [
                "icacls", ruta, "/inheritance:r",
                "/grant:r", f"{usuario}:(F)",
                "/grant:r", "*S-1-5-18:(F)",
                "/grant:r", "*S-1-5-32-544:(F)",
            ],
            check=False,
            capture_output=True,
            timeout=20,
        )
    except Exception:
        # Un fallo de ACL no debe romper la rotación ya confirmada.
        pass


def _escribir_credenciales(directorio, filas):
    nombre = f"credenciales_rotadas_{datetime.now():%Y%m%d_%H%M%S}.txt"
    ruta = os.path.join(directorio, nombre)

    cabecera = (
        "PACHA - CREDENCIALES TEMPORALES\n"
        f"Generado: {datetime.now():%Y-%m-%d %H:%M:%S}\n"
        "Uso: entregar a cada persona. Cambio obligatorio al primer ingreso.\n"
        "Elimina este archivo después de distribuirlo.\n"
        "\n"
        "usuario\trol\tnombre\tcontrasena\n"
    )
    contenido = cabecera + "".join(
        f"{f['usuario']}\t{f['rol']}\t{f['nombre'] or ''}\t{f['password']}\n"
        for f in filas
    )

    # O_EXCL evita sobrescribir un archivo existente con claves válidas.
    descriptor = os.open(ruta, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as archivo:
            archivo.write(contenido)
    except Exception:
        try:
            os.remove(ruta)
        except OSError:
            pass
        raise
    _restringir_permisos(ruta)
    return ruta


def rotar(directorio):
    info = get_db_info()
    print(f"Motor activo: {info['motor']} (fallback={info['es_fallback']})")

    session = get_session()
    ruta = None
    try:
        usuarios = session.query(Usuario).order_by(Usuario.rol, Usuario.username).all()
        if not usuarios:
            raise SystemExit("❌ No hay cuentas para rotar.")

        filas = []
        for usuario in usuarios:
            password = generar_password_temporal()
            usuario.password_hash = hashear_password(password)
            usuario.debe_cambiar_password = True
            usuario.password_actualizada = datetime.now()

            # Verificación en memoria antes de escribir o confirmar.
            if not verificar_password(usuario.password_hash, password):
                raise SystemExit("❌ Error interno al generar el hash; no se guardó nada.")

            filas.append({
                "usuario": usuario.username,
                "rol": usuario.rol,
                "nombre": usuario.nombre,
                "password": password,
            })

        ruta = _escribir_credenciales(directorio, filas)
        session.commit()

        # Confirmación posterior al commit usando una sesión limpia.
        for fila in filas:
            guardado = session.query(Usuario).filter_by(username=fila["usuario"]).first()
            if not guardado or not verificar_password(guardado.password_hash, fila["password"]):
                raise SystemExit(
                    f"❌ La verificación posterior falló para {fila['usuario']}."
                )

        print(f"✅ Cuentas rotadas: {len(filas)}")
        print(f"📄 Credenciales: {ruta}")
        print("   El archivo está fuera del repositorio y no se registró en consola.")
        return ruta
    except Exception:
        session.rollback()
        if ruta and os.path.exists(ruta):
            try:
                os.remove(ruta)
            except OSError:
                pass
        raise
    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(description="Rota contraseñas de todas las cuentas.")
    parser.add_argument(
        "--confirmar",
        action="store_true",
        help="Confirma la rotación. Sin esta bandera no se hace nada.",
    )
    parser.add_argument(
        "--directorio",
        default=os.environ.get("PACHA_DIR_CREDENCIALES", DIR_POR_DEFECTO),
        help="Carpeta destino del archivo de credenciales (fuera del repositorio).",
    )
    args = parser.parse_args()

    if not args.confirmar:
        print("Sin cambios. Ejecuta con --confirmar para rotar las contraseñas.")
        return 1

    rotar(_ruta_segura(args.directorio))
    return 0


if __name__ == "__main__":
    sys.exit(main())
