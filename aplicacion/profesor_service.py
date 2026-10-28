
from datetime import datetime
from infraestructura.database import get_session
from core.models import (
    Usuario, Simulador, Industria, Equipo, Marca,
    Segmento, Canal, Decision, Reporte, ReporteMarca, 
    DecisionMarca, EstudioMercado, DecisionEstudio,
    ReporteMarcaCanal, FuerzaVentas, AtributoFisico
)
from core.generador_nombres import generar_nombres_todos_equipos
from infraestructura.seguridad import (
    generar_password_temporal, hashear_password,
)

from infraestructura.database import get_session
from core.models import (
    Industria, Equipo, Marca, Decision, DecisionMarca,
    Reporte, ReporteMarca, Segmento, Canal,
    AtributoFisico, ReporteMarcaCanal, FuerzaVentas,
)
from core.motor_simulacion import MotorSimulacion
from core.reportes_anio0 import generar_reporte_anio0

# ============================================================
# CONFIGURACIÓN BASE
# ============================================================
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
    {"numero": 3, "nombre": "Canal 3", "total_distribuidores": 4000, "margen_promedio": 0.40}, 
]

PERFILES_MARKETING = {
    1: {"porciones": [0.11, 0.04], "fv_canales": [5, 42, 18], "dist_canales": [504, 16115, 1440]},
    2: {"porciones": [0.08, 0.06], "fv_canales": [10, 20, 5], "dist_canales": [400, 12000, 1000]},
    3: {"porciones": [0.15, 0.10], "fv_canales": [50, 100, 20], "dist_canales": [600, 20000, 2000]},
    4: {"porciones": [0.20, 0.15], "fv_canales": [10, 15, 2], "dist_canales": [800, 25000, 3000]},
    5: {"porciones": [0.05, 0.02], "fv_canales": [2, 5, 1], "dist_canales": [200, 5000, 500]},
}

# 👇 NUEVO: Atributos Físicos del Cuadro 1 (Peso, Diseño, Volumen, Frec, Potencia, Costo)
ATRIBUTOS_FISICOS_INICIALES = {
    1: {0: [11, 9, 20, 25, 10, 100], 1: [12, 9, 37, 25, 30, 125]}, # SAKA, SATO
    2: {0: [18, 7, 51, 30, 85, 160], 1: [14, 5, 65, 40, 90, 200]}, # SERI, SEFA
    3: {0: [10, 3, 50, 20, 10, 50], 1: [11, 9, 35, 25, 20, 100]},  # SIMO, SICA
    4: {0: [17, 7, 50, 30, 70, 163], 1: [10, 3, 70, 20, 90, 180]}, # SOTO, SOLO
    5: {0: [10, 3, 50, 25, 20, 70], 1: [15, 6, 40, 20, 70, 175]},  # SUXI, SUTE
}


class ProfesorService:

    @staticmethod
    def obtener_estadisticas(profesor_id):
        session = get_session()
        try:
            industrias = session.query(Industria).filter_by(profesor_id=profesor_id).all()
            total_equipos = session.query(Equipo).join(Industria).filter(Industria.profesor_id == profesor_id).count()
            return {
                "total_industrias": len(industrias),
                "total_activas": sum(1 for i in industrias if i.estado == "activa"),
                "total_bloqueadas": sum(1 for i in industrias if i.estado == "bloqueada"),
                "total_equipos": total_equipos,
            }
        finally:
            session.close()

    @staticmethod
    def listar_simuladores():
        session = get_session()
        try:
            simuladores = session.query(Simulador).order_by(Simulador.orden).all()
            return [{"id": s.id, "codigo": s.codigo, "nombre": s.nombre, "descripcion": s.descripcion or "", "estado": s.estado} for s in simuladores]
        finally:
            session.close()

    @staticmethod
    def listar_industrias(profesor_id):
        session = get_session()
        try:
            industrias = session.query(Industria).filter_by(profesor_id=profesor_id).order_by(Industria.creada.desc()).all()
            resultado = []
            for ind in industrias:
                total_equipos = session.query(Equipo).filter_by(industria_id=ind.id).count()
                equipos_decidieron = session.query(Decision).join(
                    Equipo, Decision.equipo_id == Equipo.id
                ).filter(
                    Equipo.industria_id == ind.id,
                    Decision.anio == int(ind.anio_actual or 0),
                    Decision.estado == "enviada",
                ).count()
                resultado.append({
                    "id": ind.id, "nombre": ind.nombre, "simulador_codigo": ind.simulador_codigo,
                    "anio_actual": ind.anio_actual, "anio_maximo": ind.anio_maximo, "estado": ind.estado,
                    "permitir_envio": ind.permitir_envio, "total_equipos": total_equipos,
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
            if not ind: return None
            equipos = session.query(Equipo).filter_by(industria_id=ind.id).order_by(Equipo.numero).all()
            anio = int(ind.anio_actual or 0)
            decisiones = {
                d.equipo_id: d for d in session.query(Decision).filter(
                    Decision.equipo_id.in_([e.id for e in equipos]),
                    Decision.anio == anio,
                    Decision.estado == "enviada",
                ).all()
            } if equipos else {}
            return {
                "id": ind.id, "nombre": ind.nombre, "simulador_codigo": ind.simulador_codigo,
                "anio_actual": anio, "anio_maximo": ind.anio_maximo, "estado": ind.estado,
                "permitir_envio": ind.permitir_envio, "inflacion_anual": ind.inflacion_anual,
                "tipo_cambio_usd": ind.tipo_cambio_usd, "crecimiento_pib": ind.crecimiento_pib,
                "presupuesto_inicial": ind.presupuesto_inicial, "total_equipos": len(equipos),
                "equipos_decidieron": len(decisiones),
                "equipos": [{
                    "id": eq.id, "numero": eq.numero, "nombre_empresa": eq.nombre_empresa,
                    "ya_decidio": eq.id in decisiones, "bloqueado": eq.bloqueado,
                    "estado_decision": (decisiones[eq.id].estado if eq.id in decisiones else None),
                    "presupuesto_actual": eq.presupuesto_actual, "marcas": [m.nombre for m in eq.marcas],
                } for eq in equipos],
            }
        finally:
            session.close()

    @staticmethod
    def crear_industria(profesor_id, nombre, num_equipos, codigo_escenario="markestrated"):
        session = get_session()
        try:
            if session.query(Industria).filter_by(nombre=nombre).first():
                return {"error": f"Ya existe una industria con el nombre '{nombre}'"}

            # 1. Crear Industria Base
            ind = Industria(
                nombre=nombre, simulador_codigo=codigo_escenario, profesor_id=profesor_id,
                anio_actual=0, anio_maximo=10, estado="inicializada", permitir_envio=True,
                inflacion_anual=0.09, inflacion_acumulada=0.09, tipo_cambio_usd=11.90,
                crecimiento_pib=0.04, presupuesto_inicial=10000,
            )
            session.add(ind)
            session.flush()

            # 2. Crear Segmentos y Canales
            for seg in DEFAULT_SEGMENTOS:
                session.add(Segmento(industria_id=ind.id, numero=seg["numero"], nombre=seg["nombre"], peso=seg["peso"], valor_ideal_x=seg["valor_ideal_x"], valor_ideal_y=seg["valor_ideal_y"]))
            for can in DEFAULT_CANALES:
                session.add(Canal(industria_id=ind.id, numero=can["numero"], nombre=can["nombre"], total_distribuidores=can["total_distribuidores"], margen_promedio=can["margen_promedio"]))
            session.flush()

            # 3. Generar nombres
            nombres_por_equipo = generar_nombres_todos_equipos(num_equipos, tipo="SONITE", marcas_por_equipo=2)

            # 4. Crear Equipos, Marcas, Reportes y Marketing
            for num_equipo in range(1, num_equipos + 1):
                equipo = Equipo(industria_id=ind.id, numero=num_equipo, nombre_empresa=f"Empresa {num_equipo}", presupuesto_actual=10000, ya_decidio=False, bloqueado=False)
                session.add(equipo)
                session.flush()

                marcas_creadas = []
                for idx, nombre_marca in enumerate(nombres_por_equipo.get(num_equipo, [])):
                    marca = Marca(
                        equipo_id=equipo.id, nombre=nombre_marca, tipo="SONITE", activa=True,
                        anio_lanzamiento=0, precio_actual=300, publicidad_actual=2500,
                        investigacion_actual=0, produccion_actual=100, calidad_actual=50,
                        costo_unitario=float(ATRIBUTOS_FISICOS_INICIALES.get(num_equipo, {}).get(idx, [10, 5, 50, 20, 20, 100])[5]),
                    )
                    session.add(marca)
                    session.flush()
                    marcas_creadas.append(marca)

                    # 👇 NUEVO: Guardar Atributos Físicos del Cuadro 1 👇
                    atributos = ATRIBUTOS_FISICOS_INICIALES.get(num_equipo, {}).get(idx, [10, 5, 50, 20, 20, 100])
                    for num_atributo, valor in enumerate(atributos, start=1):
                        session.add(AtributoFisico(
                            marca_id=marca.id,
                            numero=num_atributo,
                            valor=valor,
                            anio=0
                        ))

                perfil_mkt = PERFILES_MARKETING.get(num_equipo, PERFILES_MARKETING[1])

                # Fuerza de ventas inicial (Año 0) por marca y canal.
                canales = session.query(Canal).filter_by(
                    industria_id=ind.id
                ).order_by(Canal.numero).all()
                for idx, marca in enumerate(marcas_creadas):
                    for idx_canal, canal in enumerate(canales):
                        if idx_canal < len(perfil_mkt["dist_canales"]):
                            session.add(FuerzaVentas(
                                marca_id=marca.id, canal_id=canal.id,
                                vendedores=perfil_mkt["fv_canales"][idx_canal],
                                detallistas=perfil_mkt["dist_canales"][idx_canal],
                                anio=0,
                            ))
                session.flush()

                # Reporte de Año 0 con unidades coherentes con el motor.
                rep_inicial = generar_reporte_anio0(session, equipo, ind)
                session.add(rep_inicial)

            session.commit()
            return {"ok": True, "industria_id": ind.id}

        except Exception as e:
            session.rollback()
            return {"error": str(e)}
        finally:
            session.close()
            
    # RESTO DE MÉTODOS (Eliminar, Toggle, Decisiones, Resultados, CSV)
    # ============================================================
    @staticmethod
    def eliminar_industria(industria_id):
        session = get_session()
        try:
            ind = session.query(Industria).filter_by(id=industria_id).first()
            if not ind: return {"error": "Industria no encontrada"}
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
            if not ind: return {"error": "Industria no encontrada"}
            ind.permitir_envio = not ind.permitir_envio
            session.commit()
            return {"ok": True, "permitir_envio": ind.permitir_envio}
        finally:
            session.close()

    @staticmethod
    def obtener_decisiones_industria(industria_id, anio=None):
        session = get_session()
        try:
            ind = session.query(Industria).filter_by(id=industria_id).first()
            if not ind: return None
            if anio is None: anio = ind.anio_actual
            
            equipos = session.query(Equipo).filter_by(industria_id=industria_id).order_by(Equipo.numero).all()
            resultado = []
            for eq in equipos:
                dec = session.query(Decision).filter_by(equipo_id=eq.id, anio=anio).first()
                estado = (dec.estado or "enviada") if dec else None
                resultado.append({
                    "equipo_id": eq.id, "numero": eq.numero, "nombre_empresa": eq.nombre_empresa,
                    "ya_decidio": estado == "enviada", "bloqueado": eq.bloqueado,
                    "estado": estado,
                    "fecha_decision": eq.fecha_decision.strftime("%d/%m/%Y %H:%M") if eq.fecha_decision else None,
                    "datos": {"marcas": [m.marca_nombre for m in dec.marcas]} if dec else None,
                })
            return {"industria_id": ind.id, "anio": anio, "industria_nombre": ind.nombre, "equipos": resultado, "total_equipos": len(resultado), "equipos_decidieron": sum(1 for e in resultado if e["ya_decidio"])}
        finally:
            session.close()

    @staticmethod
    def obtener_resultados(industria_id, anio=None):
        session = get_session()
        try:
            ind = session.query(Industria).filter_by(id=industria_id).first()
            if not ind: return None
            if anio is None: anio = ind.anio_actual
            
            equipos = session.query(Equipo).filter_by(industria_id=industria_id).order_by(Equipo.numero).all()
            resultado = []
            for eq in equipos:
                reporte = session.query(Reporte).filter_by(equipo_id=eq.id, anio=anio).first()
                marcas_data = []
                datos = {
                    "produccion": {}, "precio": {}, "publicidad": {},
                    "investigacion": {}, "ventas": {}, "cuota": {},
                    "beneficio": {}, "inventario": {},
                }
                if reporte:
                    for rm in reporte.marcas:
                        marcas_data.append({
                            "marca": rm.marca_nombre, "produccion": rm.produccion, "unidades_vendidas": rm.unidades_vendidas,
                            "inventario": rm.inventario, "precio_final": rm.precio_final, "publicidad": rm.publicidad,
                            "contribucion_bruta_marketing": rm.contribucion_bruta_marketing, "porcion_mercado": rm.porcion_mercado,
                        })
                        datos["produccion"][rm.marca_nombre] = float(rm.produccion or 0)
                        datos["precio"][rm.marca_nombre] = float(rm.precio_final or 0)
                        datos["publicidad"][rm.marca_nombre] = float(rm.publicidad or 0)
                        marca = session.query(Marca).filter_by(
                            equipo_id=eq.id, nombre=rm.marca_nombre
                        ).first()
                        datos["investigacion"][rm.marca_nombre] = float(
                            marca.investigacion_actual if marca else 0
                        )
                        datos["ventas"][rm.marca_nombre] = float(rm.unidades_vendidas or 0)
                        datos["cuota"][rm.marca_nombre] = float(rm.porcion_mercado or 0)
                        datos["beneficio"][rm.marca_nombre] = float(rm.contribucion_bruta_marketing or 0)
                        datos["inventario"][rm.marca_nombre] = float(rm.inventario or 0)
                resultado.append({"equipo_id": eq.id, "numero": eq.numero, "nombre_empresa": eq.nombre_empresa, "marcas": marcas_data, "datos": datos if marcas_data else None})
            return {"industria_id": ind.id, "anio": anio, "industria_nombre": ind.nombre, "equipos": resultado}
        finally:
            session.close()

    @staticmethod
    def importar_alumnos_csv(industria_id, contenido_csv):
        import csv
        from io import StringIO
        session = get_session()
        resultado = {"creados": [], "errores": [], "total_filas": 0}
        try:
            ind = session.query(Industria).filter_by(id=industria_id).first()
            if not ind: return {"error": "Industria no encontrada"}
            
            reader = csv.DictReader(StringIO(contenido_csv))
            filas = list(reader)
            resultado["total_filas"] = len(filas)

            for i, fila in enumerate(filas, start=2):
                try:
                    equipo_num = int((fila.get("equipo_numero") or "").strip())
                    numero_alumno = int((fila.get("numero_alumno") or "").strip())
                    nombre = (fila.get("nombre") or "").strip()
                    email = (fila.get("email") or "").strip()

                    if not nombre or not email:
                        raise ValueError("nombre y email son obligatorios")

                    equipo = session.query(Equipo).filter_by(industria_id=industria_id, numero=equipo_num).first()
                    if not equipo:
                        raise ValueError(f"el equipo {equipo_num} no existe")

                    username = email.split("@")[0].lower().replace(".", "_").replace("-", "_")
                    if not username:
                        raise ValueError("no se pudo derivar un usuario del email")
                    if session.query(Usuario).filter_by(username=username).first():
                        username = f"{username}{i}"

                    password_temporal = generar_password_temporal()

                    # Savepoint por fila: un error no revierte las filas válidas.
                    with session.begin_nested():
                        alumno = Usuario(
                            username=username,
                            password_hash=hashear_password(password_temporal),
                            debe_cambiar_password=True,
                            rol="alumno", nombre=nombre, email=email,
                            activo=True, bloqueado=False,
                            equipo_id=equipo.id, es_representante=(numero_alumno == 1),
                        )
                        session.add(alumno)
                        session.flush()

                    resultado["creados"].append({
                        "username": username, "nombre": nombre, "email": email,
                        "equipo": equipo_num, "representante": (numero_alumno == 1),
                        "password": password_temporal,
                    })
                except Exception as e:
                    resultado["errores"].append(f"Fila {i}: {str(e)}")
            
            session.commit()
            return resultado
        except Exception as e:
            session.rollback()
            return {"error": f"Error: {str(e)}"}
        finally:
            session.close()

    @staticmethod
    def exportar_resultados_csv(industria_id, anio):
        import csv
        from io import StringIO
        session = get_session()
        try:
            ind = session.query(Industria).filter_by(id=industria_id).first()
            if not ind: return None
            equipos = session.query(Equipo).filter_by(industria_id=industria_id).order_by(Equipo.numero).all()
            output = StringIO()
            writer = csv.writer(output)
            writer.writerow(["Año", "Equipo", "Marca", "Producción", "Ventas", "Inventario", "Precio Final", "Publicidad", "Contribución Bruta", "Porción Mercado"])
            for eq in equipos:
                reporte = session.query(Reporte).filter_by(equipo_id=eq.id, anio=anio).first()
                if reporte:
                    for rm in reporte.marcas:
                        writer.writerow([anio, f"Equipo {eq.numero}", rm.marca_nombre, f"{rm.produccion:.0f}", f"{rm.unidades_vendidas:.0f}", f"{rm.inventario:.0f}", f"{rm.precio_final:.2f}", f"{rm.publicidad:.0f}", f"{rm.contribucion_bruta_marketing:.0f}", f"{rm.porcion_mercado:.2f}%"])
            output.seek(0)
            return output.getvalue()
        finally:
            session.close()

    # ============================================================
    # AISLAMIENTO ENTRE DOCENTES
    # ============================================================
    @staticmethod
    def profesor_posee_industria(profesor_id, industria_id):
        session = get_session()
        try:
            return session.query(Industria.id).filter_by(
                id=industria_id, profesor_id=profesor_id
            ).first() is not None
        finally:
            session.close()

    @staticmethod
    def profesor_posee_equipo(profesor_id, equipo_id):
        session = get_session()
        try:
            return session.query(Equipo.id).join(Industria).filter(
                Equipo.id == equipo_id, Industria.profesor_id == profesor_id
            ).first() is not None
        finally:
            session.close()

    @staticmethod
    def profesor_posee_alumno(profesor_id, alumno_id):
        session = get_session()
        try:
            return session.query(Usuario.id).join(
                Equipo, Usuario.equipo_id == Equipo.id
            ).join(
                Industria, Equipo.industria_id == Industria.id
            ).filter(
                Usuario.id == alumno_id,
                Usuario.rol == "alumno",
                Industria.profesor_id == profesor_id,
            ).first() is not None
        finally:
            session.close()

    # ============================================================
    # GESTIÓN DE ALUMNOS
    # ============================================================
    @staticmethod
    def resetear_password_alumno(profesor_id, alumno_id):
        """Genera una clave temporal solo si el alumno pertenece al profesor."""
        session = get_session()
        try:
            alumno = session.query(Usuario).join(
                Equipo, Usuario.equipo_id == Equipo.id
            ).join(
                Industria, Equipo.industria_id == Industria.id
            ).filter(
                Usuario.id == alumno_id,
                Usuario.rol == "alumno",
                Industria.profesor_id == profesor_id,
            ).first()

            if not alumno:
                return {"error": "Alumno no encontrado"}

            password_temporal = generar_password_temporal()
            alumno.password_hash = hashear_password(password_temporal)
            alumno.debe_cambiar_password = True
            alumno.password_actualizada = datetime.now()
            session.commit()
            return {
                "ok": True,
                "username": alumno.username,
                "nombre": alumno.nombre,
                "nueva_pass": password_temporal,
            }
        except Exception as e:
            session.rollback()
            return {"error": str(e)}
        finally:
            session.close()

    @staticmethod
    def resetear_passwords_alumnos(profesor_id):
        """Genera claves temporales para todos los alumnos del profesor."""
        session = get_session()
        try:
            alumnos = session.query(Usuario).join(
                Equipo, Usuario.equipo_id == Equipo.id
            ).join(
                Industria, Equipo.industria_id == Industria.id
            ).filter(
                Usuario.rol == "alumno",
                Industria.profesor_id == profesor_id,
            ).order_by(Industria.nombre, Equipo.numero, Usuario.username).all()

            credenciales = []
            for alumno in alumnos:
                password_temporal = generar_password_temporal()
                alumno.password_hash = hashear_password(password_temporal)
                alumno.debe_cambiar_password = True
                alumno.password_actualizada = datetime.now()
                credenciales.append({
                    "usuario": alumno.username,
                    "nombre": alumno.nombre,
                    "password": password_temporal,
                    "detalle": f"Equipo {alumno.equipo.numero}" if alumno.equipo else "Sin equipo",
                })

            session.commit()
            return {"ok": True, "credenciales": credenciales}
        except Exception as e:
            session.rollback()
            return {"error": str(e)}
        finally:
            session.close()

    @staticmethod
    def listar_alumnos_por_profesor(profesor_id):
        session = get_session()
        try:
            alumnos = session.query(Usuario, Equipo, Industria).\
                join(Equipo, Usuario.equipo_id == Equipo.id).\
                join(Industria, Equipo.industria_id == Industria.id).\
                filter(Industria.profesor_id == profesor_id).\
                filter(Usuario.rol == 'alumno').all()

            return [{
                "id": u.id, "nombre": u.nombre, "username": u.username, "email": u.email,
                "industria_id": ind.id, "industria_nombre": ind.nombre,
                "equipo_id": eq.id, "equipo_numero": eq.numero, "es_representante": u.es_representante,
                "debe_cambiar_password": bool(u.debe_cambiar_password),
            } for u, eq, ind in alumnos]
        finally:
            session.close()

    @staticmethod
    def eliminar_alumno(alumno_id):
        session = get_session()
        try:
            alumno = session.query(Usuario).filter_by(id=alumno_id, rol='alumno').first()
            if not alumno: return {"error": "Alumno no encontrado"}
            alumno.equipo_id = None
            alumno.activo = False
            session.commit()
            return {"ok": True}
        except Exception as e:
            session.rollback()
            return {"error": str(e)}
        finally:
            session.close()

    @staticmethod
    def actualizar_alumno(alumno_id, nombre, email):
        session = get_session()
        try:
            alumno = session.query(Usuario).filter_by(id=alumno_id, rol='alumno').first()
            if not alumno: return {"error": "Alumno no encontrado"}
            alumno.nombre = nombre
            alumno.email = email
            session.commit()
            return {"ok": True}
        except Exception as e:
            session.rollback()
            return {"error": str(e)}
        finally:
            session.close()

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

            # 1. Preparar datos de marcas (Leyendo de la BD)
            marcas_data = []
            
            for eq in equipos:
                marcas = session.query(Marca).filter_by(equipo_id=eq.id, activa=True).all()
                for m in marcas:
                    # Buscar decisión del equipo para este año
                    dec = session.query(Decision).filter_by(
                        equipo_id=eq.id, anio=anio_actual
                    ).first()

                    # Valores por defecto (última decisión o valores iniciales)
                    precio = m.precio_actual
                    publicidad = m.publicidad_actual
                    investigacion = m.investigacion_actual
                    produccion = m.produccion_actual
                    
                    # Vendedores por defecto (leer de FuerzaVentas del año anterior)
                    fv = session.query(FuerzaVentas).filter_by(
                        marca_id=m.id, anio=anio_actual
                    ).all()
                    
                    vendedores = {"1": 0, "2": 0, "3": 0}
                    detallistas = {"1": 0, "2": 0, "3": 0}
                    
                    if fv:
                        for f in fv:
                            canal = session.query(Canal).filter_by(id=f.canal_id).first()
                            if canal:
                                vendedores[str(canal.numero)] = f.vendedores
                                detallistas[str(canal.numero)] = f.detallistas
                    
                    # Si hay una decisión para este año, usarla
                    if dec:
                        dm = session.query(DecisionMarca).filter_by(
                            decision_id=dec.id, marca_nombre=m.nombre
                        ).first()
                        if dm:
                            precio = dm.precio_venta
                            publicidad = dm.presupuesto_publicitario
                            produccion = dm.produccion
                            
                            # Leer vendedores desde la decisión
                            from core.models import DecisionVendedor
                            dv = session.query(DecisionVendedor).filter_by(
                                decision_marca_id=dm.id
                            ).all()
                            for v in dv:
                                canal = session.query(Canal).filter_by(id=v.canal_id).first()
                                if canal:
                                    vendedores[str(canal.numero)] = v.vendedores

                    # Obtener el costo de transferencia real (Atributo 6)
                    attr_costo = session.query(AtributoFisico).filter_by(
                        marca_id=m.id, numero=6, anio=anio_actual
                    ).first()
                    costo_transferencia = attr_costo.valor if attr_costo else (precio * 0.55)

                    marcas_data.append({
                        "nombre": m.nombre,
                        "equipo_id": eq.id,
                        "tipo": m.tipo,
                        "precio": precio,
                        "publicidad": publicidad,
                        "investigacion": investigacion,
                        "produccion": produccion,
                        "costo_transferencia": costo_transferencia,
                        "vendedores_canal1": vendedores["1"],
                        "vendedores_canal2": vendedores["2"],
                        "vendedores_canal3": vendedores["3"],
                        "detallistas_canal1": detallistas["1"],
                        "detallistas_canal2": detallistas["2"],
                    })

            # 2. Obtener segmentos y canales
            segmentos = [{
                "id": s.id, "numero": s.numero, "peso": s.peso,
                "valor_ideal_x": s.valor_ideal_x, "valor_ideal_y": s.valor_ideal_y,
            } for s in session.query(Segmento).filter_by(industria_id=industria_id).all()]

            canales = [{
                "id": c.id, "numero": c.numero,
                "total_distribuidores": c.total_distribuidores,
                "margen_promedio": c.margen_promedio,
            } for c in session.query(Canal).filter_by(industria_id=industria_id).all()]

            # 3. Ejecutar motor
            config = {
                "mercado_total": 1300000,
                "inflacion_anual": industria.inflacion_anual,
                "crecimiento_pib": industria.crecimiento_pib,
            }
            motor = MotorSimulacion(config)
            resultado = motor.simular_ronda(marcas_data, segmentos, canales, anio_actual)

            # 4. Guardar reportes por equipo
            siguiente_anio = anio_actual + 1

            for eq in equipos:
                resultados_eq = [r for r in resultado["resultados"] if r["equipo_id"] == eq.id]

                # Buscar o crear reporte
                rep = session.query(Reporte).filter_by(
                    equipo_id=eq.id, anio=siguiente_anio
                ).first()

                if rep:
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

                # Corrección de sintaxis en la condición del panel
                if "panel" in datos and datos["panel"] and "porcion_mercado" in datos["panel"][0]:
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