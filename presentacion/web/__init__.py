from flask import (
    Flask, flash, jsonify, redirect, render_template, request, session, url_for
)
from werkzeug.middleware.proxy_fix import ProxyFix

from config import Config
from infraestructura.database import close_session, get_db_info, get_session
from infraestructura.seguridad import (
    generar_csrf_token, tokens_iguales,
)

# Rutas que no requieren sesión iniciada.
_RUTAS_PUBLICAS = {"static", "health", "auth.index", "auth.login"}
# Rutas permitidas aunque el usuario deba cambiar su contraseña.
_RUTAS_SIN_BLOQUEO_PASSWORD = {"auth.cambiar_password", "auth.logout"}


def create_app(config_class=Config):
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static"
    )
    app.config.from_object(config_class)

    # Detrás de un proxy inverso (Render, Cloudflare, nginx) se confía en las
    # cabeceras X-Forwarded-* para recuperar la IP real y el esquema https.
    app.wsgi_app = ProxyFix(
        app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1
    )

    if app.config.get("ES_PRODUCCION") and app.config.get("SECRET_KEY") == "pacha_2026_secret":
        raise RuntimeError(
            "SECRET_KEY insegura en producción. Define SECRET_KEY en el entorno."
        )

    # ============================================
    # REGISTRO DE BLUEPRINTS
    # ============================================

    # Auth (login/logout) - sin prefijo
    from presentacion.web.blueprints.auth.routes import auth_bp
    app.register_blueprint(auth_bp)

    # Alumno - con prefijo /alumno
    from presentacion.web.blueprints.alumno.routes import alumno_bp
    app.register_blueprint(alumno_bp, url_prefix="/alumno")

    # Profesor - con prefijo /profesor
    from presentacion.web.blueprints.profesor.routes import profesor_bp
    app.register_blueprint(profesor_bp, url_prefix="/profesor")

    # Decano - con prefijo /decano
    from presentacion.web.blueprints.decano.routes import decano_bp
    app.register_blueprint(decano_bp, url_prefix="/decano")

    # ============================================
    # CSRF Y SESIÓN
    # ============================================
    @app.context_processor
    def _inyectar_contexto():
        if "csrf_token" not in session:
            session["csrf_token"] = generar_csrf_token()
        return {
            "db_info": get_db_info(),
            "csrf_token": session["csrf_token"],
        }

    @app.before_request
    def _proteger_csrf():
        """Exige token CSRF en toda petición que modifica estado."""
        if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
            return None

        enviado = request.form.get("csrf_token") or request.headers.get("X-CSRFToken")
        if tokens_iguales(session.get("csrf_token"), enviado):
            return None

        if request.endpoint == "auth.login":
            return render_template(
                "auth/login.html",
                error="La sesión expiró. Vuelve a intentar el ingreso.",
                rol_activo="alumno",
            ), 400

        if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"error": "Token CSRF inválido o ausente."}), 400

        return render_template("auth/error_csrf.html"), 400

    @app.before_request
    def _verificar_sesion():
        """Valida la cuenta en cada petición y fuerza el cambio de contraseña."""
        endpoint = request.endpoint
        if endpoint is None or endpoint in _RUTAS_PUBLICAS:
            return None

        usuario_id = session.get("usuario_id")
        if not usuario_id:
            session.clear()
            return redirect(url_for("auth.index"))

        # Logout no necesita consultar la BD.
        if endpoint == "auth.logout":
            return None

        from core.models import Usuario

        db = get_session()
        try:
            user = db.query(Usuario).filter_by(id=usuario_id).first()
            if not user:
                session.clear()
                flash("La sesión ya no es válida.", "error")
                return redirect(url_for("auth.index"))

            rol = user.rol
            activo = bool(user.activo)
            bloqueado = bool(user.bloqueado)
            debe_cambiar = bool(user.debe_cambiar_password)
        except Exception:
            session.clear()
            return "Base de datos no disponible.", 503
        finally:
            db.close()

        if not activo or bloqueado:
            session.clear()
            flash("Tu cuenta está deshabilitada o bloqueada.", "error")
            return redirect(url_for("auth.index"))

        session["rol"] = rol
        session["debe_cambiar_password"] = debe_cambiar

        if debe_cambiar and endpoint not in _RUTAS_SIN_BLOQUEO_PASSWORD:
            return redirect(url_for("auth.cambiar_password"))

        return None

    @app.teardown_appcontext
    def _cerrar_sesion_db(exception=None):
        close_session()

    @app.route("/health")
    def health():
        """Estado básico del servicio. No expone credenciales."""
        info = get_db_info()
        return jsonify({
            "ok": info["inicializada"],
            "motor": info["motor"].lower(),
            "fallback": info["es_fallback"],
        })

    return app
