from flask import Blueprint, render_template, request, redirect, url_for, session
from werkzeug.security import check_password_hash
from infraestructura.repositorio import UsuarioRepo

auth_bp = Blueprint(
    "auth",
    __name__,
    template_folder="../../templates/auth"
)

@auth_bp.route("/")
def index():
    return render_template("auth/login.html", rol_activo="alumno")

@auth_bp.route("/login", methods=["POST"])
def login():
    usuario = request.form.get("usuario", "").strip()
    password = request.form.get("password", "").strip()
    rol = request.form.get("rol", "alumno")

    user = UsuarioRepo.obtener_por_username(usuario)

    if user and check_password_hash(user.password_hash, password) and user.rol == rol:
        session["usuario_id"] = user.id          # ← ✅ LÍNEA AGREGADA
        session["usuario"] = user.username
        session["rol"] = user.rol
        session["nombre"] = user.nombre
        return redirect(url_for(f"{rol}.panel"))
    else:
        return render_template(
            "auth/login.html",
            error="Credenciales incorrectas",
            rol_activo=rol
        )

@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.index"))