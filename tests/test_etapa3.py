"""
Pruebas de la Etapa 3: motor año a año, decisiones efectivas, estudios de
mercado y reportes.

No tocan PostgreSQL: usan SQLite temporal.
Ejecutar con:
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m unittest discover -s tests -v
"""
import os
import tempfile
import unittest

from sqlalchemy.orm import scoped_session, sessionmaker

import infraestructura.database as db
from aplicacion.alumno_service import AlumnoService
from aplicacion.profesor_service import ProfesorService
from aplicacion.simulacion_service import SimulacionService
from core.models import (
    Base, Usuario, Industria, Equipo, Marca, Segmento, Canal, FuerzaVentas,
    Decision, DecisionMarca, Reporte, ReporteMarca, ReporteMarcaCanal,
    ReporteMarcaSegmento, CompraEstudio, EstudioAwareness, EstudioEscala,
    EstudioResultado, EstudioMercado, LogActividad,
)
from core.motor_simulacion import MotorSimulacion
from infraestructura.database import _crear_sqlite_fallback
from tests.test_etapa2 import BaseConBD, PASSWORD_BASE


def _marca(nombre, precio=300, publicidad=2500, produccion=100,
           inventario=0, equipo_id=1, calidad=50, vendedores=None):
    return {
        "nombre": nombre, "equipo_id": equipo_id, "tipo": "SONITE",
        "precio": precio, "publicidad": publicidad, "produccion": produccion,
        "inventario": inventario, "calidad": calidad,
        "vendedores": vendedores or {1: 10, 2: 20, 3: 10},
        "detallistas": {1: 500, 2: 10000, 3: 1000},
    }


SEGMENTOS = [
    {"id": 1, "numero": 1, "peso": 0.30, "valor_ideal_x": 3.5, "valor_ideal_y": 14.5},
    {"id": 2, "numero": 2, "peso": 0.18, "valor_ideal_x": -7.7, "valor_ideal_y": 5.5},
    {"id": 3, "numero": 3, "peso": 0.15, "valor_ideal_x": 13.9, "valor_ideal_y": 11.5},
    {"id": 4, "numero": 4, "peso": 0.21, "valor_ideal_x": 9.3, "valor_ideal_y": 0.5},
    {"id": 5, "numero": 5, "peso": 0.16, "valor_ideal_x": -12.7, "valor_ideal_y": -5.3},
]
CANALES = [
    {"id": 1, "numero": 1, "total_distribuidores": 3000},
    {"id": 2, "numero": 2, "total_distribuidores": 35000},
    {"id": 3, "numero": 3, "total_distribuidores": 4000},
]


class TestMotor(unittest.TestCase):
    def motor(self):
        return MotorSimulacion({
            "mercado_total": 1300000, "crecimiento_pib": 0.04,
            "anio_base": 0, "semilla": "test",
        })

    def test_reproducible(self):
        marcas = [_marca("AAA"), _marca("BBB", precio=320)]
        a = self.motor().simular_ronda(marcas, SEGMENTOS, CANALES, 1)
        b = self.motor().simular_ronda(marcas, SEGMENTOS, CANALES, 1)
        self.assertEqual(a, b)

    def test_mercado_crece_con_pib(self):
        self.assertAlmostEqual(self.motor()._calcular_mercado(0), 1300000)
        self.assertAlmostEqual(
            self.motor()._calcular_mercado(1), 1300000 * 1.04, places=2
        )

    def test_reparte_todo_el_mercado_si_hay_oferta(self):
        marcas = [_marca(n, produccion=500) for n in ("AAA", "BBB", "CCC", "DDD")]
        salida = self.motor().simular_ronda(marcas, SEGMENTOS, CANALES, 1)
        vendidas = sum(r["unidades_vendidas"] for r in salida["resultados"])
        self.assertAlmostEqual(vendidas * 1000, salida["mercado_total"], places=0)
        for r in salida["resultados"]:
            self.assertEqual(r["demanda_no_satisfecha"], 0)
            self.assertGreaterEqual(r["inventario"], 0)

    def test_limita_por_produccion(self):
        marcas = [_marca(n, produccion=10) for n in ("AAA", "BBB")]
        salida = self.motor().simular_ronda(marcas, SEGMENTOS, CANALES, 1)
        for r in salida["resultados"]:
            self.assertAlmostEqual(r["unidades_vendidas"], 10)
            self.assertEqual(r["inventario"], 0)
            self.assertGreater(r["demanda_no_satisfecha"], 0)

    def test_inventario_permite_vender_sin_producir(self):
        marcas = [
            _marca("AAA", produccion=0, inventario=800),
            _marca("BBB", produccion=800, inventario=0),
        ]
        salida = self.motor().simular_ronda(marcas, SEGMENTOS, CANALES, 1)
        aaa = next(r for r in salida["resultados"] if r["marca"] == "AAA")
        self.assertGreater(aaa["unidades_vendidas"], 0)
        self.assertAlmostEqual(
            aaa["unidades_vendidas"] + aaa["inventario"], 800, places=1
        )

    def test_precio_menor_gana_cuota(self):
        marcas = [
            _marca("CARO", precio=500, produccion=800),
            _marca("BARATO", precio=250, produccion=800),
        ]
        salida = self.motor().simular_ronda(marcas, SEGMENTOS, CANALES, 1)
        caro = next(r for r in salida["resultados"] if r["marca"] == "CARO")
        barato = next(r for r in salida["resultados"] if r["marca"] == "BARATO")
        self.assertGreater(barato["porcion_mercado"], caro["porcion_mercado"])

    def test_reparto_por_canal_y_segmento(self):
        marcas = [_marca("AAA", produccion=800)]
        salida = self.motor().simular_ronda(marcas, SEGMENTOS, CANALES, 1)
        r = salida["resultados"][0]
        self.assertEqual(len(r["por_canal"]), 3)
        self.assertEqual(len(r["por_segmento"]), 5)
        self.assertAlmostEqual(
            sum(c["ventas_unidades"] for c in r["por_canal"]),
            r["unidades_vendidas"], places=1,
        )
        self.assertAlmostEqual(
            sum(s["ventas_unidades"] for s in r["por_segmento"]),
            r["unidades_vendidas"], places=1,
        )


class BaseDominio(unittest.TestCase):
    """SQLite temporal con una industria completa, sin usuarios de login."""

    def setUp(self):
        fd, self.ruta = tempfile.mkstemp(prefix="pacha_test3_", suffix=".db")
        os.close(fd)
        self.url = f"sqlite:///{self.ruta}"
        self.guardado = (db.engine, db.SessionLocal, db.DB_ACTUAL, db.DB_ES_FALLBACK)
        self.engine = _crear_sqlite_fallback(self.url)
        Base.metadata.create_all(self.engine)
        db.engine = self.engine
        db.SessionLocal = scoped_session(
            sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        )
        db.DB_ACTUAL = "sqlite"
        db.DB_ES_FALLBACK = True
        self._sembrar()

    def tearDown(self):
        db.close_session()
        self.engine.dispose()
        db.engine, db.SessionLocal, db.DB_ACTUAL, db.DB_ES_FALLBACK = self.guardado
        try:
            os.remove(self.ruta)
        except OSError:
            pass

    def _sembrar(self):
        sesion = db.SessionLocal()
        try:
            profe = Usuario(
                username="prof_test", password_hash="x", rol="profesor",
                nombre="Profe", activo=True, debe_cambiar_password=False,
            )
            sesion.add(profe)
            sesion.flush()
            ind = Industria(
                nombre="Mercado Test", profesor_id=profe.id, anio_actual=0,
                anio_maximo=10, estado="inicializada", permitir_envio=True,
                inflacion_anual=0.09, crecimiento_pib=0.04,
                tipo_cambio_usd=11.90, presupuesto_inicial=10000,
            )
            sesion.add(ind)
            sesion.flush()
            self.industria_id = ind.id

            self.equipos = []
            for numero in (1, 2):
                eq = Equipo(
                    industria_id=ind.id, numero=numero,
                    nombre_empresa=f"Empresa {numero}", presupuesto_actual=10000,
                )
                sesion.add(eq)
                sesion.flush()
                self.equipos.append(eq.id)

            for seg in SEGMENTOS:
                sesion.add(Segmento(
                    industria_id=ind.id, numero=seg["numero"],
                    nombre=f"Segmento {seg['numero']}", peso=seg["peso"],
                    valor_ideal_x=seg["valor_ideal_x"],
                    valor_ideal_y=seg["valor_ideal_y"],
                ))
            for canal in CANALES:
                sesion.add(Canal(
                    industria_id=ind.id, numero=canal["numero"],
                    nombre=f"Canal {canal['numero']}",
                    total_distribuidores=canal["total_distribuidores"],
                    margen_promedio=0.4,
                ))
            sesion.flush()

            for idx, eq_id in enumerate(self.equipos):
                for sufijo in ("A", "B"):
                    marca = Marca(
                        equipo_id=eq_id, nombre=f"M{sufijo}{idx + 1}",
                        tipo="SONITE", activa=True, precio_actual=300,
                        publicidad_actual=2500, produccion_actual=100,
                        calidad_actual=50,
                    )
                    sesion.add(marca)
                    sesion.flush()
                    for canal in CANALES:
                        sesion.add(FuerzaVentas(
                            marca_id=marca.id, canal_id=canal["id"],
                            vendedores=10, detallistas=1000, anio=0,
                        ))

            for numero in range(1, 16):
                sesion.add(EstudioMercado(
                    numero=numero, nombre=f"Estudio {numero}",
                    descripcion="Estudio de prueba", costo_base=10000,
                    tipo_producto="SONITE",
                ))

            sesion.commit()
        finally:
            sesion.close()

    def enviar(self, equipo_id, precio=300, produccion=100, estudios=None,
               estado="enviada", vendedores=None, publicidad=2500):
        decisiones = {}
        for marca in self.marcas(equipo_id):
            decisiones[marca.nombre] = {
                "precio": precio,
                "publicidad": publicidad,
                "produccion": produccion,
                "proyecto_id": "",
                "objetivo_x": 0,
                "objetivo_y": 0,
                "vendedores": vendedores or {1: 10, 2: 20, 3: 10},
            }
        return AlumnoService.guardar_decision(
            equipo_id, 0, decisiones,
            canales_ids=[1, 2, 3], estudios_ids=estudios or [],
            estado=estado,
        )

    def marcas(self, equipo_id):
        sesion = db.SessionLocal()
        try:
            return sesion.query(Marca).filter_by(
                equipo_id=equipo_id, activa=True
            ).order_by(Marca.id).all()
        finally:
            sesion.close()


class TestProcesamiento(BaseDominio):
    def test_ronda_crea_reporte_completo(self):
        self.enviar(self.equipos[0])
        self.enviar(self.equipos[1])
        salida = SimulacionService.procesar_ronda(self.industria_id)
        self.assertTrue(salida.get("ok"), salida)
        self.assertEqual(salida["anio_procesado"], 0)
        self.assertEqual(salida["siguiente_anio"], 1)

        sesion = db.SessionLocal()
        try:
            reportes = sesion.query(Reporte).filter_by(anio=1).all()
            self.assertEqual(len(reportes), 2)
            for rep in reportes:
                self.assertEqual(len(rep.marcas), 2)
                for rm in rep.marcas:
                    self.assertEqual(len(rm.canales), 3)
                    self.assertEqual(len(rm.segmentos), 5)
                    self.assertGreater(rm.precio_final, 0)
                    self.assertIsNotNone(rm.costo_transferencia)
            ind = sesion.query(Industria).filter_by(id=self.industria_id).first()
            self.assertEqual(ind.anio_actual, 1)
            self.assertEqual(ind.estado, "en_curso")
            for eq in sesion.query(Equipo).filter_by(industria_id=self.industria_id):
                self.assertFalse(eq.ya_decidio)
                self.assertIsNone(eq.fecha_decision)
            self.assertEqual(
                sesion.query(LogActividad).filter_by(
                    accion="procesar_ronda"
                ).count(), 1
            )
        finally:
            sesion.close()

    def test_sin_decision_usa_valores_vigentes(self):
        salida = SimulacionService.procesar_ronda(self.industria_id)
        self.assertTrue(salida.get("ok"), salida)
        self.assertEqual(len(salida["equipos_sin_decision"]), 2)
        sesion = db.SessionLocal()
        try:
            reportes = sesion.query(Reporte).filter_by(anio=1).all()
            self.assertEqual(len(reportes), 2)
            for rep in reportes:
                for rm in rep.marcas:
                    self.assertEqual(rm.precio_final, 300)
        finally:
            sesion.close()

    def test_avanza_al_siguiente_anio(self):
        SimulacionService.procesar_ronda(self.industria_id)
        segunda = SimulacionService.procesar_ronda(self.industria_id)
        self.assertTrue(segunda.get("ok"), segunda)
        self.assertEqual(segunda["anio_procesado"], 1)
        self.assertEqual(segunda["siguiente_anio"], 2)

    def test_no_duplica_un_reporte_existente(self):
        sesion = db.SessionLocal()
        try:
            sesion.add(Reporte(equipo_id=self.equipos[0], anio=1))
            sesion.commit()
        finally:
            sesion.close()
        salida = SimulacionService.procesar_ronda(self.industria_id)
        self.assertIn("error", salida)
        self.assertIn("Ya existe un reporte", salida["error"])

    def test_borrador_no_es_efectivo(self):
        self.enviar(self.equipos[0], precio=999, estado="borrador")
        salida = SimulacionService.procesar_ronda(self.industria_id)
        self.assertTrue(salida.get("ok"), salida)
        self.assertEqual(len(salida["equipos_sin_decision"]), 2)

        sesion = db.SessionLocal()
        try:
            dec = sesion.query(Decision).filter_by(equipo_id=self.equipos[0]).first()
            self.assertEqual(dec.estado, "borrador")
            rep = sesion.query(Reporte).filter_by(
                equipo_id=self.equipos[0], anio=1
            ).first()
            for rm in rep.marcas:
                self.assertEqual(rm.precio_final, 300)
        finally:
            sesion.close()

    def test_decision_enviada_no_se_reenvia(self):
        self.assertEqual(self.enviar(self.equipos[0]).get("ok"), True)
        segundo = self.enviar(self.equipos[0], precio=400)
        self.assertIn("error", segundo)

    def test_decision_actualiza_estado_de_marca(self):
        self.enviar(self.equipos[0], precio=350, produccion=150,
                    publicidad=3000)
        SimulacionService.procesar_ronda(self.industria_id)
        sesion = db.SessionLocal()
        try:
            for marca in sesion.query(Marca).filter_by(equipo_id=self.equipos[0]):
                self.assertEqual(marca.precio_actual, 350)
                self.assertEqual(marca.produccion_actual, 150)
                self.assertEqual(marca.publicidad_actual, 3000)
        finally:
            sesion.close()

    def test_finaliza_al_llegar_al_maximo(self):
        sesion = db.SessionLocal()
        try:
            ind = sesion.query(Industria).filter_by(id=self.industria_id).first()
            ind.anio_maximo = 1
            sesion.commit()
        finally:
            sesion.close()
        salida = SimulacionService.procesar_ronda(self.industria_id)
        self.assertTrue(salida["finalizada"])
        segunda = SimulacionService.procesar_ronda(self.industria_id)
        self.assertIn("error", segunda)


class TestEstudios(BaseDominio):
    def test_compra_y_generacion(self):
        self.enviar(self.equipos[0], estudios=[1, 4, 14])
        sesion = db.SessionLocal()
        try:
            compras = sesion.query(CompraEstudio).filter_by(
                equipo_id=self.equipos[0], anio=0
            ).all()
            self.assertEqual(len(compras), 3)
            self.assertTrue(all(c.costo == 10000 for c in compras))
        finally:
            sesion.close()

        salida = SimulacionService.procesar_ronda(self.industria_id)
        self.assertEqual(salida["estudios_generados"], 3)

        sesion = db.SessionLocal()
        try:
            ids = [c.id for c in sesion.query(CompraEstudio).filter_by(
                equipo_id=self.equipos[0]
            ).all()]
            self.assertGreater(
                sesion.query(EstudioAwareness).filter(
                    EstudioAwareness.compra_id.in_(ids)
                ).count(), 0,
            )
            self.assertGreater(
                sesion.query(EstudioEscala).filter(
                    EstudioEscala.compra_id.in_(ids)
                ).count(), 0,
            )
            self.assertGreater(
                sesion.query(EstudioResultado).filter(
                    EstudioResultado.compra_id.in_(ids)
                ).count(), 0,
            )
            rep = sesion.query(Reporte).filter_by(
                equipo_id=self.equipos[0], anio=1
            ).first()
            self.assertGreater(rep.investigacion_mercado, 0)
        finally:
            sesion.close()

    def test_deseleccionar_estudio_elimina_la_compra(self):
        decisiones = {}
        for marca in self.marcas(self.equipos[0]):
            decisiones[marca.nombre] = {
                "precio": 300, "publicidad": 2500, "produccion": 100,
                "vendedores": {1: 10, 2: 20, 3: 10},
            }
        AlumnoService.guardar_decision(
            self.equipos[0], 0, decisiones, [1, 2, 3], [1, 2], "borrador"
        )
        AlumnoService.guardar_decision(
            self.equipos[0], 0, decisiones, [1, 2, 3], [1], "enviada"
        )
        sesion = db.SessionLocal()
        try:
            compras = sesion.query(CompraEstudio).filter_by(
                equipo_id=self.equipos[0]
            ).all()
            self.assertEqual([c.estudio_id for c in compras], [1])
        finally:
            sesion.close()

    def test_vista_de_estudios_arma_bloques(self):
        self.enviar(self.equipos[0], estudios=[1, 6])
        SimulacionService.procesar_ronda(self.industria_id)
        datos = AlumnoService.listar_estudios_equipo(self.equipos[0], 0)
        self.assertEqual(len(datos["estudios"]), 2)
        titulos = [b["titulo"] for e in datos["estudios"] for b in e["bloques"]]
        self.assertIn("Conocimiento de marca", titulos)
        self.assertIn("Pronóstico de mercado", titulos)


class BaseWeb(BaseConBD):
    """Base de login + dominio completo en la industria A."""

    def setUp(self):
        super().setUp()
        self._sembrar_dominio()

    def _sembrar_dominio(self):
        sesion = db.SessionLocal()
        try:
            ind = sesion.query(Industria).filter_by(id=self.ids["ind_a"]).first()
            eq2 = Equipo(
                industria_id=ind.id, numero=2, nombre_empresa="Empresa A2",
                presupuesto_actual=10000,
            )
            sesion.add(eq2)
            sesion.flush()
            self.ids["eq_a2"] = eq2.id

            for seg in SEGMENTOS:
                sesion.add(Segmento(
                    industria_id=ind.id, numero=seg["numero"],
                    nombre=f"Segmento {seg['numero']}", peso=seg["peso"],
                    valor_ideal_x=seg["valor_ideal_x"],
                    valor_ideal_y=seg["valor_ideal_y"],
                ))
            for canal in CANALES:
                sesion.add(Canal(
                    industria_id=ind.id, numero=canal["numero"],
                    nombre=f"Canal {canal['numero']}",
                    total_distribuidores=canal["total_distribuidores"],
                    margen_promedio=0.4,
                ))
            sesion.flush()

            for eq_id in (self.ids["eq_a"], eq2.id):
                for sufijo in ("A", "B"):
                    marca = Marca(
                        equipo_id=eq_id, nombre=f"W{sufijo}{eq_id}",
                        tipo="SONITE", activa=True, precio_actual=300,
                        publicidad_actual=2500, produccion_actual=100,
                        calidad_actual=50,
                    )
                    sesion.add(marca)
                    sesion.flush()
                    for canal in CANALES:
                        sesion.add(FuerzaVentas(
                            marca_id=marca.id, canal_id=canal["id"],
                            vendedores=10, detallistas=1000, anio=0,
                        ))
            for numero in range(1, 16):
                sesion.add(EstudioMercado(
                    numero=numero, nombre=f"Estudio {numero}",
                    descripcion="Estudio de prueba", costo_base=10000,
                    tipo_producto="SONITE",
                ))
            sesion.commit()
        finally:
            sesion.close()


class TestRutasAlumno(BaseWeb):
    def test_hoja_decisiones_muestra_canales_y_estudios(self):
        self.login("alumno_a", rol="alumno")
        respuesta = self.client.get("/alumno/decisiones")
        self.assertEqual(respuesta.status_code, 200)
        html = respuesta.get_data(as_text=True)
        self.assertIn("Estudios de Mercado", html)
        self.assertIn("Estudio 1", html)
        self.assertIn("GUARDAR BORRADOR", html)

    def test_enviar_decision_desde_la_ruta(self):
        self.login("alumno_a", rol="alumno")
        token = self.csrf()
        datos = {"csrf_token": token, "estudios": ["1"]}
        sesion = db.SessionLocal()
        try:
            marcas = sesion.query(Marca).filter_by(equipo_id=self.ids["eq_a"]).all()
            canales = sesion.query(Canal).filter_by(
                industria_id=self.ids["ind_a"]
            ).all()
        finally:
            sesion.close()
        for marca in marcas:
            datos[f"precio_{marca.nombre}"] = "310"
            datos[f"publicidad_{marca.nombre}"] = "2500"
            datos[f"produccion_{marca.nombre}"] = "100"
            for canal in canales:
                datos[f"vendedores_{canal.id}_{marca.nombre}"] = "10"

        respuesta = self.client.post("/alumno/decisiones/enviar", data=datos)
        self.assertEqual(respuesta.status_code, 302)

        sesion = db.SessionLocal()
        try:
            dec = sesion.query(Decision).filter_by(
                equipo_id=self.ids["eq_a"]
            ).first()
            self.assertEqual(dec.estado, "enviada")
            self.assertEqual(
                sesion.query(CompraEstudio).filter_by(
                    equipo_id=self.ids["eq_a"], anio=0
                ).count(), 1,
            )
        finally:
            sesion.close()

    def test_guardar_borrador_desde_la_ruta(self):
        self.login("alumno_a", rol="alumno")
        token = self.csrf()
        datos = {"csrf_token": token}
        sesion = db.SessionLocal()
        try:
            marcas = sesion.query(Marca).filter_by(equipo_id=self.ids["eq_a"]).all()
        finally:
            sesion.close()
        for marca in marcas:
            datos[f"precio_{marca.nombre}"] = "305"

        respuesta = self.client.post("/alumno/decisiones/guardar", data=datos)
        self.assertEqual(respuesta.status_code, 302)
        sesion = db.SessionLocal()
        try:
            dec = sesion.query(Decision).filter_by(
                equipo_id=self.ids["eq_a"]
            ).first()
            self.assertEqual(dec.estado, "borrador")
            eq = sesion.query(Equipo).filter_by(id=self.ids["eq_a"]).first()
            self.assertFalse(eq.ya_decidio)
        finally:
            sesion.close()

    def test_post_sin_csrf_se_rechaza(self):
        self.login("alumno_a", rol="alumno")
        respuesta = self.client.post("/alumno/decisiones/enviar", data={})
        self.assertEqual(respuesta.status_code, 400)

    def test_estudios_y_reporte_se_renderizan(self):
        self.login("alumno_a", rol="alumno")
        token = self.csrf()
        datos = {"csrf_token": token, "estudios": ["1"]}
        sesion = db.SessionLocal()
        try:
            marcas = sesion.query(Marca).filter_by(equipo_id=self.ids["eq_a"]).all()
            canales = sesion.query(Canal).filter_by(
                industria_id=self.ids["ind_a"]
            ).all()
        finally:
            sesion.close()
        for marca in marcas:
            datos[f"precio_{marca.nombre}"] = "300"
            datos[f"publicidad_{marca.nombre}"] = "2500"
            datos[f"produccion_{marca.nombre}"] = "100"
            for canal in canales:
                datos[f"vendedores_{canal.id}_{marca.nombre}"] = "10"
        self.client.post("/alumno/decisiones/enviar", data=datos)

        salida = SimulacionService.procesar_ronda(self.ids["ind_a"])
        self.assertTrue(salida.get("ok"), salida)

        estudios = self.client.get("/alumno/estudios?anio=0")
        self.assertEqual(estudios.status_code, 200)
        self.assertIn("Conocimiento de marca", estudios.get_data(as_text=True))

        reporte = self.client.get("/alumno/reporte/1")
        self.assertEqual(reporte.status_code, 200)
        self.assertIn("Ventas por segmento", reporte.get_data(as_text=True))

    def test_reporte_fuera_de_rango_redirige(self):
        self.login("alumno_a", rol="alumno")
        respuesta = self.client.get("/alumno/reporte/99")
        self.assertEqual(respuesta.status_code, 302)


class TestRutasProfesor(BaseWeb):
    def test_resultados_tienen_estructura_para_la_vista(self):
        SimulacionService.procesar_ronda(self.ids["ind_a"])
        datos = ProfesorService.obtener_resultados(self.ids["ind_a"], 1)
        self.assertEqual(len(datos["equipos"]), 2)
        for eq in datos["equipos"]:
            self.assertIsNotNone(eq["datos"])
            self.assertIn("ventas", eq["datos"])
            self.assertIn("cuota", eq["datos"])

        self.login("profe_a", rol="profesor")
        respuesta = self.client.get(
            f"/profesor/simulaciones/{self.ids['ind_a']}/resultados"
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("EQUIPO 1", respuesta.get_data(as_text=True))

    def test_panel_muestra_decisiones_efectivas(self):
        self.login("profe_a", rol="profesor")
        respuesta = self.client.get(f"/profesor/simulaciones/{self.ids['ind_a']}")
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("0 de 2", respuesta.get_data(as_text=True))

    def test_procesar_ronda_desde_la_ruta(self):
        self.login("profe_a", rol="profesor")
        token = self.csrf()
        respuesta = self.client.post(
            f"/profesor/simulaciones/{self.ids['ind_a']}/procesar",
            data={"csrf_token": token},
        )
        self.assertEqual(respuesta.status_code, 302)
        sesion = db.SessionLocal()
        try:
            self.assertEqual(
                sesion.query(Reporte).filter_by(anio=1).count(), 2
            )
        finally:
            sesion.close()
