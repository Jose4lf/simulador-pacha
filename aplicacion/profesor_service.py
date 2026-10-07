"""
Servicio del Profesor - PACHA (esquema normalizado)
"""
from datetime import datetime
from infraestructura.database import get_session
from core.models import (
    Usuario, Simulador, Industria, Equipo, Marca,
    Segmento, Canal, Decision, Reporte, DecisionMarca,
    EstudioMercado, DecisionEstudio,
)
from core.generador_nombres import generar_nombres_todos_equipos, vocal_equipo


# Configuración por defecto de una industria Markestrated
DEFAULT_SEGMENTOS = [
    {"numero": 1, "nombre": "Segmento 1", "peso": 0.30, "valor_ideal_x": 3.5, "valor_ideal_y": 14.5},
    {"numero": 2, "nombre": "Segmento 2", "peso": 0.18, "valor_ideal_x": -7.7, "valor_ideal_y": 5.5},
    {"numero": 3, "nombre": "Segmento 3", "peso": 0.15, "valor_ideal_x": 13.9, "valor_ideal_y": 11.5},
    {"numero": 4, "nombre": "Segmento 4", "peso": 0.21, "valor_ideal_x": 9.3, "valor_ideal_y": 0.5},
    {"numero": 5, "nombre": "Segmento 5", "peso": 0.16, "valor_ideal_x": -12.7, "valor_ideal_y": -5.3},
]

DEFAULT_CANALES = [
    {"numero": 1, "nombre": "Canal 1", "total_distribuidores": 3000, "margen_promedio": 0.40},
    {"numero": 2, "nombre": "Canal 2", "total_distribuidores": 35000, "margen_promedio": 0.35},
    {"numero": 3, "nombre": "Canal 3", "total_distribuidores": 4000, "margin_promedio": 0.40},
]


class ProfesorService:

    # ============================================================
    # ESTADÍSTICAS
    # ============================================================
    @staticmethod
    def obtener_estadisticas(profesor_id):
        session = get_session()
        try:
            industrias = session.query(Industria).filter_by(profesor_id=profesor_id).all()
            total_equipos = 0
            for ind in industrias:
                total_equipos += session.query(Equipo).filter_by(industria_id=ind.id).count()
            return {
                "total_industrias": len(industrias),
                "total_activas": sum(1 for i in industrias if i.estado == "activa"),
                "total_bloqueadas": sum(1 for i in industrias if i.estado == "bloqueada"),
                "total_equipos": total_equipos,
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
    # INDUSTRIAS
    # ============================================================
    @staticmethod
    def listar_industrias(profesor_id):
        session = get_session()
        try:
            industrias = session.query(Industria).filter_by(
                profesor_id=profesor_id
            ).order_by(Industria.creada.desc()).all()

            resultado = []
            for ind in industrias:
                total_equipos = session.query(Equipo).filter_by(industria_id=ind.id).count()
                equipos_decidieron = session.query(Equipo).filter_by(
                    industria_id=ind.id, ya_decidio=True
                ).count()

                resultado.append({
                    "id": ind.id,
                    "nombre": ind.nombre,
                    "simulador_codigo": ind.simulador_codigo,
                    "anio_actual": ind.anio_actual,
                    "anio_maximo": ind.anio_maximo,
                    "estado": ind.estado,
                    "permitir_envio": ind.permitir_envio,
                    "total_equipos": total_equipos,
                    "equipos_decidieron": equipos_decidieron,
                    "creada": ind.creada.strftime("%d/%m/%Y %H:%M") if ind.creada else "—",
                })
            return resultado
        finally:
            session.close()

    @staticmethod
    def obtener_industria(industria_id):
        session = get_session()
        try:
            ind = session.query(Industria).filter_by(id=industria_id).first()
            if not ind:
                return None

            equipos = session.query(Equipo).filter_by(
                industria_id=ind.id
            ).order_by(Equipo.numero).all()

            return {
                "id": ind.id,
                "nombre": ind.nombre,
                "simulador_codigo": ind.simulador_codigo,
                "anio_actual": ind.anio_actual,
                "anio_maximo": ind.anio_maximo,
                "estado": ind.estado,
                "permitir_envio": ind.permitir_envio,
                "inflacion_anual": ind.inflacion_anual,
                "tipo_cambio_usd": ind.tipo_cambio_usd,
                "crecimiento_pib": ind.crecimiento_pib,
                "presupuesto_inicial": ind.presupuesto_inicial,
                "total_equipos": len(equipos),
                "equipos_decidieron": sum(1 for eq in equipos if eq.ya_decidio),
                "equipos": [{
                    "id": eq.id,
                    "numero": eq.numero,
                    "nombre_empresa": eq.nombre_empresa,
                    "ya_decidio": eq.ya_decidio,
                    "bloqueado": eq.bloqueado,
                    "presupuesto_actual": eq.presupuesto_actual,
                    "marcas": [m.nombre for m in eq.marcas],
                } for eq in equipos],
            }
        finally:
            session.close()

    @staticmethod
    def crear_industria(profesor_id, nombre, num_equipos, codigo_escenario="markestrated"):
        """
        Crea una industria completa con:
        - 5 segmentos
        - 3 canales
        - Equipos con 2 marcas SONITE cada uno (nombres LABSAG)
        """
        session = get_session()
        try:
            # Verificar nombre único
            existente = session.query(Industria).filter_by(nombre=nombre).first()
            if existente:
                return {"error": f"Ya existe una industria con el nombre '{nombre}'"}

            # 1. Crear industria
            ind = Industria(
                nombre=nombre,
                simulador_codigo=codigo_escenario,
                profesor_id=profesor_id,
                anio_actual=0,
                anio_maximo=10,
                estado="inicializada",
                permitir_envio=True,
                inflacion_anual=0.09,
                inflacion_acumulada=0.09,
                tipo_cambio_usd=11.90,
                crecimiento_pib=0.04,
                presupuesto_inicial=10000,
            )
            session.add(ind)
            session.commit()
            session.refresh(ind)

            # 2. Crear 5 segmentos
            for seg in DEFAULT_SEGMENTOS:
                session.add(Segmento(
                    industria_id=ind.id,
                    numero=seg["numero"],
                    nombre=seg["nombre"],
                    peso=seg["peso"],
                    valor_ideal_x=seg["valor_ideal_x"],
                    valor_ideal_y=seg["valor_ideal_y"],
                ))
            session.commit()

            # 3. Crear 3 canales
            for can in DEFAULT_CANALES:
                session.add(Canal(
                    industria_id=ind.id,
                    numero=can["numero"],
                    nombre=can["nombre"],
                    total_distribuidores=can["total_distribuidores"],
                    margen_promedio=can.get("margen_promedio", 0.40),
                ))
            session.commit()

            # 4. Generar nombres LABSAG para todos los equipos
            nombres_por_equipo = generar_nombres_todos_equipos(
                num_equipos, tipo="SONITE", marcas_por_equipo=2
            )

                        # 5. Crear equipos con sus marcas y reporte del Año 0
            for num_equipo in range(1, num_equipos + 1):
                equipo = Equipo(
                    industria_id=ind.id,
                    numero=num_equipo,
                    nombre_empresa=f"Empresa {num_equipo}",
                    presupuesto_actual=10000,
                    ya_decidio=False,
                    bloqueado=False,
                )
                session.add(equipo)
                session.commit()
                session.refresh(equipo)

                # Crear marcas SONITE con nombres LABSAG
                nombres = nombres_por_equipo.get(num_equipo, [])
                marcas_creadas = []
                for idx, nombre_marca in enumerate(nombres):
                    marca = Marca(
                        equipo_id=equipo.id,
                        nombre=nombre_marca,
                        tipo="SONITE",
                        activa=True,
                        anio_lanzamiento=0,
                        precio_actual=300,
                        publicidad_actual=2500,
                        investigacion_actual=0,
                        produccion_actual=100,
                        calidad_actual=50,
                    )
                    session.add(marca)
                    session.commit()
                    session.refresh(marca)
                    marcas_creadas.append(marca)

                # ============================================================
                # CREAR REPORTE INICIAL DEL AÑO 0
                # ============================================================
                from core.models import Reporte, ReporteMarca

                rep_inicial = Reporte(
                    equipo_id=equipo.id,
                    anio=0,
                    mercado_total=1300000,
                    contribucion_bruta_total=0,
                    contribucion_neta_total=0,
                    presupuesto_proximo_periodo=10000,
                    inflacion_aplicada=ind.inflacion_anual,
                    crecimiento_pnb=ind.crecimiento_pib,
                    tipo_cambio=ind.tipo_cambio_usd,
                )
                session.add(rep_inicial)
                session.commit()
                session.refresh(rep_inicial)

                # Crear reporte_marca inicial (con valores del escenario)
                for marca in marcas_creadas:
                    rm = ReporteMarca(
                        reporte_id=rep_inicial.id,
                        marca_nombre=marca.nombre,
                        produccion=100,
                        unidades_vendidas=100,
                        inventario=0,
                        precio_final=300,
                        precio_promedio=300,
                        costo_transferencia=165,
                        ingresos=30000,
                        costo_productos_vendidos=16500,
                        costo_inventario=0,
                        publicidad=2500,
                        contribucion_bruta_marketing=11000,
                        porcion_mercado=100.0 / (num_equipos * 2),
                    )
                    session.add(rm)
                session.commit()

            return {"ok": True, "industria_id": ind.id}
        except Exception as e:
            session.rollback()
            return {"error": str(e)}
        finally:
            session.close()

    @staticmethod
    def eliminar_industria(industria_id):
        session = get_session()
        try:
            ind = session.query(Industria).filter_by(id=industria_id).first()
            if not ind:
                return {"error": "Industria no encontrada"}
            session.delete(ind)
            session.commit()
            return {"ok": True}
        finally:
            session.close()

    @staticmethod
    def toggle_permitir_envio(industria_id):
        session = get_session()
        try:
            ind = session.query(Industria).filter_by(id=industria_id).first()
            if not ind:
                return {"error": "Industria no encontrada"}
            ind.permitir_envio = not ind.permitir_envio
            session.commit()
            return {"ok": True, "permitir_envio": ind.permitir_envio}
        finally:
            session.close()

    # ============================================================
    # DECISIONES
    # ============================================================
    @staticmethod
    def obtener_decisiones_industria(industria_id, anio=None):
        session = get_session()
        try:
            ind = session.query(Industria).filter_by(id=industria_id).first()
            if not ind:
                return None
            if anio is None:
                anio = ind.anio_actual

            equipos = session.query(Equipo).filter_by(
                industria_id=industria_id
            ).order_by(Equipo.numero).all()

            resultado = []
            for eq in equipos:
                dec = session.query(Decision).filter_by(
                    equipo_id=eq.id, anio=anio
                ).first()

                resultado.append({
                    "equipo_id": eq.id,
                    "numero": eq.numero,
                    "nombre_empresa": eq.nombre_empresa,
                    "ya_decidio": eq.ya_decidio,
                    "bloqueado": eq.bloqueado,
                    "fecha_decision": eq.fecha_decision.strftime("%d/%m/%Y %H:%M") if eq.fecha_decision else None,
                    "datos": {"marcas": [m.marca_nombre for m in dec.marcas]} if dec else None,
                })

            return {
                "industria_id": ind.id,
                "anio": anio,
                "industria_nombre": ind.nombre,
                "equipos": resultado,
                "total_equipos": len(resultado),
                "equipos_decidieron": sum(1 for e in resultado if e["ya_decidio"]),
            }
        finally:
            session.close()

    # ============================================================
    # RESULTADOS
    # ============================================================
    @staticmethod
    def obtener_resultados(industria_id, anio=None):
        session = get_session()
        try:
            ind = session.query(Industria).filter_by(id=industria_id).first()
            if not ind:
                return None
            if anio is None:
                anio = ind.anio_actual

            equipos = session.query(Equipo).filter_by(
                industria_id=industria_id
            ).order_by(Equipo.numero).all()

            resultado = []
            for eq in equipos:
                reporte = session.query(Reporte).filter_by(
                    equipo_id=eq.id, anio=anio
                ).first()

                marcas_data = []
                if reporte:
                    for rm in reporte.marcas:
                        marcas_data.append({
                            "marca": rm.marca_nombre,
                            "produccion": rm.produccion,
                            "unidades_vendidas": rm.unidades_vendidas,
                            "inventario": rm.inventario,
                            "precio_final": rm.precio_final,
                            "publicidad": rm.publicidad,
                            "contribucion_bruta_marketing": rm.contribucion_bruta_marketing,
                            "porcion_mercado": rm.porcion_mercado,
                        })

                resultado.append({
                    "equipo_id": eq.id,
                    "numero": eq.numero,
                    "nombre_empresa": eq.nombre_empresa,
                    "marcas": marcas_data,
                })

            return {
                "industria_id": ind.id,
                "anio": anio,
                "industria_nombre": ind.nombre,
                "equipos": resultado,
            }
        finally:
            session.close()

    # ============================================================
    # IMPORTAR ALUMNOS CSV
    # ============================================================
    @staticmethod
    def importar_alumnos_csv(industria_id, contenido_csv):
        import csv
        from io import StringIO
        from werkzeug.security import generate_password_hash

        session = get_session()
        resultado = {"creados": [], "errores": [], "total_filas": 0}

        try:
            ind = session.query(Industria).filter_by(id=industria_id).first()
            if not ind:
                return {"error": "Industria no encontrada"}

            reader = csv.DictReader(StringIO(contenido_csv))
            filas = list(reader)
            resultado["total_filas"] = len(filas)

            for i, fila in enumerate(filas, start=2):
                try:
                    equipo_num_str = (fila.get("equipo_numero") or "").strip()
                    numero_alumno_str = (fila.get("numero_alumno") or "").strip()
                    nombre = (fila.get("nombre") or "").strip()
                    email = (fila.get("email") or "").strip()

                    if not equipo_num_str or not nombre or not email:
                        resultado["errores"].append(f"Fila {i}: faltan datos")
                        continue

                    try:
                        equipo_num = int(equipo_num_str)
                        numero_alumno = int(numero_alumno_str)
                    except ValueError:
                        resultado["errores"].append(f"Fila {i}: equipo_numero o numero_alumno no son números")
                        continue

                    equipo = session.query(Equipo).filter_by(
                        industria_id=industria_id, numero=equipo_num
                    ).first()

                    if not equipo:
                        resultado["errores"].append(f"Fila {i}: equipo {equipo_num} no existe")
                        continue

                    # Username desde email
                    username_base = email.split("@")[0].lower().replace(".", "_").replace("-", "_")
                    username = username_base
                    contador = 1
                    while session.query(Usuario).filter_by(username=username).first():
                        username = f"{username_base}{contador}"
                        contador += 1

                    es_representante = (numero_alumno == 1)

                    alumno = Usuario(
                        username=username,
                        password_hash=generate_password_hash("alumno123"),
                        rol="alumno",
                        nombre=nombre,
                        email=email,
                        activo=True,
                        bloqueado=False,
                        equipo_id=equipo.id,
                        es_representante=es_representante,
                    )
                    session.add(alumno)
                    session.commit()

                    resultado["creados"].append({
                        "username": username,
                        "nombre": nombre,
                        "email": email,
                        "equipo": equipo_num,
                        "representante": es_representante,
                    })

                except Exception as e:
                    session.rollback()
                    resultado["errores"].append(f"Fila {i}: {str(e)}")

            return resultado
        except Exception as e:
            session.rollback()
            return {"error": f"Error: {str(e)}"}
        finally:
            session.close()

    # ============================================================
    # EXPORTAR CSV
    # ============================================================
    @staticmethod
    def exportar_resultados_csv(industria_id, anio):
        import csv
        from io import StringIO

        session = get_session()
        try:
            ind = session.query(Industria).filter_by(id=industria_id).first()
            if not ind:
                return None

            equipos = session.query(Equipo).filter_by(
                industria_id=industria_id
            ).order_by(Equipo.numero).all()

            output = StringIO()
            writer = csv.writer(output)
            writer.writerow([
                "Año", "Equipo", "Marca", "Producción", "Ventas",
                "Inventario", "Precio Final", "Publicidad",
                "Contribución Bruta", "Porción Mercado"
            ])

            for eq in equipos:
                reporte = session.query(Reporte).filter_by(
                    equipo_id=eq.id, anio=anio
                ).first()

                if reporte:
                    for rm in reporte.marcas:
                        writer.writerow([
                            anio,
                            f"Equipo {eq.numero}",
                            rm.marca_nombre,
                            f"{rm.produccion:.0f}",
                            f"{rm.unidades_vendidas:.0f}",
                            f"{rm.inventario:.0f}",
                            f"{rm.precio_final:.2f}",
                            f"{rm.publicidad:.0f}",
                            f"{rm.contribucion_bruta_marketing:.0f}",
                            f"{rm.porcion_mercado:.2f}%",
                        ])

            output.seek(0)
            return output.getvalue()
        finally:
            session.close()