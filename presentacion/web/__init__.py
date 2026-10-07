from flask import Flask
from config import Config


def create_app(config_class=Config):
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static"
    )
    app.config.from_object(config_class)

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

    return app