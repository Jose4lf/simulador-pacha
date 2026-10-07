"""
Repositorios - PACHA (esquema normalizado)
Solo lo esencial. Se ampliará en bloques siguientes.
"""
from infraestructura.database import get_session
from core.models import (
    Usuario, Simulador, AsignacionSimulador, Configuracion,
    Industria, Equipo, Segmento, Canal, Marca,
    EstudioMercado, Decision, Reporte
)


# ============================================================
# USUARIOS
# ============================================================
class UsuarioRepo:
    @staticmethod
    def obtener_por_username(username):
        session = get_session()
        try:
            return session.query(Usuario).filter_by(username=username).first()
        finally:
            session.close()

    @staticmethod
    def obtener_por_id(usuario_id):
        session = get_session()
        try:
            return session.query(Usuario).filter_by(id=usuario_id).first()
        finally:
            session.close()

    @staticmethod
    def listar_todos():
        session = get_session()
        try:
            return session.query(Usuario).order_by(Usuario.id).all()
        finally:
            session.close()


# ============================================================
# SIMULADORES
# ============================================================
class SimuladorRepo:
    @staticmethod
    def listar_todos():
        session = get_session()
        try:
            return session.query(Simulador).order_by(Simulador.orden).all()
        finally:
            session.close()

    @staticmethod
    def obtener_por_codigo(codigo):
        session = get_session()
        try:
            return session.query(Simulador).filter_by(codigo=codigo).first()
        finally:
            session.close()


# ============================================================
# ESTUDIOS DE MERCADO
# ============================================================
class EstudioMercadoRepo:
    @staticmethod
    def listar_todos():
        session = get_session()
        try:
            return session.query(EstudioMercado).order_by(EstudioMercado.numero).all()
        finally:
            session.close()

    @staticmethod
    def obtener_por_numero(numero):
        session = get_session()
        try:
            return session.query(EstudioMercado).filter_by(numero=numero).first()
        finally:
            session.close()
    @staticmethod
    def listar_todos():
        session = get_session()
        try:
            return session.query(Simulador).order_by(Simulador.orden).all()
        finally:
            session.close()

    @staticmethod
    def obtener_por_codigo(codigo):
        session = get_session()
        try:
            return session.query(Simulador).filter_by(codigo=codigo).first()
        finally:
            session.close()
    @staticmethod
    def obtener_por_username(username):
        """Devuelve el usuario por username."""
        session = get_session()
        try:
            return session.query(Usuario).filter_by(username=username).first()
        finally:
            session.close()

    @staticmethod
    def obtener_por_id(usuario_id):
        session = get_session()
        try:
            return session.query(Usuario).filter_by(id=usuario_id).first()
        finally:
            session.close()

    @staticmethod
    def crear(username, password_hash, rol, nombre, equipo_id=None):
        session = get_session()
        try:
            u = Usuario(
                username=username,
                password_hash=password_hash,
                rol=rol,
                nombre=nombre,
                equipo_id=equipo_id
            )
            session.add(u)
            session.commit()
            session.refresh(u)
            return u
        finally:
            session.close()

    @staticmethod
    def listar_todos():
        session = get_session()
        try:
            return session.query(Usuario).order_by(Usuario.id).all()
        finally:
            session.close()