"""
Servicio de simulación — PACHA (Etapa 3)
=========================================

Orquesta el motor con la base normalizada y persiste, en una sola
transacción, todo lo que produce una ronda:

- cabecera y detalle del reporte por equipo, marca, canal y segmento;
- estado de las marcas para el año siguiente;
- fuerza de ventas elegida;
- datos de los estudios comprados;
- presupuesto, año de la industria y bitácora.

Regla de decisión efectiva
--------------------------
Solo se procesa una decisión por equipo y período, y solo si está en estado
``enviada``. Los borradores se conservan pero no se aplican.

Regla de ausencia
-----------------
Si un equipo no tiene decisión efectiva para el período, la ronda se calcula
igual con los valores vigentes de sus marcas (precio, publicidad, producción y
fuerza de ventas del último año). No se inventan valores: la ausencia se
reporta al profesor en el resumen de la ronda.
"""
from datetime import datetime

from infraestructura.database import get_session
from core.models import (
    Industria, Equipo, Marca, Decision, DecisionMarca, DecisionVendedor,
    Reporte, ReporteMarca, ReporteMarcaCanal, ReporteMarcaSegmento,
    Segmento, Canal, FuerzaVentas, CompraEstudio, EstudioMercado,
    ProyectoID, LogActividad,
)
from core.motor_simulacion import MotorSimulacion
from aplicacion.proyecto_service import ProyectoService


class SimulacionService:

    @staticmethod
    def procesar_ronda(industria_id, usuario_id=None):
        session = get_session()
        try:
            industria = session.query(Industria).filter_by(id=industria_id).first()
            if not industria:
                return {"error": "Industria no encontrada"}

            if industria.estado == "finalizada":
                return {"error": "La simulación ya está finalizada."}

            anio_actual = int(industria.anio_actual or 0)
            siguiente_anio = anio_actual + 1
            anio_maximo = int(industria.anio_maximo or 10)

            if siguiente_anio > anio_maximo:
                return {
                    "error": (
                        f"El período {anio_actual} es el último. No se puede "
                        f"procesar un reporte para el año {siguiente_anio}."
                    )
                }

            equipos = session.query(Equipo).filter_by(
                industria_id=industria_id
            ).order_by(Equipo.numero).all()
            if not equipos:
                return {"error": "No hay equipos en la simulación"}

            ids_equipos = [eq.id for eq in equipos]

            # Idempotencia: nunca sobrescribir un reporte ya calculado.
            existentes = session.query(Reporte).filter(
                Reporte.equipo_id.in_(ids_equipos),
                Reporte.anio == siguiente_anio,
            ).all()
            if existentes:
                return {
                    "error": (
                        f"Ya existe un reporte del año {siguiente_anio} para "
                        f"{len(existentes)} equipo(s). Procesamiento cancelado "
                        "para no duplicar datos."
                    )
                }

            segmentos = session.query(Segmento).filter_by(
                industria_id=industria_id
            ).order_by(Segmento.numero).all()
            canales = session.query(Canal).filter_by(
                industria_id=industria_id
            ).order_by(Canal.numero).all()

            # Decisiones efectivas del período (una por equipo por restricción).
            decisiones = {
                d.equipo_id: d
                for d in session.query(Decision).filter(
                    Decision.equipo_id.in_(ids_equipos),
                    Decision.anio == anio_actual,
                    Decision.estado == "enviada",
                ).all()
            }

            # Proyectos de I&D aprobados que el equipo aplica en esta hoja:
            # se ejecutan antes del motor para que la marca ya tenga los
            # atributos, el costo unitario y la calidad del nuevo producto.
            proyectos_aplicados = ProyectoService.aplicar_proyectos_decisiones(
                session, equipos, decisiones, anio_actual
            )

            marcas_por_equipo = {}
            marcas_data = []
            sin_decision = []

            for eq in equipos:
                decision = decisiones.get(eq.id)
                if not decision:
                    sin_decision.append({
                        "equipo_id": eq.id,
                        "numero": eq.numero,
                        "nombre": eq.nombre_empresa or f"Empresa {eq.numero}",
                        "motivo": "Sin decisión efectiva: se usan los valores vigentes.",
                    })

                marcas = session.query(Marca).filter_by(
                    equipo_id=eq.id, activa=True
                ).order_by(Marca.id).all()
                marcas_por_equipo[eq.id] = marcas

                for marca in marcas:
                    datos = SimulacionService._datos_marca(
                        session, eq, marca, decision, anio_actual, canales
                    )
                    marcas_data.append(datos)

            if not marcas_data:
                return {"error": "No hay marcas activas para simular"}

            config = {
                "mercado_total": 1300000,
                "inflacion_anual": industria.inflacion_anual,
                "crecimiento_pib": industria.crecimiento_pib,
                "anio_base": 0,
                "semilla": f"industria-{industria.id}",
            }
            motor = MotorSimulacion(config)
            salida = motor.simular_ronda(
                marcas_data,
                [{
                    "id": s.id, "numero": s.numero, "peso": s.peso,
                    "valor_ideal_x": s.valor_ideal_x,
                    "valor_ideal_y": s.valor_ideal_y,
                } for s in segmentos],
                [{
                    "id": c.id, "numero": c.numero,
                    "total_distribuidores": c.total_distribuidores,
                    "margen_promedio": c.margen_promedio,
                } for c in canales],
                anio_actual,
            )

            resultados_por_equipo = {}
            for resultado in salida["resultados"]:
                resultados_por_equipo.setdefault(resultado["equipo_id"], []).append(resultado)

            estudios_generados = 0
            resumen_equipos = []

            for eq in equipos:
                resultados = resultados_por_equipo.get(eq.id, [])
                marcas = marcas_por_equipo.get(eq.id, [])

                gasto_estudios = session.query(CompraEstudio).filter_by(
                    equipo_id=eq.id, anio=anio_actual
                ).all()
                costo_estudios_miles = sum(
                    float(c.costo or 0) for c in gasto_estudios
                ) / 1000.0

                gasto_id = session.query(ProyectoID).filter(
                    ProyectoID.equipo_id == eq.id,
                    ProyectoID.anio_inicio == anio_actual,
                    ProyectoID.estado != "cancelado",
                ).all()
                investigacion_total = sum(float(p.gastos or 0) for p in gasto_id) / 1000.0

                costo_fijo = MotorSimulacion.COSTO_FIJO_POR_MARCA * len(resultados)
                bruta = sum(r["contribucion_bruta_marketing"] for r in resultados)
                neta = bruta - costo_fijo - investigacion_total - costo_estudios_miles
                presupuesto = max(
                    float(industria.presupuesto_inicial or 10000),
                    neta * 0.3,
                )

                reporte = Reporte(
                    equipo_id=eq.id,
                    anio=siguiente_anio,
                    mercado_total=salida["mercado_total"],
                    contribucion_bruta_total=round(bruta, 2),
                    contribucion_neta_total=round(neta, 2),
                    presupuesto_proximo_periodo=round(presupuesto, 2),
                    investigacion_total=round(investigacion_total, 2),
                    fuerza_ventas_total=round(
                        sum(r["costo_fuerza_ventas"] for r in resultados), 2
                    ),
                    investigacion_mercado=round(costo_estudios_miles, 2),
                    costo_util_excepcional=round(costo_fijo, 2),
                    inflacion_aplicada=industria.inflacion_anual,
                    crecimiento_pnb=industria.crecimiento_pib,
                    tipo_cambio=industria.tipo_cambio_usd,
                )
                session.add(reporte)
                session.flush()

                for resultado in resultados:
                    rm = ReporteMarca(
                        reporte_id=reporte.id,
                        marca_nombre=resultado["marca"],
                        produccion=resultado["produccion"],
                        unidades_vendidas=resultado["unidades_vendidas"],
                        inventario=resultado["inventario"],
                        precio_final=resultado["precio_final"],
                        precio_promedio=resultado["precio_promedio"],
                        costo_transferencia=resultado["costo_transferencia"],
                        ingresos=resultado["ingresos"],
                        costo_productos_vendidos=resultado["costo_productos_vendidos"],
                        costo_inventario=resultado["costo_inventario"],
                        publicidad=resultado["publicidad"],
                        contribucion_bruta_marketing=resultado["contribucion_bruta_marketing"],
                        porcion_mercado=resultado["porcion_mercado"],
                    )
                    session.add(rm)
                    session.flush()

                    for canal in resultado["por_canal"]:
                        if canal["canal_id"] is None:
                            continue
                        session.add(ReporteMarcaCanal(
                            reporte_marca_id=rm.id,
                            canal_id=canal["canal_id"],
                            vendedores=canal["vendedores"],
                            detallistas=canal["detallistas"],
                            ventas_unidades=canal["ventas_unidades"],
                        ))

                    for segmento in resultado["por_segmento"]:
                        if segmento["segmento_id"] is None:
                            continue
                        session.add(ReporteMarcaSegmento(
                            reporte_marca_id=rm.id,
                            segmento_id=segmento["segmento_id"],
                            ventas_unidades=segmento["ventas_unidades"],
                            porcion_mercado=segmento["porcion_mercado"],
                        ))

                # Estado de las marcas para el próximo período.
                for marca in marcas:
                    datos = next(
                        (d for d in marcas_data
                         if d["equipo_id"] == eq.id and d["nombre"] == marca.nombre),
                        None,
                    )
                    if not datos:
                        continue
                    marca.precio_actual = datos["precio"]
                    marca.publicidad_actual = datos["publicidad"]
                    marca.produccion_actual = datos["produccion"]
                    marca.calidad_actual = datos["calidad"]

                    for canal in canales:
                        historial = session.query(FuerzaVentas).filter_by(
                            marca_id=marca.id, canal_id=canal.id
                        ).order_by(FuerzaVentas.anio.desc()).all()
                        vendedores = datos["vendedores"].get(canal.id, 0)
                        detallistas = datos["detallistas"].get(canal.id, 0)
                        if historial:
                            existente = next(
                                (f for f in historial if f.anio == siguiente_anio), None
                            )
                            if existente:
                                existente.vendedores = vendedores
                                existente.detallistas = detallistas
                            else:
                                session.add(FuerzaVentas(
                                    marca_id=marca.id, canal_id=canal.id,
                                    vendedores=vendedores, detallistas=detallistas,
                                    anio=siguiente_anio,
                                ))
                        else:
                            session.add(FuerzaVentas(
                                marca_id=marca.id, canal_id=canal.id,
                                vendedores=vendedores, detallistas=detallistas,
                                anio=siguiente_anio,
                            ))

                eq.presupuesto_actual = round(presupuesto, 2)
                eq.ya_decidio = False
                eq.fecha_decision = None

                resumen_equipos.append({
                    "equipo_id": eq.id,
                    "numero": eq.numero,
                    "nombre": eq.nombre_empresa or f"Empresa {eq.numero}",
                    "tuvo_decision": eq.id in decisiones,
                    "marcas": len(resultados),
                    "contribucion_neta": round(neta, 2),
                    "presupuesto": round(presupuesto, 2),
                })

            estudios_generados = SimulacionService._generar_datos_estudios(
                session, industria_id, equipos, anio_actual
            )

            # Evaluación de los proyectos de I&D iniciados este año. El
            # resultado queda disponible para aplicarse en la próxima hoja.
            proyectos_evaluados = ProyectoService.evaluar_proyectos(
                session, industria, equipos, anio_actual
            )

            industria.anio_actual = siguiente_anio
            if siguiente_anio >= anio_maximo:
                industria.estado = "finalizada"
            elif industria.estado == "inicializada":
                industria.estado = "en_curso"

            session.add(LogActividad(
                usuario_id=usuario_id,
                accion="procesar_ronda",
                detalle=(
                    f"Industria {industria.id}: período {anio_actual} → "
                    f"reporte {siguiente_anio}, {len(marcas_data)} marcas"
                )[:255],
            ))

            session.commit()

            return {
                "ok": True,
                "anio_procesado": anio_actual,
                "siguiente_anio": siguiente_anio,
                "total_equipos": len(equipos),
                "total_marcas": len(marcas_data),
                "mercado_total": salida["mercado_total"],
                "factor_mercado": salida["factor_mercado"],
                "equipos_sin_decision": sin_decision,
                "estudios_generados": estudios_generados,
                "proyectos": proyectos_evaluados,
                "proyectos_aplicados": proyectos_aplicados,
                "equipos": resumen_equipos,
                "finalizada": industria.estado == "finalizada",
            }

        except Exception as e:
            session.rollback()
            return {"error": str(e)}
        finally:
            session.close()

    # ------------------------------------------------------------------
    # Preparación de datos
    # ------------------------------------------------------------------
    @staticmethod
    def _datos_marca(session, equipo, marca, decision, anio, canales):
        """Combina estado de la marca, decisión efectiva e historial."""
        precio = float(marca.precio_actual or 0)
        publicidad = float(marca.publicidad_actual or 0)
        produccion = float(marca.produccion_actual or 0)
        investigacion = float(marca.investigacion_actual or 0)
        vendedores = {}
        detallistas = {}
        objetivo_x = None
        objetivo_y = None

        if decision:
            dm = session.query(DecisionMarca).filter_by(
                decision_id=decision.id, marca_nombre=marca.nombre
            ).first()
            if dm:
                precio = float(dm.precio_venta or precio)
                publicidad = float(dm.presupuesto_publicitario or publicidad)
                produccion = float(dm.produccion or produccion)
                objetivo_x = dm.objetivo_perceptual_x
                objetivo_y = dm.objetivo_perceptual_y
                for dv in dm.vendedores:
                    vendedores[dv.canal_id] = int(dv.vendedores or 0)

        if not vendedores:
            for canal in canales:
                fila = session.query(FuerzaVentas).filter_by(
                    marca_id=marca.id, canal_id=canal.id
                ).order_by(FuerzaVentas.anio.desc()).first()
                if fila:
                    vendedores[canal.id] = int(fila.vendedores or 0)
                    detallistas[canal.id] = int(fila.detallistas or 0)
                else:
                    vendedores[canal.id] = 0
                    detallistas[canal.id] = 0
        else:
            for canal in canales:
                if canal.id not in vendedores:
                    vendedores[canal.id] = 0
                fila = session.query(FuerzaVentas).filter_by(
                    marca_id=marca.id, canal_id=canal.id
                ).order_by(FuerzaVentas.anio.desc()).first()
                detallistas[canal.id] = int(fila.detallistas or 0) if fila else 0

        inventario = 0.0
        if anio > 0:
            previo = session.query(ReporteMarca).join(Reporte).filter(
                Reporte.equipo_id == equipo.id,
                Reporte.anio == anio,
                ReporteMarca.marca_nombre == marca.nombre,
            ).first()
            if previo:
                inventario = float(previo.inventario or 0)

        return {
            "nombre": marca.nombre,
            "equipo_id": equipo.id,
            "tipo": marca.tipo,
            "precio": precio,
            "publicidad": publicidad,
            "investigacion": investigacion,
            "produccion": produccion,
            "inventario": inventario,
            "calidad": float(marca.calidad_actual or 50),
            "costo_unitario": float(marca.costo_unitario or 0),
            "vendedores": vendedores,
            "detallistas": detallistas,
            "objetivo_perceptual_x": objetivo_x,
            "objetivo_perceptual_y": objetivo_y,
        }

    # ------------------------------------------------------------------
    # Estudios de mercado
    # ------------------------------------------------------------------
    @staticmethod
    def _generar_datos_estudios(session, industria_id, equipos, anio):
        """Genera y guarda los datos de los estudios comprados en el período."""
        from core.models import (
            EstudioAwareness, EstudioIntencion, EstudioPanelConsumidores,
            EstudioPanelDistribuidores, EstudioEscala, EstudioMapa,
            EstudioPronostico, EstudioPublicidadCompetencia,
            EstudioFuerzaVentasCompetencia, EstudioResultado, AtributoFisico,
        )
        from core.generador_estudios import GeneradorEstudios

        segmentos = session.query(Segmento).filter_by(
            industria_id=industria_id
        ).order_by(Segmento.numero).all()
        canales = session.query(Canal).filter_by(
            industria_id=industria_id
        ).order_by(Canal.numero).all()

        segmentos_data = [{
            "id": s.id, "numero": s.numero, "peso": s.peso,
            "valor_ideal_x": s.valor_ideal_x, "valor_ideal_y": s.valor_ideal_y,
        } for s in segmentos]
        canales_data = [{
            "id": c.id, "numero": c.numero, "nombre": c.nombre,
            "total_distribuidores": c.total_distribuidores,
        } for c in canales]

        todas_marcas = []
        for eq in equipos:
            for m in session.query(Marca).filter_by(
                equipo_id=eq.id, activa=True
            ).all():
                atributos = session.query(AtributoFisico).filter_by(
                    marca_id=m.id, anio=anio
                ).order_by(AtributoFisico.numero).all()
                if not atributos:
                    atributos = session.query(AtributoFisico).filter_by(
                        marca_id=m.id
                    ).order_by(AtributoFisico.anio.desc(), AtributoFisico.numero).all()
                todas_marcas.append({
                    "nombre": m.nombre,
                    "equipo_id": eq.id,
                    "precio": float(m.precio_actual or 0),
                    "publicidad": float(m.publicidad_actual or 0),
                    "produccion": float(m.produccion_actual or 0),
                    "posicion_x": 0,
                    "posicion_y": 0,
                    "atributos": [float(a.valor or 0) for a in atributos],
                })

        generador = GeneradorEstudios(todas_marcas, segmentos_data, canales_data, anio)
        generados = 0

        for eq in equipos:
            compras = session.query(CompraEstudio).filter_by(
                equipo_id=eq.id, anio=anio
            ).all()

            for compra in compras:
                estudio = session.query(EstudioMercado).filter_by(
                    id=compra.estudio_id
                ).first()
                if not estudio:
                    continue

                # Regeneración limpia: evita duplicados si se reprocesa.
                for modelo in (
                    EstudioAwareness, EstudioIntencion, EstudioPanelConsumidores,
                    EstudioPanelDistribuidores, EstudioEscala, EstudioMapa,
                    EstudioPronostico, EstudioPublicidadCompetencia,
                    EstudioFuerzaVentasCompetencia, EstudioResultado,
                ):
                    session.query(modelo).filter_by(compra_id=compra.id).delete()

                datos = generador.generar_estudio(estudio.numero)

                for item in datos.get("awareness", []):
                    session.add(EstudioAwareness(
                        compra_id=compra.id,
                        marca_nombre=item["marca"],
                        awareness=item["awareness"],
                    ))

                for item in datos.get("intenciones", []):
                    seg = next(
                        (s for s in segmentos if s.numero == item["segmento"]), None
                    )
                    if seg:
                        session.add(EstudioIntencion(
                            compra_id=compra.id,
                            marca_nombre=item["marca"],
                            segmento_id=seg.id,
                            intencion=item["intencion"],
                        ))

                for item in datos.get("habitos", []):
                    session.add(EstudioResultado(
                        compra_id=compra.id,
                        categoria="habitos_compra",
                        entidad=f"Segmento {item['segmento']} · Canal {item['canal']}",
                        metrica="porcentaje",
                        valor=item["porcentaje"],
                    ))

                for item in datos.get("panel", []):
                    if "segmento" in item:
                        seg = next(
                            (s for s in segmentos if s.numero == item["segmento"]), None
                        )
                        if seg:
                            session.add(EstudioPanelConsumidores(
                                compra_id=compra.id,
                                marca_nombre=item["marca"],
                                segmento_id=seg.id,
                                porcion_mercado=item["porcion_mercado"],
                                ventas_unidades=item["ventas_unidades"],
                            ))
                    elif "canal" in item:
                        can = next(
                            (c for c in canales if c.numero == item["canal"]), None
                        )
                        if can:
                            session.add(EstudioPanelDistribuidores(
                                compra_id=compra.id,
                                marca_nombre=item["marca"],
                                canal_id=can.id,
                                porcion_mercado=item["porcion_mercado"],
                                ventas_unidades=item["ventas_unidades"],
                            ))

                for item in datos.get("escalas", []):
                    for escala in ("valor", "potencia", "diseno"):
                        session.add(EstudioEscala(
                            compra_id=compra.id,
                            marca_nombre=item["marca"],
                            escala=escala.upper(),
                            valor=item[escala],
                        ))

                for item in datos.get("ideales", []):
                    for metrica in ("valor", "potencia", "diseno"):
                        session.add(EstudioResultado(
                            compra_id=compra.id,
                            categoria="ideales_segmento",
                            entidad=f"Segmento {item['segmento']}",
                            metrica=metrica,
                            valor=item[metrica],
                        ))

                for item in datos.get("marcas", []):
                    session.add(EstudioMapa(
                        compra_id=compra.id,
                        entidad_tipo="MARCA",
                        entidad_nombre=item["marca"],
                        posicion_x=item["posicion_x"],
                        posicion_y=item["posicion_y"],
                    ))
                for item in datos.get("segmentos", []):
                    session.add(EstudioMapa(
                        compra_id=compra.id,
                        entidad_tipo="SEGMENTO",
                        entidad_nombre=f"Segmento {item['segmento']}",
                        posicion_x=item["posicion_x"],
                        posicion_y=item["posicion_y"],
                    ))

                for item in datos.get("pronosticos", []):
                    seg = next(
                        (s for s in segmentos if s.numero == item["segmento"]), None
                    )
                    if seg:
                        session.add(EstudioPronostico(
                            compra_id=compra.id,
                            segmento_id=seg.id,
                            unidades_esperadas=item["unidades_esperadas"],
                        ))

                for item in datos.get("publicidad", []):
                    session.add(EstudioPublicidadCompetencia(
                        compra_id=compra.id,
                        marca_nombre=item["marca"],
                        publicidad_estimada=item["publicidad_estimada"],
                    ))

                for item in datos.get("fuerza_ventas", []):
                    can = next(
                        (c for c in canales if c.numero == item["canal"]), None
                    )
                    if can:
                        session.add(EstudioFuerzaVentasCompetencia(
                            compra_id=compra.id,
                            marca_nombre=item["marca"],
                            canal_id=can.id,
                            vendedores_estimados=item["vendedores_estimados"],
                        ))

                # Experimentos 14/15 y cualquier métrica suelta.
                for item in datos.get("test", []):
                    entidad = item.get("marca") or item.get("entidad") or ""
                    for clave, valor in item.items():
                        if clave in ("marca", "entidad") or not isinstance(valor, (int, float)):
                            continue
                        session.add(EstudioResultado(
                            compra_id=compra.id,
                            categoria="experimento",
                            entidad=str(entidad),
                            metrica=str(clave),
                            valor=float(valor),
                        ))

                generados += 1

        return generados
