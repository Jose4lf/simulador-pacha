from datetime import datetime

from flask import (
    Blueprint, flash, redirect, render_template, request, session, url_for,
)

from core.models import Usuario
from infraestructura.database import get_session
from infraestructura.seguridad import (
    generar_csrf_token, hashear_password, limpiar_intentos_login, login_bloqueado,
    registrar_fallo_login, segundos_para_desbloqueo, validar_password,
    verificar_password,
)

auth_bp = Blueprint(
    "auth",
    __name__,
    template_folder="../../templates/auth"
)

_ROLES_VALIDOS = {"alumno", "profesor", "decano"}


@auth_bp.route("/")
def index():
    if session.get("usuario_id") and not session.get("debe_cambiar_password"):
        rol = session.get("rol")
        if rol in _ROLES_VALIDOS:
            return redirect(url_for(f"{rol}.panel"))
    return render_template("auth/login.html", rol_activo="alumno")


@auth_bp.route("/login", methods=["POST"])
def login():
    usuario = request.form.get("usuario", "").strip()
    password = request.form.get("password", "")
    rol = request.form.get("rol", "alumno")
    ip = request.remote_addr or "desconocida"

    if rol not in _ROLES_VALIDOS:
        rol = "alumno"

    if login_bloqueado(usuario, ip):
        minutos = max(1, segundos_para_desbloqueo(usuario, ip) // 60)
        return render_template(
            "auth/login.html",
            error=f"Demasiados intentos fallidos. Espera {minutos} minuto(s).",
            rol_activo=rol,
        ), 429

    db = get_session()
    try:
        user = db.query(Usuario).filter_by(username=usuario).first()

        credenciales_ok = bool(
            user
            and verificar_password(user.password_hash, password)
            and user.rol == rol
            and user.activo
            and not user.bloqueado
        )

        if not credenciales_ok:
            registrar_fallo_login(usuario, ip)
            return render_template(
                "auth/login.html",
                error="Credenciales incorrectas",
                rol_activo=rol,
            )

        # Migración transparente de hashes legados en texto plano.
        if user.password_hash and not str(user.password_hash).startswith(
            ("scrypt:", "pbkdf2:", "argon2")
        ):
            user.password_hash = hashear_password(password)
            db.commit()

        datos = {
            "id": user.id,
            "username": user.username,
            "rol": user.rol,
            "nombre": user.nombre,
            "debe_cambiar": bool(user.debe_cambiar_password),
        }
    finally:
        db.close()

    limpiar_intentos_login(usuario, ip)

    # Evita fijación de sesión: se descarta cualquier estado previo.
    session.clear()
    session.permanent = True
    session["usuario_id"] = datos["id"]
    session["usuario"] = datos["username"]
    session["rol"] = datos["rol"]
    session["nombre"] = datos["nombre"]
    session["debe_cambiar_password"] = datos["debe_cambiar"]
    session["csrf_token"] = generar_csrf_token()

    if datos["debe_cambiar"]:
        return redirect(url_for("auth.cambiar_password"))

    return redirect(url_for(f"{datos['rol']}.panel"))


@auth_bp.route("/cambiar-password", methods=["GET", "POST"])
def cambiar_password():
    if "usuario_id" not in session:
        return redirect(url_for("auth.index"))

    error = None
    if request.method == "POST":
        actual = request.form.get("actual", "")
        nueva = request.form.get("nueva", "")
        confirmar = request.form.get("confirmar", "")

        if not actual or not nueva or not confirmar:
            error = "Completa los tres campos."
        elif nueva != confirmar:
            error = "La nueva contraseña y su confirmación no coinciden."
        else:
            db = get_session()
            try:
                user = db.query(Usuario).filter_by(id=session["usuario_id"]).first()
                if not user:
                    session.clear()
                    return redirect(url_for("auth.index"))

                if not verificar_password(user.password_hash, actual):
                    error = "La contraseña actual no es correcta."
                elif verificar_password(user.password_hash, nueva):
                    error = "La nueva contraseña debe ser distinta de la actual."
                else:
                    ok, mensaje = validar_password(nueva, user.username)
                    if not ok:
                        error = mensaje
                    else:
                        user.password_hash = hashear_password(nueva)
                        user.debe_cambiar_password = False
                        user.password_actualizada = datetime.now()
                        db.commit()

                        session.clear()
                        flash("Contraseña actualizada. Inicia sesión de nuevo.", "exito")
                        return redirect(url_for("auth.index"))
            finally:
                db.close()

    return render_template(
        "auth/cambiar_password.html",
        error=error,
        nombre=session.get("nombre"),
        obligatorio=bool(session.get("debe_cambiar_password")),
    )


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.index"))
