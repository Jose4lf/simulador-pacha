"""
Servicio del Profesor - PACHA (esquema normalizado)
"""
from datetime import datetime
from infraestructura.database import get_session
from core.models import (
    Usuario, Simulador, Industria, Equipo, Marca,
    Segmento, Canal, Decision, Reporte, ReporteMarca, 
    DecisionMarca, EstudioMercado, DecisionEstudio,
    ReporteMarcaCanal, FuerzaVentas
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
    # CORREGIDO: "margin_promedio" cambiado a "margen_promedio"
    {"numero": 3, "nombre": "Canal 3", "total_distribuidores": 4000, "margen_promedio": 0.40}, 
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
                    # Valores por defecto iniciales
                    precio_ini = 300
                    pub_ini = 2500
                    prod_ini = 100

                    # Ajustar valores iniciales de la Marca según la firma
                    if num_equipo == 1:
                        if idx == 0: precio_ini, pub_ini, prod_ini = 278, 1650, 10599
                        elif idx == 1: precio_ini, pub_ini, prod_ini = 420, 2100, 8800
                    elif num_equipo == 2:
                        if idx == 0: precio_ini, pub_ini, prod_ini = 300, 3000, 5000
                        elif idx == 1: precio_ini, pub_ini, prod_ini = 320, 2500, 4000
                    elif num_equipo == 3:
                        if idx == 0: precio_ini, pub_ini, prod_ini = 300, 5000, 12000
                        elif idx == 1: precio_ini, pub_ini, prod_ini = 310, 4000, 8000
                    elif num_equipo == 4:
                        if idx == 0: precio_ini, pub_ini, prod_ini = 300, 6000, 15000
                        elif idx == 1: precio_ini, pub_ini, prod_ini = 320, 4500, 10000
                    elif num_equipo == 5:
                        if idx == 0: precio_ini, pub_ini, prod_ini = 300, 5500, 13000
                        elif idx == 1: precio_ini, pub_ini, prod_ini = 310, 4200, 9000

                    marca = Marca(
                        equipo_id=equipo.id,
                        nombre=nombre_marca,
                        tipo="SONITE",
                        activa=True,
                        anio_lanzamiento=0,
                        precio_actual=precio_ini,
                        publicidad_actual=pub_ini,
                        investigacion_actual=0,
                        produccion_actual=prod_ini,
                        calidad_actual=50,
                    )
                    session.add(marca)
                    session.commit()
                    session.refresh(marca)
                    marcas_creadas.append(marca)

                # ============================================================
                # CREAR REPORTE INICIAL DEL AÑO 0 (Datos exactos por equipo)
                # ============================================================
                # Asignar totales según el número de equipo (Perfiles variados)
                neta_total = 0.0
                bruta_total = 0.0
                presupuesto = 7000.0
                id_total = 0.0
                fv_total = 0.0
                inv_mercado = 0.0
                costo_exc = 0.0

                if num_equipo == 1:
                    neta_total, bruta_total, presupuesto = 4700.0, 6166.0, 7000.0
                    fv_total = -1466.0
                elif num_equipo == 2:
                    neta_total, bruta_total, presupuesto = 7308.0, 7000.0, 8000.0
                    fv_total = 308.0
                elif num_equipo == 3:
                    neta_total, bruta_total, presupuesto = 15950.0, 16500.0, 9500.0
                    fv_total = -550.0
                elif num_equipo == 4:
                    neta_total, bruta_total, presupuesto = 22719.0, 26000.0, 11000.0
                    fv_total = -3281.0
                elif num_equipo == 5:
                    neta_total, bruta_total, presupuesto = 19323.0, 20000.0, 10000.0
                    fv_total = -677.0

                rep_inicial = Reporte(
                    equipo_id=equipo.id,
                    anio=0,
                    mercado_total=1300000,
                    contribucion_bruta_total=bruta_total,
                    contribucion_neta_total=neta_total,
                    presupuesto_proximo_periodo=presupuesto,
                    investigacion_total=id_total,
                    fuerza_ventas_total=fv_total,
                    investigacion_mercado=inv_mercado,
                    costo_util_excepcional=costo_exc,
                    inflacion_aplicada=ind.inflacion_anual,
                    crecimiento_pnb=ind.crecimiento_pib,
                    tipo_cambio=ind.tipo_cambio_usd,
                )
                session.add(rep_inicial)
                session.commit()
                session.refresh(rep_inicial) # 👈 IMPORTANTE: Refrescar

                # Crear reporte_marca inicial con datos financieros exactos
                for idx, marca in enumerate(marcas_creadas):
                    prod, vendidas, inv = 100, 100, 0
                    precio, precio_prom, costo_trans = 300, 300, 165
                    ingresos, costo_prod, costo_inv = 30000, 16500, 0
                    publicidad, contribucion = 2500, 11000

                    if num_equipo == 1:
                        if idx == 0:
                            prod, vendidas, inv = 10599.0, 10599.0, 0.0
                            precio, precio_prom, costo_trans = 278.0, 171.0, 108.0
                            ingresos, costo_prod, costo_inv = 18099.0, 11397.0, 0.0
                            publicidad, contribucion = 1650.0, 5052.0
                        elif idx == 1:
                            prod, vendidas, inv = 8800.0, 3439.8, 5360.2
                            precio, precio_prom, costo_trans = 420.0, 259.0, 140.0
                            ingresos, costo_prod, costo_inv = 8908.0, 4829.0, 865.0
                            publicidad, contribucion = 2100.0, 1113.0
                    elif num_equipo == 2:
                        if idx == 0:
                            prod, vendidas, inv = 5000.0, 4500.0, 500.0
                            precio, precio_prom, costo_trans = 300.0, 280.0, 150.0
                            ingresos, costo_prod, costo_inv = 1260000.0, 675000.0, 75000.0
                            publicidad, contribucion = 30000.0, 480000.0
                        elif idx == 1:
                            prod, vendidas, inv = 4000.0, 3800.0, 200.0
                            precio, precio_prom, costo_trans = 320.0, 300.0, 160.0
                            ingresos, costo_prod, costo_inv = 1140000.0, 608000.0, 32000.0
                            publicidad, contribucion = 25000.0, 455000.0
                    elif num_equipo == 3:
                        if idx == 0:
                            prod, vendidas, inv = 12000.0, 11000.0, 1000.0
                            precio, precio_prom, costo_trans = 300.0, 290.0, 150.0
                            ingresos, costo_prod, costo_inv = 3190000.0, 1650000.0, 150000.0
                            publicidad, contribucion = 50000.0, 1340000.0
                        elif idx == 1:
                            prod, vendidas, inv = 8000.0, 7500.0, 500.0
                            precio, precio_prom, costo_trans = 310.0, 295.0, 155.0
                            ingresos, costo_prod, costo_inv = 2212500.0, 1162500.0, 77500.0
                            publicidad, contribucion = 40000.0, 932500.0
                    elif num_equipo == 4:
                        if idx == 0:
                            prod, vendidas, inv = 15000.0, 14500.0, 500.0
                            precio, precio_prom, costo_trans = 300.0, 295.0, 150.0
                            ingresos, costo_prod, costo_inv = 4277500.0, 2175000.0, 75000.0
                            publicidad, contribucion = 60000.0, 1967500.0
                        elif idx == 1:
                            prod, vendidas, inv = 10000.0, 9800.0, 200.0
                            precio, precio_prom, costo_trans = 320.0, 310.0, 160.0
                            ingresos, costo_prod, costo_inv = 3038000.0, 1568000.0, 32000.0
                            publicidad, contribucion = 45000.0, 1375000.0
                    elif num_equipo == 5:
                        if idx == 0:
                            prod, vendidas, inv = 13000.0, 12500.0, 500.0
                            precio, precio_prom, costo_trans = 300.0, 290.0, 150.0
                            ingresos, costo_prod, costo_inv = 3625000.0, 1875000.0, 75000.0
                            publicidad, contribucion = 55000.0, 1620000.0
                        elif idx == 1:
                            prod, vendidas, inv = 9000.0, 8500.0, 500.0
                            precio, precio_prom, costo_trans = 310.0, 300.0, 155.0
                            ingresos, costo_prod, costo_inv = 2550000.0, 1317500.0, 77500.0
                            publicidad, contribucion = 42000.0, 1120000.0

                    rm = ReporteMarca(
                        reporte_id=rep_inicial.id,
                        marca_nombre=marca.nombre,
                        produccion=prod,
                        unidades_vendidas=vendidas,
                        inventario=inv,
                        precio_final=precio,
                        precio_promedio=precio_prom,
                        costo_transferencia=costo_trans,
                        ingresos=ingresos,
                        costo_productos_vendidos=costo_prod,
                        costo_inventario=costo_inv,
                        publicidad=publicidad,
                        contribucion_bruta_marketing=contribucion,
                        porcion_mercado=100.0 / (num_equipos * 2),
                    )
                    session.add(rm)
                session.commit()

                # ============================================================
                # CREAR DATOS DE MARKETING (Distribuidores y Fuerza de Ventas)
                # ============================================================
                # 1. Asignar Porción de Mercado según el equipo
                if num_equipo == 1:
                    porciones = [0.11, 0.04]
                    fv_canales = [5, 42, 18]
                    dist_canales = [504, 16115, 1440]
                elif num_equipo == 2:
                    porciones = [0.08, 0.06]
                    fv_canales = [10, 20, 5]
                    dist_canales = [400, 12000, 1000]
                elif num_equipo == 3:
                    porciones = [0.15, 0.10]
                    fv_canales = [50, 100, 20]
                    dist_canales = [600, 20000, 2000]
                elif num_equipo == 4:
                    porciones = [0.20, 0.15]
                    fv_canales = [10, 15, 2]
                    dist_canales = [800, 25000, 3000]
                elif num_equipo == 5:
                    porciones = [0.05, 0.02]
                    fv_canales = [2, 5, 1]
                    dist_canales = [200, 5000, 500]

                # Actualizar ReporteMarca con la porción de mercado real
                for idx_rm, rm in enumerate(rep_inicial.marcas):
                    if idx_rm < len(porciones):
                        rm.porcion_mercado = porciones[idx_rm] * 100

                # Obtener los canales de la industria
                canales = session.query(Canal).filter_by(industria_id=ind.id).order_by(Canal.numero).all()

                # Guardar Distribuidores y Fuerza de Ventas
                for idx_rm, rm in enumerate(rep_inicial.marcas):
                    for idx_canal, canal in enumerate(canales):
                        if idx_canal < len(dist_canales):
                            rm_canal = ReporteMarcaCanal(
                                reporte_marca_id=rm.id,
                                canal_id=canal.id,
                                detallistas=dist_canales[idx_canal],
                                vendedores=fv_canales[idx_canal],
                                ventas_unidades=rm.unidades_vendidas / 3
                            )
                            session.add(rm_canal)

                            # Guardar la fuerza de ventas
                            fuerza = FuerzaVentas(
                                marca_id=marcas_creadas[idx_rm].id, # Usar el ID de la marca correcta
                                canal_id=canal.id,
                                vendedores=fv_canales[idx_canal],
                                detallistas=dist_canales[idx_canal],
                                anio=0
                            )
                            session.add(fuerza)
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