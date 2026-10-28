"""
Servicio del Alumno — PACHA (Etapa 3)
=====================================

Incluye el ciclo de decisiones (borrador / enviada), la compra de estudios y
la lectura de reportes y resultados de estudios.

Regla de decisión efectiva
--------------------------
Cada equipo tiene **una** fila de decisión por período (restricción única en
base de datos). Mientras está en ``borrador`` puede editarse; al enviarse pasa
a ``enviada`` y queda bloqueada. El motor solo aplica decisiones ``enviada``.
"""
from datetime import datetime
import re

from infraestructura.database import get_session
from core.models import (
    Usuario, Industria, Equipo, Marca, Decision, DecisionMarca, DecisionVendedor,
    DecisionEstudio, Reporte, ReporteMarca, ReporteMarcaCanal, ReporteMarcaSegmento,
    Segmento, Canal, FuerzaVentas, EstudioMercado, CompraEstudio,
    EstudioAwareness, EstudioIntencion, EstudioPanelConsumidores,
    EstudioPanelDistribuidores, EstudioEscala, EstudioMapa, EstudioPronostico,
    EstudioPublicidadCompetencia, EstudioFuerzaVentasCompetencia, EstudioResultado,
    LogActividad, ProyectoID,
)


class AlumnoService:

    # ------------------------------------------------------------------
    # Contexto del equipo
    # ------------------------------------------------------------------
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
            if not industria:
                return None

            marcas = session.query(Marca).filter_by(
                equipo_id=equipo.id, activa=True
            ).order_by(Marca.id).all()
            canales = session.query(Canal).filter_by(
                industria_id=industria.id
            ).order_by(Canal.numero).all()

            anio = int(industria.anio_actual or 0)
            decision = session.query(Decision).filter_by(
                equipo_id=equipo.id, anio=anio
            ).first()

            decisiones_marca = {}
            vendedores_decision = {}
            estudios_comprados = []
            if decision:
                for dm in decision.marcas:
                    decisiones_marca[dm.marca_nombre] = {
                        "precio": float(dm.precio_venta or 0),
                        "publicidad": float(dm.presupuesto_publicitario or 0),
                        "produccion": float(dm.produccion or 0),
                        "proyecto_id": dm.proyecto_id_nombre or "",
                        "objetivo_x": float(dm.objetivo_perceptual_x or 0),
                        "objetivo_y": float(dm.objetivo_perceptual_y or 0),
                        "vendedores": {
                            dv.canal_id: int(dv.vendedores or 0)
                            for dv in dm.vendedores
                        },
                    }
                estudios_comprados = [de.estudio_id for de in decision.estudios]

            # Proyectos de I&D aprobados disponibles para aplicar este período.
            proyectos_aprobados = session.query(ProyectoID).filter(
                ProyectoID.equipo_id == equipo.id,
                ProyectoID.estado == "aprobado",
                ProyectoID.anio_aprobacion <= anio,
            ).order_by(ProyectoID.nombre).all()
            proyectos_por_marca = {}
            marcas_nuevas = []
            for proyecto in proyectos_aprobados:
                if proyecto.es_nueva_marca:
                    marcas_nuevas.append({
                        "nombre": proyecto.nombre,
                        "costo_estandar": float(proyecto.costo_estandar or 0),
                        "presupuesto_normal": float(proyecto.presupuesto_normal or 0),
                    })
                elif proyecto.marca_destino_id:
                    proyectos_por_marca.setdefault(
                        proyecto.marca_destino_id, []
                    ).append({
                        "nombre": proyecto.nombre,
                        "es_nueva_marca": False,
                    })

            marcas_data = []
            for m in marcas:
                vigente = decisiones_marca.get(m.nombre, {})
                vendedores = {}
                detallistas = {}
                for canal in canales:
                    if canal.id in vigente.get("vendedores", {}):
                        vendedores[canal.id] = vigente["vendedores"][canal.id]
                    else:
                        fila = session.query(FuerzaVentas).filter_by(
                            marca_id=m.id, canal_id=canal.id
                        ).order_by(FuerzaVentas.anio.desc()).first()
                        vendedores[canal.id] = int(fila.vendedores or 0) if fila else 0
                    fila = session.query(FuerzaVentas).filter_by(
                        marca_id=m.id, canal_id=canal.id
                    ).order_by(FuerzaVentas.anio.desc()).first()
                    detallistas[canal.id] = int(fila.detallistas or 0) if fila else 0

                marcas_data.append({
                    "id": m.id,
                    "nombre": m.nombre,
                    "tipo": m.tipo,
                    "precio_actual": float(m.precio_actual or 0),
                    "publicidad_actual": float(m.publicidad_actual or 0),
                    "investigacion_actual": float(m.investigacion_actual or 0),
                    "produccion_actual": float(m.produccion_actual or 0),
                    "calidad_actual": float(m.calidad_actual or 0),
                    # Valores para el formulario: borrador si existe, si no vigentes.
                    "precio_form": vigente.get("precio", float(m.precio_actual or 0)),
                    "publicidad_form": vigente.get(
                        "publicidad", float(m.publicidad_actual or 0)
                    ),
                    "produccion_form": vigente.get(
                        "produccion", float(m.produccion_actual or 0)
                    ),
                    "proyecto_id": vigente.get("proyecto_id", ""),
                    "objetivo_x": vigente.get("objetivo_x", 0),
                    "objetivo_y": vigente.get("objetivo_y", 0),
                    "vendedores": vendedores,
                    "detallistas": detallistas,
                    "proyectos": proyectos_por_marca.get(m.id, []),
                })

            estudios = session.query(EstudioMercado).order_by(EstudioMercado.numero).all()

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
                    "ya_decidio": bool(equipo.ya_decidio),
                    "bloqueado": bool(equipo.bloqueado),
                    "presupuesto_actual": float(equipo.presupuesto_actual or 0),
                },
                "industria": {
                    "id": industria.id,
                    "nombre": industria.nombre,
                    "anio_actual": anio,
                    "anio_maximo": int(industria.anio_maximo or 10),
                    "estado": industria.estado,
                    "permitir_envio": bool(industria.permitir_envio),
                    "inflacion_anual": float(industria.inflacion_anual or 0),
                    "tipo_cambio_usd": float(industria.tipo_cambio_usd or 0),
                    "crecimiento_pib": float(industria.crecimiento_pib or 0),
                },
                "decision": {
                    "id": decision.id,
                    "estado": decision.estado or "enviada",
                    "actualizada": decision.actualizada,
                } if decision else None,
                "marcas": marcas_data,
                "canales": [{
                    "id": c.id,
                    "numero": c.numero,
                    "nombre": c.nombre,
                    "total_distribuidores": int(c.total_distribuidores or 0),
                } for c in canales],
                "estudios": [{
                    "id": e.id,
                    "numero": e.numero,
                    "nombre": e.nombre,
                    "descripcion": e.descripcion or "",
                    "costo_base": float(e.costo_base or 0),
                    "tipo_producto": e.tipo_producto,
                } for e in estudios],
                "estudios_comprados": estudios_comprados,
                "marcas_nuevas": marcas_nuevas,
            }
        finally:
            session.close()

    # ------------------------------------------------------------------
    # Decisiones
    # ------------------------------------------------------------------
    @staticmethod
    def guardar_decision(equipo_id, anio, decisiones, canales_ids=None, estudios_ids=None,
                         estado="enviada", usuario_id=None):
        """Guarda un borrador o envía la decisión efectiva del período.

        ``decisiones``: {nombre_marca: {precio, publicidad, produccion,
        proyecto_id, objetivo_x, objetivo_y, vendedores: {canal_id: n}}}
        """
        if estado not in ("borrador", "enviada"):
            return {"error": "Estado de decisión inválido"}

        session = get_session()
        try:
            equipo = session.query(Equipo).filter_by(id=equipo_id).first()
            if not equipo:
                return {"error": "Equipo no encontrado"}
            if equipo.bloqueado:
                return {"error": "El equipo está bloqueado por el profesor"}
            if estado == "enviada" and equipo.ya_decidio:
                return {
                    "error": (
                        "La decisión de este período ya fue enviada. "
                        "No se puede modificar."
                    )
                }

            dec = session.query(Decision).filter_by(
                equipo_id=equipo_id, anio=anio
            ).first()

            if dec and (dec.estado or "enviada") == "enviada" and estado == "borrador":
                return {"error": "La decisión ya fue enviada; no admite borradores."}

            if dec:
                for dm in list(dec.marcas):
                    session.delete(dm)
                for de in list(dec.estudios):
                    session.delete(de)
                session.flush()
                dec.estado = estado
                dec.actualizada = datetime.now()
                if estado == "enviada":
                    dec.enviada = datetime.now()
            else:
                dec = Decision(
                    equipo_id=equipo_id,
                    anio=anio,
                    estado=estado,
                    actualizada=datetime.now(),
                    enviada=datetime.now() if estado == "enviada" else None,
                )
                session.add(dec)
                session.flush()

            canales_ids = set(canales_ids or [])

            # Normaliza nombres y valida el uso de proyectos de I&D. Las marcas
            # nuevas solo pueden nacer de un proyecto aprobado de marca nueva.
            decisiones = {
                str(nombre).strip().upper(): datos
                for nombre, datos in decisiones.items()
            }
            marcas_existentes = {
                m.nombre.upper(): m for m in session.query(Marca).filter_by(
                    equipo_id=equipo_id, activa=True
                ).all()
            }
            proyectos_equipo = {
                p.nombre: p for p in session.query(ProyectoID).filter(
                    ProyectoID.equipo_id == equipo_id,
                    ProyectoID.estado == "aprobado",
                    ProyectoID.anio_aprobacion <= anio,
                ).all()
            }
            nuevas = 0
            for nombre_marca, datos in decisiones.items():
                proyecto_nombre = (
                    datos.get("proyecto_id") or ""
                ).strip().upper()
                datos["proyecto_id"] = proyecto_nombre
                if nombre_marca in marcas_existentes:
                    if not proyecto_nombre:
                        continue
                    proyecto = proyectos_equipo.get(proyecto_nombre)
                    if not proyecto:
                        return {"error": (
                            f"El proyecto {proyecto_nombre} no está aprobado "
                            f"para {nombre_marca}."
                        )}
                    if proyecto.es_nueva_marca:
                        return {"error": (
                            f"{proyecto_nombre} es un proyecto de marca nueva; "
                            "no se puede aplicar a una marca existente."
                        )}
                    if (proyecto.marca_destino_id
                            and proyecto.marca_destino_id
                            != marcas_existentes[nombre_marca].id):
                        return {"error": (
                            f"El proyecto {proyecto_nombre} fue aprobado para "
                            f"otra marca, no para {nombre_marca}."
                        )}
                    continue

                proyecto = proyectos_equipo.get(proyecto_nombre)
                if not proyecto or not proyecto.es_nueva_marca:
                    return {"error": (
                        f"La marca {nombre_marca} no existe y no hay un "
                        "proyecto aprobado de marca nueva que la respalde."
                    )}
                if not re.match(r"^[A-Z]{4,10}$", nombre_marca):
                    return {"error": (
                        f"Nombre de marca nueva inválido: {nombre_marca}. "
                        "Usa entre 4 y 10 letras mayúsculas."
                    )}
                if session.query(Marca).filter_by(
                    equipo_id=equipo_id, nombre=nombre_marca
                ).first():
                    return {"error": f"La marca {nombre_marca} ya existe."}
                nuevas += 1

            if len(marcas_existentes) + nuevas > 5:
                return {"error": (
                    "El equipo no puede superar las 5 marcas activas."
                )}

            for nombre_marca, datos in decisiones.items():
                try:
                    precio = float(datos.get("precio", 0))
                    publicidad = float(datos.get("publicidad", 0))
                    produccion = float(datos.get("produccion", 0))
                except (TypeError, ValueError):
                    return {"error": f"Valores numéricos inválidos en {nombre_marca}"}

                if precio <= 0:
                    return {"error": f"El precio de {nombre_marca} debe ser mayor que cero"}
                if publicidad < 0 or produccion < 0:
                    return {"error": f"Publicidad y producción no pueden ser negativas ({nombre_marca})"}

                dm = DecisionMarca(
                    decision_id=dec.id,
                    marca_nombre=nombre_marca,
                    proyecto_id_nombre=(datos.get("proyecto_id") or None),
                    produccion=produccion,
                    presupuesto_publicitario=publicidad,
                    precio_venta=precio,
                    objetivo_perceptual_x=datos.get("objetivo_x"),
                    objetivo_perceptual_y=datos.get("objetivo_y"),
                )
                session.add(dm)
                session.flush()

                vendedores = datos.get("vendedores") or {}
                for canal_id, cantidad in vendedores.items():
                    if canales_ids and canal_id not in canales_ids:
                        continue
                    try:
                        cantidad = int(cantidad)
                    except (TypeError, ValueError):
                        cantidad = 0
                    if cantidad < 0:
                        return {"error": f"Los vendedores no pueden ser negativos ({nombre_marca})"}
                    session.add(DecisionVendedor(
                        decision_marca_id=dm.id,
                        canal_id=canal_id,
                        vendedores=cantidad,
                    ))

            # Estudios seleccionados: se guardan como intención en borrador y
            # como compra efectiva al enviar.
            estudios_ids = [int(e) for e in (estudios_ids or [])]
            estudios_validos = session.query(EstudioMercado).filter(
                EstudioMercado.id.in_(estudios_ids)
            ).all() if estudios_ids else []
            ids_validos = {e.id for e in estudios_validos}

            for estudio_id in ids_validos:
                session.add(DecisionEstudio(
                    decision_id=dec.id,
                    estudio_id=estudio_id,
                    comprado=(estado == "enviada"),
                ))

            if estado == "enviada":
                existentes = session.query(CompraEstudio).filter_by(
                    equipo_id=equipo_id, anio=anio
                ).all()
                por_estudio = {c.estudio_id: c for c in existentes}

                for compra in existentes:
                    if compra.estudio_id not in ids_validos:
                        session.delete(compra)

                catalogo = {e.id: e for e in estudios_validos}
                for estudio_id in ids_validos:
                    if estudio_id in por_estudio:
                        continue
                    session.add(CompraEstudio(
                        equipo_id=equipo_id,
                        estudio_id=estudio_id,
                        anio=anio,
                        costo=float(catalogo[estudio_id].costo_base or 0),
                    ))

                equipo.ya_decidio = True
                equipo.fecha_decision = datetime.now()
            else:
                equipo.ya_decidio = False
                equipo.fecha_decision = None

            session.add(LogActividad(
                usuario_id=usuario_id,
                accion=f"decision_{estado}",
                detalle=f"Equipo {equipo_id}, período {anio}"[:255],
            ))
            session.commit()
            return {"ok": True, "estado": estado, "decision_id": dec.id}
        except Exception as e:
            session.rollback()
            return {"error": str(e)}
        finally:
            session.close()

    # ------------------------------------------------------------------
    # Reportes
    # ------------------------------------------------------------------
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

            numeros_segmento = {
                s.id: s.numero
                for s in session.query(Segmento).filter_by(
                    industria_id=session.query(Equipo).filter_by(
                        id=equipo_id
                    ).first().industria_id
                ).all()
            }

            marcas = []
            for rm in rep.marcas:
                canales_data = {}
                fv_c1, fv_c2, fv_c3 = 0, 0, 0
                for rm_canal in rm.canales:
                    canales_data[rm_canal.canal_id] = float(rm_canal.detallistas or 0)
                    if rm_canal.canal_id == 1:
                        fv_c1 = float(rm_canal.vendedores or 0)
                    if rm_canal.canal_id == 2:
                        fv_c2 = float(rm_canal.vendedores or 0)
                    if rm_canal.canal_id == 3:
                        fv_c3 = float(rm_canal.vendedores or 0)

                segmentos_data = {}
                for rm_seg in rm.segmentos:
                    numero = numeros_segmento.get(rm_seg.segmento_id)
                    if numero is None:
                        continue
                    segmentos_data[numero] = {
                        "ventas_unidades": float(rm_seg.ventas_unidades or 0),
                        "porcion_mercado": float(rm_seg.porcion_mercado or 0),
                    }

                marcas.append({
                    "marca": rm.marca_nombre,
                    "produccion": float(rm.produccion or 0),
                    "unidades_vendidas": float(rm.unidades_vendidas or 0),
                    "inventario": float(rm.inventario or 0),
                    "precio_final": float(rm.precio_final or 0),
                    "precio_promedio": float(rm.precio_promedio or 0),
                    "costo_transferencia": float(rm.costo_transferencia or 0),
                    "ingresos": float(rm.ingresos or 0),
                    "costo_productos_vendidos": float(rm.costo_productos_vendidos or 0),
                    "costo_inventario": float(rm.costo_inventario or 0),
                    "publicidad": float(rm.publicidad or 0),
                    "contribucion_bruta_marketing": float(rm.contribucion_bruta_marketing or 0),
                    "porcion_mercado": float(rm.porcion_mercado or 0),
                    "detallistas": canales_data,
                    "fv_canal_1": fv_c1,
                    "fv_canal_2": fv_c2,
                    "fv_canal_3": fv_c3,
                    "segmentos": segmentos_data,
                })

            return {
                "anio": int(rep.anio),
                "mercado_total": float(rep.mercado_total or 0),
                "contribucion_bruta_total": float(rep.contribucion_bruta_total or 0),
                "contribucion_neta_total": float(rep.contribucion_neta_total or 0),
                "presupuesto_proximo_periodo": float(rep.presupuesto_proximo_periodo or 0),
                "investigacion_total": float(rep.investigacion_total or 0),
                "fuerza_ventas_total": float(rep.fuerza_ventas_total or 0),
                "investigacion_mercado": float(rep.investigacion_mercado or 0),
                "costo_util_excepcional": float(rep.costo_util_excepcional or 0),
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
                contribucion_acum = sum(
                    float(rep.contribucion_neta_total or 0) for rep in reportes
                )
                ventas_totales = 0.0
                porciones = []
                marcas_nombres = []
                for rep in reportes:
                    for rm in rep.marcas:
                        ventas_totales += float(rm.unidades_vendidas or 0)
                        porciones.append(float(rm.porcion_mercado or 0))
                        if rm.marca_nombre not in marcas_nombres:
                            marcas_nombres.append(rm.marca_nombre)
                porcion_mercado = (
                    sum(porciones) / len(porciones) if porciones else 0.0
                )
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
            for idx, p in enumerate(participantes, start=1):
                p["ranking"] = idx
            return participantes
        finally:
            session.close()

    # ------------------------------------------------------------------
    # Estudios
    # ------------------------------------------------------------------
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

    @staticmethod
    def listar_estudios_equipo(equipo_id, anio=None):
        """Devuelve los estudios comprados por el equipo y sus resultados."""
        session = get_session()
        try:
            equipo = session.query(Equipo).filter_by(id=equipo_id).first()
            if not equipo:
                return {"anio": anio, "estudios": []}

            if anio is None:
                ultima = session.query(CompraEstudio).filter_by(
                    equipo_id=equipo_id
                ).order_by(CompraEstudio.anio.desc()).first()
                if ultima:
                    anio = ultima.anio
                else:
                    industria = session.query(Industria).filter_by(
                        id=equipo.industria_id
                    ).first()
                    anio = int(industria.anio_actual or 0) if industria else 0

            compras = session.query(CompraEstudio).filter_by(
                equipo_id=equipo_id, anio=anio
            ).order_by(CompraEstudio.estudio_id).all()

            estudios = []
            for compra in compras:
                estudio = session.query(EstudioMercado).filter_by(
                    id=compra.estudio_id
                ).first()
                if not estudio:
                    continue
                estudios.append({
                    "id": estudio.id,
                    "numero": estudio.numero,
                    "nombre": estudio.nombre,
                    "descripcion": estudio.descripcion or "",
                    "tipo_producto": estudio.tipo_producto,
                    "costo": float(compra.costo or estudio.costo_base or 0),
                    "comprado": compra.comprado,
                    "bloques": AlumnoService._bloques_estudio(session, compra, estudio),
                })

            return {"anio": anio, "estudios": estudios}
        finally:
            session.close()

    @staticmethod
    def _bloques_estudio(session, compra, estudio):
        """Convierte los datos persistidos del estudio en tablas para la vista."""
        bloques = []

        awareness = session.query(EstudioAwareness).filter_by(
            compra_id=compra.id
        ).order_by(EstudioAwareness.marca_nombre).all()
        if awareness:
            bloques.append({
                "titulo": "Conocimiento de marca",
                "columnas": ["Marca", "Awareness (%)"],
                "filas": [[a.marca_nombre, f"{float(a.awareness or 0) * 100:.1f}"] for a in awareness],
            })

        intenciones = session.query(EstudioIntencion).filter_by(
            compra_id=compra.id
        ).all()
        if intenciones:
            segmentos = sorted({i.segmento_id for i in intenciones})
            numeros = {
                s.id: s.numero for s in session.query(Segmento).filter(
                    Segmento.id.in_(segmentos)
                ).all()
            }
            por_marca = {}
            for item in intenciones:
                fila = por_marca.setdefault(item.marca_nombre, {})
                fila[numeros.get(item.segmento_id, item.segmento_id)] = float(
                    item.intencion or 0
                )
            numeros_presentes = sorted({
                n for fila in por_marca.values() for n in fila
            })
            columnas = ["Marca"] + [f"Segmento {n}" for n in numeros_presentes]
            filas = []
            for marca, valores in sorted(por_marca.items()):
                filas.append([marca] + [
                    f"{valores.get(n, 0) * 100:.1f}%" for n in numeros_presentes
                ])
            bloques.append({
                "titulo": "Intención de compra por segmento",
                "columnas": columnas,
                "filas": filas,
            })

        panel_cons = session.query(EstudioPanelConsumidores).filter_by(
            compra_id=compra.id
        ).all()
        if panel_cons:
            numeros = {
                s.id: s.numero for s in session.query(Segmento).filter(
                    Segmento.id.in_({p.segmento_id for p in panel_cons})
                ).all()
            }
            bloques.append({
                "titulo": "Panel de consumidores",
                "columnas": ["Marca", "Segmento", "Porción (%)", "Ventas (miles U)"],
                "filas": [[
                    p.marca_nombre,
                    f"Segmento {numeros.get(p.segmento_id, p.segmento_id)}",
                    f"{float(p.porcion_mercado or 0) * 100:.1f}",
                    f"{float(p.ventas_unidades or 0):,.0f}",
                ] for p in panel_cons],
            })

        panel_dist = session.query(EstudioPanelDistribuidores).filter_by(
            compra_id=compra.id
        ).all()
        if panel_dist:
            numeros = {
                c.id: c.numero for c in session.query(Canal).filter(
                    Canal.id.in_({p.canal_id for p in panel_dist})
                ).all()
            }
            bloques.append({
                "titulo": "Panel de distribuidores",
                "columnas": ["Marca", "Canal", "Porción (%)", "Ventas (miles U)"],
                "filas": [[
                    p.marca_nombre,
                    f"Canal {numeros.get(p.canal_id, p.canal_id)}",
                    f"{float(p.porcion_mercado or 0) * 100:.1f}",
                    f"{float(p.ventas_unidades or 0):,.0f}",
                ] for p in panel_dist],
            })

        escalas = session.query(EstudioEscala).filter_by(
            compra_id=compra.id
        ).all()
        if escalas:
            por_marca = {}
            for e in escalas:
                por_marca.setdefault(e.marca_nombre, {})[e.escala] = float(e.valor or 0)
            bloques.append({
                "titulo": "Escalas semánticas (1 a 7)",
                "columnas": ["Marca", "Valor", "Potencia", "Diseño"],
                "filas": [[
                    marca,
                    f"{valores.get('VALOR', 0):.2f}",
                    f"{valores.get('POTENCIA', 0):.2f}",
                    f"{valores.get('DISENO', 0):.2f}",
                ] for marca, valores in sorted(por_marca.items())],
            })

        mapa = session.query(EstudioMapa).filter_by(compra_id=compra.id).all()
        if mapa:
            bloques.append({
                "titulo": "Mapa perceptual",
                "columnas": ["Entidad", "Tipo", "Eje X", "Eje Y"],
                "filas": [[
                    m.entidad_nombre, m.entidad_tipo,
                    f"{float(m.posicion_x or 0):.1f}",
                    f"{float(m.posicion_y or 0):.1f}",
                ] for m in mapa],
            })

        pronosticos = session.query(EstudioPronostico).filter_by(
            compra_id=compra.id
        ).all()
        if pronosticos:
            numeros = {
                s.id: s.numero for s in session.query(Segmento).filter(
                    Segmento.id.in_({p.segmento_id for p in pronosticos})
                ).all()
            }
            bloques.append({
                "titulo": "Pronóstico de mercado",
                "columnas": ["Segmento", "Unidades esperadas (miles U)"],
                "filas": [[
                    f"Segmento {numeros.get(p.segmento_id, p.segmento_id)}",
                    f"{float(p.unidades_esperadas or 0):,.0f}",
                ] for p in pronosticos],
            })

        publicidad = session.query(EstudioPublicidadCompetencia).filter_by(
            compra_id=compra.id
        ).order_by(EstudioPublicidadCompetencia.marca_nombre).all()
        if publicidad:
            bloques.append({
                "titulo": "Publicidad de la competencia",
                "columnas": ["Marca", "Publicidad estimada (miles Bs.)"],
                "filas": [[
                    p.marca_nombre, f"{float(p.publicidad_estimada or 0):,.0f}"
                ] for p in publicidad],
            })

        fuerza = session.query(EstudioFuerzaVentasCompetencia).filter_by(
            compra_id=compra.id
        ).all()
        if fuerza:
            numeros = {
                c.id: c.numero for c in session.query(Canal).filter(
                    Canal.id.in_({f.canal_id for f in fuerza})
                ).all()
            }
            bloques.append({
                "titulo": "Fuerza de ventas de la competencia",
                "columnas": ["Marca", "Canal", "Vendedores"],
                "filas": [[
                    f.marca_nombre,
                    f"Canal {numeros.get(f.canal_id, f.canal_id)}",
                    f"{int(f.vendedores_estimados or 0)}",
                ] for f in fuerza],
            })

        extras = session.query(EstudioResultado).filter_by(
            compra_id=compra.id
        ).all()
        if extras:
            por_categoria = {}
            for e in extras:
                por_categoria.setdefault(e.categoria, []).append(e)
            etiquetas = {
                "habitos_compra": "Hábitos de compra",
                "ideales_segmento": "Ideales de segmento",
                "experimento": "Resultados del experimento",
            }
            for categoria, filas in por_categoria.items():
                bloques.append({
                    "titulo": etiquetas.get(categoria, categoria.replace("_", " ").title()),
                    "columnas": ["Entidad", "Métrica", "Valor"],
                    "filas": [[
                        f.entidad, f.metrica.replace("_", " ").title(),
                        f"{float(f.valor or 0):,.2f}",
                    ] for f in filas],
                })

        if not bloques:
            bloques.append({
                "titulo": "Sin resultados",
                "columnas": ["Estado"],
                "filas": [["Este estudio se procesará en la próxima ronda."]],
                "vacio": True,
            })

        return bloques
