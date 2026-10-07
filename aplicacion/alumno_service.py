"""
Servicio del Alumno - PACHA
"""
from infraestructura.database import get_session
from core.models import (
    Usuario, Industria, Equipo, Marca, Decision, DecisionMarca,
    Reporte, ReporteMarca, EstudioMercado,
)


class AlumnoService:

    @staticmethod
    def obtener_equipo_del_alumno(usuario_id):
        session = get_session()
        try:
            usuario = session.query(Usuario).filter_by(id=usuario_id).first()
            if not usuario or not usuario.equipo_id:
                return None

            equipo = session.query(Equipo).filter_by(id=usuario.equipo_id).first()
            if not equipo:
                return None

            industria = session.query(Industria).filter_by(id=equipo.industria_id).first()
            marcas = session.query(Marca).filter_by(equipo_id=equipo.id, activa=True).all()

            return {
                "usuario": {
                    "id": usuario.id,
                    "username": usuario.username,
                    "nombre": usuario.nombre,
                },
                "equipo": {
                    "id": equipo.id,
                    "numero": equipo.numero,
                    "nombre_empresa": equipo.nombre_empresa,
                    "ya_decidio": equipo.ya_decidio,
                    "bloqueado": equipo.bloqueado,
                    "presupuesto_actual": float(equipo.presupuesto_actual or 0),
                },
                "industria": {
                    "id": industria.id,
                    "nombre": industria.nombre,
                    "anio_actual": int(industria.anio_actual or 0),
                    "anio_maximo": int(industria.anio_maximo or 10),
                    "estado": industria.estado,
                    "permitir_envio": bool(industria.permitir_envio),
                    "inflacion_anual": float(industria.inflacion_anual or 0),
                    "tipo_cambio_usd": float(industria.tipo_cambio_usd or 0),
                    "crecimiento_pib": float(industria.crecimiento_pib or 0),
                } if industria else None,
                "marcas": [{
                    "id": m.id,
                    "nombre": m.nombre,
                    "tipo": m.tipo,
                    "precio_actual": float(m.precio_actual or 0),
                    "publicidad_actual": float(m.publicidad_actual or 0),
                    "investigacion_actual": float(m.investigacion_actual or 0),
                    "produccion_actual": float(m.produccion_actual or 0),
                } for m in marcas],
            }
        finally:
            session.close()

    @staticmethod
    def listar_reportes(equipo_id):
        session = get_session()
        try:
            reportes = session.query(Reporte).filter_by(
                equipo_id=equipo_id
            ).order_by(Reporte.anio).all()

            resultado = []
            for rep in reportes:
                marcas = []
                for rm in rep.marcas:
                    marcas.append({
                        "marca": rm.marca_nombre,
                        "produccion": float(rm.produccion or 0),
                        "unidades_vendidas": float(rm.unidades_vendidas or 0),
                        "inventario": float(rm.inventario or 0),
                        "precio_final": float(rm.precio_final or 0),
                        "publicidad": float(rm.publicidad or 0),
                        "contribucion_bruta_marketing": float(rm.contribucion_bruta_marketing or 0),
                        "porcion_mercado": float(rm.porcion_mercado or 0),
                    })
                resultado.append({
                    "anio": int(rep.anio),
                    "mercado_total": float(rep.mercado_total or 0),
                    "contribucion_bruta_total": float(rep.contribucion_bruta_total or 0),
                    "contribucion_neta_total": float(rep.contribucion_neta_total or 0),
                    "presupuesto_proximo_periodo": float(rep.presupuesto_proximo_periodo or 0),
                    "marcas": marcas,
                })
            return resultado
        finally:
            session.close()

    @staticmethod
    def obtener_reporte(equipo_id, anio):
        session = get_session()
        try:
            rep = session.query(Reporte).filter_by(
                equipo_id=equipo_id, anio=anio
            ).first()

            if not rep:
                return None

            marcas = []
            for rm in rep.marcas:
                marcas.append({
                    "marca": rm.marca_nombre,
                    "produccion": float(rm.produccion or 0),
                    "unidades_vendidas": float(rm.unidades_vendidas or 0),
                    "inventario": float(rm.inventario or 0),
                    "precio_final": float(rm.precio_final or 0),
                    "publicidad": float(rm.publicidad or 0),
                    "contribucion_bruta_marketing": float(rm.contribucion_bruta_marketing or 0),
                    "porcion_mercado": float(rm.porcion_mercado or 0),
                    "ingresos": float(rm.ingresos or 0),
                    "costo_productos_vendidos": float(rm.costo_productos_vendidos or 0),
                    "costo_inventario": float(rm.costo_inventario or 0),
                })

            return {
                "anio": int(rep.anio),
                "mercado_total": float(rep.mercado_total or 0),
                "contribucion_bruta_total": float(rep.contribucion_bruta_total or 0),
                "contribucion_neta_total": float(rep.contribucion_neta_total or 0),
                "presupuesto_proximo_periodo": float(rep.presupuesto_proximo_periodo or 0),
                "investigacion_total": 0.0,
                "fuerza_ventas_total": 0.0,
                "investigacion_mercado": 0.0,
                "marcas": marcas,
            }
        finally:
            session.close()

    @staticmethod
    def listar_equipos_industria(industria_id):
        session = get_session()
        try:
            equipos = session.query(Equipo).filter_by(
                industria_id=industria_id
            ).order_by(Equipo.numero).all()

            return [{
                "id": eq.id,
                "numero": eq.numero,
                "nombre_empresa": eq.nombre_empresa,
                "ya_decidio": bool(eq.ya_decidio),
                "bloqueado": bool(eq.bloqueado),
            } for eq in equipos]
        finally:
            session.close()

    @staticmethod
    def guardar_decision(equipo_id, anio, decisiones):
        from datetime import datetime
        session = get_session()
        try:
            dec = session.query(Decision).filter_by(
                equipo_id=equipo_id, anio=anio
            ).first()

            if dec:
                for dm in dec.marcas:
                    session.delete(dm)
                session.commit()
                dec.enviada = datetime.now()
            else:
                dec = Decision(equipo_id=equipo_id, anio=anio)
                session.add(dec)
                session.commit()
                session.refresh(dec)

            for marca_nombre, datos in decisiones.items():
                dm = DecisionMarca(
                    decision_id=dec.id,
                    marca_nombre=marca_nombre,
                    proyecto_id_nombre=datos.get("proyecto_id"),
                    produccion=datos.get("produccion", 0),
                    presupuesto_publicitario=datos.get("publicidad", 0),
                    precio_venta=datos.get("precio", 300),
                )
                session.add(dm)
            session.commit()

            equipo = session.query(Equipo).filter_by(id=equipo_id).first()
            if equipo:
                equipo.ya_decidio = True
                equipo.fecha_decision = datetime.now()
                session.commit()

            return {"ok": True}
        except Exception as e:
            session.rollback()
            return {"error": str(e)}
        finally:
            session.close()
    
    @staticmethod
    def obtener_participantes(industria_id, equipo_actual_id):
        session = get_session()
        try:
            equipos = session.query(Equipo).filter_by(
            industria_id=industria_id
            ).order_by(Equipo.numero).all()
            
            participantes = []
            for eq in equipos:
                reportes = session.query(Reporte).filter_by(
                    equipo_id=eq.id
                ).all()
                contribucion_acum =sum(
                    float(rep.contribucion_neta_total or 0) for rep in reportes
                )
                ventas_totales = 0.0
                porcion_mercado = 0.0
                marcas_nombres = []
                for rep in reportes:
                    for rm in rep.marcas:
                        ventas_totales += float(rm.unidades_vendidas or 0)
                        porcion_mercado += float(rm.porcion_mercado or 0)
                        if rm.marca_nombre not in marcas_nombres:
                            marcas_nombres.append(rm.marca_nombre)
                        if marcas_nombres:
                            porcion_mercado = porcion_mercado / len((marcas_nombres) or 1)
                participantes.append({
                "equipo_id": eq.id,
                "firma": f"Firma {eq.numero}",
                "marcas": ", ".join(marcas_nombres) if marcas_nombres else "—",
                "contribucion": contribucion_acum,
                "porcion": porcion_mercado,
                "ventas": ventas_totales,
                "es_tuya": (eq.id == equipo_actual_id),
            }) 
                participantes.sort(key=lambda p: p["contribucion"], reverse=True)
                for idx, p in enumerate(participantes,start=1):
                    p["ranking"] = idx
            return participantes
        finally:
            session.close()
    
    @staticmethod
    def listar_estudios_disponibles():
        session = get_session()
        try:
            estudios = session.query(EstudioMercado).order_by(EstudioMercado.numero).all()
            return [{
                "id": e.id,
                "numero": e.numero,
                "nombre": e.nombre,
                "descripcion": e.descripcion or "",
                "costo_base": float(e.costo_base or 0),
                "tipo_producto": e.tipo_producto,
            } for e in estudios]
        finally:
            session.close()
            
    
