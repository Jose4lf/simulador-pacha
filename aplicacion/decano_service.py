"""
Servicio del Decano - PACHA (esquema normalizado)
"""
from werkzeug.security import generate_password_hash
from infraestructura.database import get_session
from core.models import Usuario, Simulador, AsignacionSimulador, Configuracion


class DecanoService:

    # ============================================================
    # PROFESORES
    # ============================================================
    @staticmethod
    def listar_profesores():
        session = get_session()
        try:
            profesores = session.query(Usuario).filter_by(rol="profesor").order_by(Usuario.username).all()
            resultado = []
            for p in profesores:
                asignaciones = session.query(AsignacionSimulador).filter_by(usuario_id=p.id).all()
                simuladores = []
                for a in asignaciones:
                    sim = session.query(Simulador).filter_by(id=a.simulador_id).first()
                    if sim:
                        simuladores.append({
                            "codigo": sim.codigo,
                            "nombre": sim.nombre,
                            "estado": sim.estado,
                        })
                resultado.append({
                    "id": p.id,
                    "username": p.username,
                    "nombre": p.nombre,
                    "email": p.email or "—",
                    "activo": p.activo,
                    "bloqueado": p.bloqueado,
                    "simuladores": simuladores,
                })
            return resultado
        finally:
            session.close()

    @staticmethod
    def obtener_profesor(usuario_id):
        session = get_session()
        try:
            p = session.query(Usuario).filter_by(id=usuario_id, rol="profesor").first()
            if not p:
                return None
            asignaciones = session.query(AsignacionSimulador).filter_by(usuario_id=p.id).all()
            simuladores_ids = [a.simulador_id for a in asignaciones]
            return {
                "id": p.id,
                "username": p.username,
                "nombre": p.nombre,
                "email": p.email or "",
                "activo": p.activo,
                "bloqueado": p.bloqueado,
                "simuladores_ids": simuladores_ids,
            }
        finally:
            session.close()

    @staticmethod
    def crear_profesor(username, password, nombre, email, activo=True, bloqueado=False, simuladores_ids=None):
        session = get_session()
        try:
            existente = session.query(Usuario).filter_by(username=username).first()
            if existente:
                return {"error": f"El usuario '{username}' ya existe"}

            p = Usuario(
                username=username,
                password_hash=generate_password_hash(password),
                rol="profesor",
                nombre=nombre,
                email=email,
                activo=activo,
                bloqueado=bloqueado,
            )
            session.add(p)
            session.commit()
            session.refresh(p)

            if simuladores_ids:
                for sim_id in simuladores_ids:
                    session.add(AsignacionSimulador(usuario_id=p.id, simulador_id=sim_id))
                session.commit()

            return {"ok": True, "id": p.id}
        finally:
            session.close()

    @staticmethod
    def actualizar_profesor(usuario_id, nombre=None, email=None,
                            activo=None, bloqueado=None,
                            nueva_password=None, simuladores_ids=None):
        session = get_session()
        try:
            p = session.query(Usuario).filter_by(id=usuario_id, rol="profesor").first()
            if not p:
                return {"error": "Profesor no encontrado"}

            if nombre is not None:
                p.nombre = nombre
            if email is not None:
                p.email = email
            if activo is not None:
                p.activo = activo
            if bloqueado is not None:
                p.bloqueado = bloqueado
            if nueva_password:
                p.password_hash = generate_password_hash(nueva_password)

            if simuladores_ids is not None:
                session.query(AsignacionSimulador).filter_by(usuario_id=p.id).delete()
                for sim_id in simuladores_ids:
                    session.add(AsignacionSimulador(usuario_id=p.id, simulador_id=sim_id))

            session.commit()
            return {"ok": True}
        finally:
            session.close()

    @staticmethod
    def eliminar_profesor(usuario_id):
        session = get_session()
        try:
            p = session.query(Usuario).filter_by(id=usuario_id, rol="profesor").first()
            if not p:
                return {"error": "Profesor no encontrado"}
            session.delete(p)
            session.commit()
            return {"ok": True}
        finally:
            session.close()

    # ============================================================
    # PERMISOS
    # ============================================================
    @staticmethod
    def listar_permisos():
        session = get_session()
        try:
            profesores = session.query(Usuario).filter_by(rol="profesor").order_by(Usuario.username).all()
            simuladores = session.query(Simulador).order_by(Simulador.orden).all()

            resultado = []
            for p in profesores:
                asignaciones = session.query(AsignacionSimulador).filter_by(usuario_id=p.id).all()
                ids_asignados = [a.simulador_id for a in asignaciones]
                permisos = {sim.id: sim.id in ids_asignados for sim in simuladores}
                resultado.append({
                    "profesor": {"id": p.id, "username": p.username, "nombre": p.nombre},
                    "permisos": permisos,
                })

            return {
                "profesores": resultado,
                "simuladores": [{
                    "id": s.id, "nombre": s.nombre, "codigo": s.codigo, "estado": s.estado,
                } for s in simuladores],
            }
        finally:
            session.close()

    # ============================================================
    # SIMULADORES
    # ============================================================
    @staticmethod
    def listar_simuladores():
        session = get_session()
        try:
            simuladores = session.query(Simulador).order_by(Simulador.orden).all()
            return [{
                "id": s.id, "codigo": s.codigo, "nombre": s.nombre,
                "descripcion": s.descripcion or "", "estado": s.estado,
            } for s in simuladores]
        finally:
            session.close()

    # ============================================================
    # CONTRASEÑAS
    # ============================================================
    @staticmethod
    def listar_usuarios_para_password(busqueda=""):
        session = get_session()
        try:
            query = session.query(Usuario).filter(Usuario.rol != "decano")
            if busqueda:
                like = f"%{busqueda}%"
                query = query.filter((Usuario.username.like(like)) | (Usuario.nombre.like(like)))
            usuarios = query.order_by(Usuario.rol, Usuario.username).all()
            return [{
                "id": u.id, "username": u.username, "nombre": u.nombre,
                "rol": u.rol, "activo": u.activo, "bloqueado": u.bloqueado,
            } for u in usuarios]
        finally:
            session.close()

    @staticmethod
    def resetear_password_usuario(usuario_id, nueva_password="pacha2026"):
        session = get_session()
        try:
            u = session.query(Usuario).filter_by(id=usuario_id).first()
            if not u:
                return {"error": "Usuario no encontrado"}
            u.password_hash = generate_password_hash(nueva_password)
            session.commit()
            return {"ok": True, "username": u.username, "password": nueva_password}
        finally:
            session.close()

    # ============================================================
    # CONFIGURACIÓN
    # ============================================================
    @staticmethod
    def obtener_configuracion():
        session = get_session()
        try:
            configs = session.query(Configuracion).all()
            resultado = {c.clave: c.valor for c in configs}
            defaults = {
                "nombre_sistema": "PACHA",
                "idioma": "es",
                "tema": "andino",
                "anio_maximo_default": "10",
                "inflacion_default": "9.0",
                "bolivia_inflacion_anual": "5.70",
                "bolivia_inflacion_acumulada": "3.88",
                "bolivia_tipo_cambio_usd": "11.90",
                "bolivia_crecimiento_pib": "0.50",
                "bolivia_tasa_desempleo": "4.50",
                "bolivia_fecha_actualizacion": "2026-10-05",
            }
            for k, v in defaults.items():
                if k not in resultado:
                    resultado[k] = v
            return resultado
        finally:
            session.close()

    @staticmethod
    def actualizar_configuracion(clave, valor):
        session = get_session()
        try:
            c = session.query(Configuracion).filter_by(clave=clave).first()
            if c:
                c.valor = valor
            else:
                session.add(Configuracion(clave=clave, valor=valor))
            session.commit()
            return {"ok": True}
        finally:
            session.close()

    # ============================================================
    # ESTADÍSTICAS
    # ============================================================
    @staticmethod
    def obtener_estadisticas():
        session = get_session()
        try:
            return {
                "total_profesores": session.query(Usuario).filter_by(rol="profesor").count(),
                "total_alumnos": session.query(Usuario).filter_by(rol="alumno").count(),
                "total_usuarios": session.query(Usuario).count(),
                "total_simuladores": session.query(Simulador).count(),
            }
        finally:
            session.close()