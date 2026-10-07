"""
Servicio de simulación - PACHA
Orquesta el motor con la BD normalizada.
"""
from infraestructura.database import get_session
from core.models import (
    Industria, Equipo, Marca, Decision, DecisionMarca,
    Reporte, ReporteMarca, Segmento, Canal,
)
from core.motor_simulacion import MotorSimulacion


class SimulacionService:

    @staticmethod
    def procesar_ronda(industria_id):
        session = get_session()
        try:
            industria = session.query(Industria).filter_by(id=industria_id).first()
            if not industria:
                return {"error": "Industria no encontrada"}

            anio_actual = industria.anio_actual
            equipos = session.query(Equipo).filter_by(industria_id=industria_id).all()

            if not equipos:
                return {"error": "No hay equipos"}

            # Preparar datos de marcas
            marcas_data = []
            mapa_marcas = {}

            for eq in equipos:
                marcas = session.query(Marca).filter_by(equipo_id=eq.id, activa=True).all()
                for m in marcas:
                    # Buscar decisión del equipo
                    dec = session.query(Decision).filter_by(
                        equipo_id=eq.id, anio=anio_actual
                    ).first()

                    precio = m.precio_actual
                    publicidad = m.publicidad_actual
                    investigacion = m.investigacion_actual
                    produccion = m.produccion_actual

                    if dec:
                        dm = session.query(DecisionMarca).filter_by(
                            decision_id=dec.id, marca_nombre=m.nombre
                        ).first()
                        if dm:
                            precio = dm.precio_venta
                            publicidad = dm.presupuesto_publicitario
                            produccion = dm.produccion

                    marcas_data.append({
                        "nombre": m.nombre,
                        "equipo_id": eq.id,
                        "tipo": m.tipo,
                        "precio": precio,
                        "publicidad": publicidad,
                        "investigacion": investigacion,
                        "produccion": produccion,
                        "vendedores_canal1": 20,
                        "vendedores_canal2": 15,
                        "vendedores_canal3": 30,
                        "detallistas_canal1": 0,
                        "detallistas_canal2": 0,
                    })
                    mapa_marcas[m.nombre] = eq.id

            # Obtener segmentos y canales
            segmentos = [{
                "id": s.id, "numero": s.numero, "peso": s.peso,
                "valor_ideal_x": s.valor_ideal_x, "valor_ideal_y": s.valor_ideal_y,
            } for s in session.query(Segmento).filter_by(industria_id=industria_id).all()]

            canales = [{
                "id": c.id, "numero": c.numero,
                "total_distribuidores": c.total_distribuidores,
                "margen_promedio": c.margen_promedio,
            } for c in session.query(Canal).filter_by(industria_id=industria_id).all()]

            # Ejecutar motor
            config = {
                "mercado_total": 1300000,
                "inflacion_anual": industria.inflacion_anual,
                "crecimiento_pib": industria.crecimiento_pib,
            }
            motor = MotorSimulacion(config)
            resultado = motor.simular_ronda(marcas_data, segmentos, canales, anio_actual)

            # Guardar reportes por equipo
            siguiente_anio = anio_actual + 1

            for eq in equipos:
                # Filtrar resultados del equipo
                resultados_eq = [r for r in resultado["resultados"] if r["equipo_id"] == eq.id]

                # Buscar o crear reporte
                rep = session.query(Reporte).filter_by(
                    equipo_id=eq.id, anio=siguiente_anio
                ).first()

                if rep:
                    # Eliminar marcas anteriores
                    for rm in rep.marcas:
                        session.delete(rm)
                    session.commit()
                else:
                    rep = Reporte(equipo_id=eq.id, anio=siguiente_anio)
                    session.add(rep)
                    session.commit()
                    session.refresh(rep)

                # Actualizar datos del reporte
                rep.mercado_total = resultado["mercado_total"]
                contrib_bruta = sum(r["contribucion_bruta_marketing"] for r in resultados_eq)
                rep.contribucion_bruta_total = contrib_bruta
                rep.contribucion_neta_total = contrib_bruta * 0.8
                rep.presupuesto_proximo_periodo = max(10000, contrib_bruta * 0.3)
                rep.inflacion_aplicada = industria.inflacion_anual
                rep.crecimiento_pnb = industria.crecimiento_pib
                rep.tipo_cambio = industria.tipo_cambio_usd
                session.commit()

                # Crear reportes de marcas
                for r in resultados_eq:
                    rm = ReporteMarca(
                        reporte_id=rep.id,
                        marca_nombre=r["marca"],
                        produccion=r["produccion"],
                        unidades_vendidas=r["unidades_vendidas"],
                        inventario=r["inventario"],
                        precio_final=r["precio_final"],
                        publicidad=r["publicidad"],
                        contribucion_bruta_marketing=r["contribucion_bruta_marketing"],
                        porcion_mercado=r["porcion_mercado"],
                    )
                    session.add(rm)
                session.commit()

                # Resetear equipo
                eq.ya_decidio = False
                eq.fecha_decision = None

            # Actualizar industria
            industria.anio_actual = siguiente_anio
            if siguiente_anio >= industria.anio_maximo:
                industria.estado = "finalizada"
            session.commit()

            return {
                "ok": True,
                "anio_procesado": anio_actual,
                "siguiente_anio": siguiente_anio,
                "total_equipos": len(equipos),
                "total_marcas": len(marcas_data),
                "mercado_total": resultado["mercado_total"],
            }

        except Exception as e:
            session.rollback()
            return {"error": str(e)}
        finally:
            session.close()
    @staticmethod
    def _generar_datos_estudios(session, industria_id, equipos, anio):
        """Genera y guarda los datos de los estudios comprados."""
        from core.models import (
            CompraEstudio, EstudioMercado, Segmento, Canal, Marca,
            EstudioAwareness, EstudioIntencion, EstudioPanelConsumidores,
            EstudioPanelDistribuidores, EstudioEscala, EstudioMapa,
            EstudioPronostico, EstudioPublicidadCompetencia,
            EstudioFuerzaVentasCompetencia,
        )
        from core.generador_estudios import GeneradorEstudios

        # Obtener segmentos y canales
        segmentos = session.query(Segmento).filter_by(industria_id=industria_id).order_by(Segmento.numero).all()
        canales = session.query(Canal).filter_by(industria_id=industria_id).order_by(Canal.numero).all()

        segmentos_data = [{
            "id": s.id, "numero": s.numero, "peso": s.peso,
            "valor_ideal_x": s.valor_ideal_x, "valor_ideal_y": s.valor_ideal_y,
        } for s in segmentos]

        canales_data = [{
            "id": c.id, "numero": c.numero, "nombre": c.nombre,
            "total_distribuidores": c.total_distribuidores,
        } for c in canales]

        # Todas las marcas de la industria
        todas_marcas = []
        for eq in equipos:
            for m in session.query(Marca).filter_by(equipo_id=eq.id, activa=True).all():
                todas_marcas.append({
                    "nombre": m.nombre,
                    "equipo_id": eq.id,
                    "precio": m.precio_actual,
                    "publicidad": m.publicidad_actual,
                    "produccion": m.produccion_actual,
                    "posicion_x": 0,
                    "posicion_y": 0,
                })

        # Generador
        generador = GeneradorEstudios(todas_marcas, segmentos_data, canales_data, anio)

        # Para cada equipo, generar datos de sus estudios comprados
        for eq in equipos:
            compras = session.query(CompraEstudio).filter_by(
                equipo_id=eq.id, anio=anio
            ).all()

            for compra in compras:
                estudio = session.query(EstudioMercado).filter_by(id=compra.estudio_id).first()
                if not estudio:
                    continue

                datos = generador.generar_estudio(estudio.numero)

                # Guardar según el tipo de estudio
                if "awareness" in datos:
                    for item in datos["awareness"]:
                        session.add(EstudioAwareness(
                            compra_id=compra.id,
                            marca_nombre=item["marca"],
                            awareness=item["awareness"],
                        ))
                    for item in datos.get("intenciones", []):
                        seg = next((s for s in segmentos if s.numero == item["segmento"]), None)
                        if seg:
                            session.add(EstudioIntencion(
                                compra_id=compra.id,
                                marca_nombre=item["marca"],
                                segmento_id=seg.id,
                                intencion=item["intencion"],
                            ))

                if "panel" in datos and "porcion_mercado" in datos["panel"][0] if datos["panel"] else False:
                    for item in datos["panel"]:
                        if "segmento" in item:
                            seg = next((s for s in segmentos if s.numero == item["segmento"]), None)
                            if seg:
                                session.add(EstudioPanelConsumidores(
                                    compra_id=compra.id,
                                    marca_nombre=item["marca"],
                                    segmento_id=seg.id,
                                    porcion_mercado=item["porcion_mercado"],
                                    ventas_unidades=item["ventas_unidades"],
                                ))
                        elif "canal" in item:
                            can = next((c for c in canales if c.numero == item["canal"]), None)
                            if can:
                                session.add(EstudioPanelDistribuidores(
                                    compra_id=compra.id,
                                    marca_nombre=item["marca"],
                                    canal_id=can.id,
                                    porcion_mercado=item["porcion_mercado"],
                                    ventas_unidades=item["ventas_unidades"],
                                ))

                if "escalas" in datos:
                    for item in datos["escalas"]:
                        for escala in ["valor", "potencia", "diseno"]:
                            session.add(EstudioEscala(
                                compra_id=compra.id,
                                marca_nombre=item["marca"],
                                escala=escala.upper(),
                                valor=item[escala],
                            ))

                if "marcas" in datos and "segmentos" in datos:
                    for item in datos["marcas"]:
                        session.add(EstudioMapa(
                            compra_id=compra.id,
                            entidad_tipo="MARCA",
                            entidad_nombre=item["marca"],
                            posicion_x=item["posicion_x"],
                            posicion_y=item["posicion_y"],
                        ))
                    for item in datos["segmentos"]:
                        session.add(EstudioMapa(
                            compra_id=compra.id,
                            entidad_tipo="SEGMENTO",
                            entidad_nombre=f"Segmento {item['segmento']}",
                            posicion_x=item["posicion_x"],
                            posicion_y=item["posicion_y"],
                        ))

                if "pronosticos" in datos:
                    for item in datos["pronosticos"]:
                        seg = next((s for s in segmentos if s.numero == item["segmento"]), None)
                        if seg:
                            session.add(EstudioPronostico(
                                compra_id=compra.id,
                                segmento_id=seg.id,
                                unidades_esperadas=item["unidades_esperadas"],
                            ))

                if "publicidad" in datos:
                    for item in datos["publicidad"]:
                        session.add(EstudioPublicidadCompetencia(
                            compra_id=compra.id,
                            marca_nombre=item["marca"],
                            publicidad_estimada=item["publicidad_estimada"],
                        ))

                if "fuerza_ventas" in datos:
                    for item in datos["fuerza_ventas"]:
                        can = next((c for c in canales if c.numero == item["canal"]), None)
                        if can:
                            session.add(EstudioFuerzaVentasCompetencia(
                                compra_id=compra.id,
                                marca_nombre=item["marca"],
                                canal_id=can.id,
                                vendedores_estimados=item["vendedores_estimados"],
                            ))

                session.commit()