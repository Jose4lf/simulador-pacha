"""
Pruebas de la Etapa 5: Centro de I+D, evaluación de proyectos, aplicación a
marcas existentes y lanzamiento de marcas nuevas.

No tocan PostgreSQL: usan SQLite temporal.
Ejecutar con:
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m unittest discover -s tests -v
"""
import unittest

import infraestructura.database as db
from aplicacion.alumno_service import AlumnoService
from aplicacion.profesor_service import ProfesorService
from aplicacion.proyecto_service import ProyectoService
from aplicacion.simulacion_service import SimulacionService
from core.modelo_id import (
    PRESUPUESTO_MAXIMO, costo_estandar, evaluar_proyecto, indice_calidad,
    presupuesto_requerido, probabilidad_exito, validar_atributos,
    validar_nombre,
)
from core.models import (
    AtributoFisico, Equipo, FuerzaVentas, Industria, Marca, ProyectoAtributo,
    ProyectoID, ProyectoResultado, Reporte, ReporteMarca,
)
from tests.test_etapa3 import BaseDominio, BaseWeb

ATRIBUTOS_BASE = [10.0, 5.0, 50.0, 20.0, 20.0, 100.0]


def _con_costo(costo, atributos=None):
    """Copia de los atributos base con otro costo objetivo."""
    valores = list(atributos or ATRIBUTOS_BASE)
    valores[5] = costo
    return valores


class TestMatematicaID(unittest.TestCase):
    def test_costo_estandar(self):
        self.assertAlmostEqual(
            costo_estandar(dict(enumerate(ATRIBUTOS_BASE, start=1))), 83.5,
            places=2,
        )

    def test_presupuesto_requerido_suma_esfuerzos(self):
        actuales = dict(enumerate(ATRIBUTOS_BASE, start=1))
        objetivo = {1: 11, 2: 6, 3: 51, 4: 21, 5: 21, 6: 90}
        # 1*30 + 1*70 + 1*15 + 1*20 + 1*20 + 10*10 = 255
        self.assertAlmostEqual(
            presupuesto_requerido(actuales, objetivo), 255.0, places=2
        )

    def test_subir_el_costo_no_ahorra_presupuesto(self):
        actuales = dict(enumerate(ATRIBUTOS_BASE, start=1))
        objetivo = {1: 11, 2: 6, 3: 51, 4: 21, 5: 21, 6: 500}
        self.assertAlmostEqual(
            presupuesto_requerido(actuales, objetivo), 155.0, places=2
        )

    def test_probabilidad_proporcional(self):
        self.assertAlmostEqual(probabilidad_exito(700, 1000), 0.7)
        self.assertAlmostEqual(probabilidad_exito(1200, 1000), 1.0)
        self.assertAlmostEqual(probabilidad_exito(100, 0), 1.0)

    def test_indice_calidad_extremos(self):
        mejor = {1: 10, 2: 10, 3: 20, 4: 50, 5: 100, 6: 100}
        peor = {1: 20, 2: 3, 3: 100, 4: 5, 5: 5, 6: 100}
        self.assertAlmostEqual(indice_calidad(mejor), 100.0)
        self.assertAlmostEqual(indice_calidad(peor), 0.0)

    def test_validar_atributos(self):
        ok, _ = validar_atributos(dict(enumerate(ATRIBUTOS_BASE, start=1)))
        self.assertTrue(ok)
        incompleto = dict(enumerate(ATRIBUTOS_BASE[:5], start=1))
        self.assertFalse(validar_atributos(incompleto)[0])
        fuera = dict(enumerate(ATRIBUTOS_BASE, start=1))
        fuera[1] = 25
        self.assertFalse(validar_atributos(fuera)[0])

    def test_validar_nombre(self):
        self.assertTrue(validar_nombre("PSAMA"))
        self.assertTrue(validar_nombre("pvbra"))
        self.assertFalse(validar_nombre("PXAMA"))
        self.assertFalse(validar_nombre("PSAM"))
        self.assertFalse(validar_nombre(""))

    def test_evaluacion_determinista(self):
        actuales = dict(enumerate(ATRIBUTOS_BASE, start=1))
        objetivo = {1: 12, 2: 6, 3: 45, 4: 25, 5: 30, 6: 95}
        uno = evaluar_proyecto(
            actuales, objetivo, 500, equipo_id=1, nombre="PSAMA", anio=1,
            semilla="fija",
        )
        dos = evaluar_proyecto(
            actuales, objetivo, 500, equipo_id=1, nombre="PSAMA", anio=1,
            semilla="fija",
        )
        self.assertEqual(uno, dos)

    def test_fracaso_automatico_por_costo(self):
        actuales = dict(enumerate(ATRIBUTOS_BASE, start=1))
        objetivo = dict(enumerate(ATRIBUTOS_BASE, start=1))
        objetivo[2] = 5.1
        objetivo[6] = 500
        resultado = evaluar_proyecto(actuales, objetivo, 1000)
        self.assertFalse(resultado["aprobado"])
        self.assertEqual(resultado["atributo_fallido"], 6)
        self.assertAlmostEqual(
            resultado["costo_minimo"], costo_estandar(objetivo), places=2
        )

    def test_probabilidad_uno_aprueba(self):
        actuales = dict(enumerate(ATRIBUTOS_BASE, start=1))
        objetivo = dict(actuales)
        objetivo[6] = 99
        resultado = evaluar_proyecto(actuales, objetivo, 100)
        self.assertTrue(resultado["aprobado"])
        self.assertAlmostEqual(resultado["probabilidad"], 1.0)


class BaseID(BaseDominio):
    """Industria en Año 1 con atributos físicos en todas las marcas."""

    def setUp(self):
        super().setUp()
        self._fijar_anio(1)
        sesion = db.SessionLocal()
        try:
            for marca in sesion.query(Marca).all():
                for numero, valor in enumerate(ATRIBUTOS_BASE, start=1):
                    sesion.add(AtributoFisico(
                        marca_id=marca.id, numero=numero, valor=valor,
                        anio=0,
                    ))
                marca.costo_unitario = ATRIBUTOS_BASE[5]
            sesion.commit()
        finally:
            sesion.close()

    def _fijar_anio(self, anio, industria_id=None):
        sesion = db.SessionLocal()
        try:
            industria = sesion.query(Industria).filter_by(
                id=industria_id or self.industria_id
            ).first()
            industria.anio_actual = anio
            industria.estado = "en_curso"
            industria.permitir_envio = True
            sesion.commit()
        finally:
            sesion.close()

    def _marca(self, equipo_id=None, indice=0):
        sesion = db.SessionLocal()
        try:
            return sesion.query(Marca).filter_by(
                equipo_id=equipo_id or self.equipos[0], activa=True
            ).order_by(Marca.id).all()[indice]
        finally:
            sesion.close()

    def _proyecto(self, nombre):
        sesion = db.SessionLocal()
        try:
            return sesion.query(ProyectoID).filter_by(nombre=nombre).first()
        finally:
            sesion.close()

    def _aprobar(self, proyecto_id, anio=1):
        sesion = db.SessionLocal()
        try:
            proyecto = sesion.query(ProyectoID).filter_by(id=proyecto_id).first()
            proyecto.estado = "aprobado"
            proyecto.anio_aprobacion = anio
            sesion.commit()
        finally:
            sesion.close()

    def _datos(self, atributos=None, presupuesto=100, marca=None,
               marca_nueva=None, nombre="PSAMA"):
        return {
            "nombre": nombre,
            "marca_id": str(marca.id) if marca else None,
            "marca_nueva": marca_nueva,
            "presupuesto": str(presupuesto),
            "atributos": [str(v) for v in (atributos or _con_costo(99))],
        }


class TestAltaProyectos(BaseID):
    def test_crear_proyecto_sobre_marca_existente(self):
        marca = self._marca()
        salida = ProyectoService.crear_proyecto(
            self.equipos[0], 1, self._datos(marca=marca)
        )
        self.assertTrue(salida.get("ok"), salida)
        self.assertAlmostEqual(
            salida["estimacion"]["presupuesto_normal"], 10.0, places=2
        )
        self.assertAlmostEqual(
            salida["estimacion"]["probabilidad"], 1.0, places=4
        )
        proyecto = self._proyecto("PSAMA")
        self.assertIsNotNone(proyecto)
        self.assertEqual(proyecto.estado, "en_desarrollo")
        self.assertEqual(proyecto.marca_destino_id, marca.id)
        self.assertFalse(proyecto.es_nueva_marca)
        self.assertAlmostEqual(proyecto.gastos, 100000.0, places=2)
        sesion = db.SessionLocal()
        try:
            self.assertEqual(
                sesion.query(ProyectoAtributo).filter_by(
                    proyecto_id=proyecto.id
                ).count(),
                6,
            )
        finally:
            sesion.close()

    def test_nombre_invalido(self):
        marca = self._marca()
        salida = ProyectoService.crear_proyecto(
            self.equipos[0], 1, self._datos(marca=marca, nombre="XX1")
        )
        self.assertIn("error", salida)

    def test_presupuesto_fuera_de_rango(self):
        marca = self._marca()
        salida = ProyectoService.crear_proyecto(
            self.equipos[0], 1,
            self._datos(marca=marca, presupuesto=PRESUPUESTO_MAXIMO + 1),
        )
        self.assertIn("error", salida)
        salida = ProyectoService.crear_proyecto(
            self.equipos[0], 1, self._datos(marca=marca, presupuesto=50)
        )
        self.assertIn("error", salida)

    def test_atributo_fuera_de_rango(self):
        marca = self._marca()
        atributos = _con_costo(99)
        atributos[0] = 99
        salida = ProyectoService.crear_proyecto(
            self.equipos[0], 1, self._datos(marca=marca, atributos=atributos)
        )
        self.assertIn("error", salida)

    def test_marca_de_otro_equipo(self):
        marca = self._marca(equipo_id=self.equipos[1])
        salida = ProyectoService.crear_proyecto(
            self.equipos[0], 1, self._datos(marca=marca)
        )
        self.assertIn("error", salida)

    def test_anio_cero_bloqueado(self):
        self._fijar_anio(0)
        marca = self._marca()
        salida = ProyectoService.crear_proyecto(
            self.equipos[0], 0, self._datos(marca=marca)
        )
        self.assertIn("error", salida)

    def test_marca_nueva_valida(self):
        salida = ProyectoService.crear_proyecto(
            self.equipos[0], 1,
            self._datos(marca_nueva="SAMA", nombre="PSAMA"),
        )
        self.assertTrue(salida.get("ok"), salida)
        proyecto = self._proyecto("PSAMA")
        self.assertTrue(proyecto.es_nueva_marca)
        self.assertIsNone(proyecto.marca_destino_id)

    def test_marca_nueva_nombre_invalido(self):
        salida = ProyectoService.crear_proyecto(
            self.equipos[0], 1,
            self._datos(marca_nueva="SA", nombre="PSAMA"),
        )
        self.assertIn("error", salida)

    def test_marca_nueva_duplicada(self):
        salida = ProyectoService.crear_proyecto(
            self.equipos[0], 1,
            self._datos(marca_nueva=self._marca().nombre, nombre="PSAMA"),
        )
        self.assertIn("error", salida)

    def test_maximo_cuatro_por_anio(self):
        marca = self._marca()
        for sufijo in ("AAA", "AAB", "AAC", "AAD"):
            salida = ProyectoService.crear_proyecto(
                self.equipos[0], 1,
                self._datos(marca=marca, nombre=f"PS{sufijo}"),
            )
            self.assertTrue(salida.get("ok"), salida)
        salida = ProyectoService.crear_proyecto(
            self.equipos[0], 1,
            self._datos(marca=marca, nombre="PSAAE"),
        )
        self.assertIn("error", salida)
        self.assertIn("4", salida["error"])

    def test_maximo_cinco_nombres_por_simulacion(self):
        marca = self._marca()
        for sufijo in ("AAA", "AAB", "AAC", "AAD"):
            ProyectoService.crear_proyecto(
                self.equipos[0], 1,
                self._datos(marca=marca, nombre=f"PS{sufijo}"),
            )
        self._fijar_anio(2)
        salida = ProyectoService.crear_proyecto(
            self.equipos[0], 2,
            self._datos(marca=marca, nombre="PSAAE"),
        )
        self.assertTrue(salida.get("ok"), salida)
        salida = ProyectoService.crear_proyecto(
            self.equipos[0], 2,
            self._datos(marca=marca, nombre="PSAAF"),
        )
        self.assertIn("error", salida)

    def test_reenvio_fallido_exige_mismo_nombre_y_mas_presupuesto(self):
        marca = self._marca()
        salida = ProyectoService.crear_proyecto(
            self.equipos[0], 1, self._datos(marca=marca, nombre="PSAMA")
        )
        self.assertTrue(salida.get("ok"), salida)
        sesion = db.SessionLocal()
        try:
            proyecto = sesion.query(ProyectoID).filter_by(
                nombre="PSAMA"
            ).first()
            proyecto.estado = "fallido"
            sesion.commit()
        finally:
            sesion.close()

        self._fijar_anio(2)
        # Mismo presupuesto: rechazado.
        salida = ProyectoService.crear_proyecto(
            self.equipos[0], 2, self._datos(marca=marca, nombre="PSAMA")
        )
        self.assertIn("error", salida)
        # Atributos distintos: rechazado.
        salida = ProyectoService.crear_proyecto(
            self.equipos[0], 2,
            self._datos(marca=marca, nombre="PSAMA",
                        atributos=_con_costo(90)),
        )
        self.assertIn("error", salida)
        # Mismo nombre, mismos atributos y más presupuesto: aceptado.
        salida = ProyectoService.crear_proyecto(
            self.equipos[0], 2,
            self._datos(marca=marca, nombre="PSAMA", presupuesto=150),
        )
        self.assertTrue(salida.get("ok"), salida)
        sesion = db.SessionLocal()
        try:
            intentos = sesion.query(ProyectoID).filter_by(
                equipo_id=self.equipos[0], nombre="PSAMA"
            ).count()
            self.assertEqual(intentos, 2)
        finally:
            sesion.close()

    def test_cancelar_proyecto(self):
        marca = self._marca()
        salida = ProyectoService.crear_proyecto(
            self.equipos[0], 1, self._datos(marca=marca)
        )
        proyecto_id = salida["proyecto_id"]
        self.assertTrue(
            ProyectoService.cancelar_proyecto(
                self.equipos[0], proyecto_id
            ).get("ok")
        )
        self.assertEqual(self._proyecto("PSAMA").estado, "cancelado")
        self.assertIn(
            "error",
            ProyectoService.cancelar_proyecto(self.equipos[0], proyecto_id),
        )


class TestEvaluacionProyectos(BaseID):
    def test_ronda_aprueba_proyecto(self):
        marca = self._marca()
        salida = ProyectoService.crear_proyecto(
            self.equipos[0], 1,
            self._datos(marca=marca, presupuesto=1000),
        )
        self.assertTrue(salida.get("ok"), salida)

        ronda = SimulacionService.procesar_ronda(self.industria_id)
        self.assertTrue(ronda.get("ok"), ronda)
        self.assertEqual(ronda["proyectos"]["evaluados"], 1)
        self.assertEqual(ronda["proyectos"]["aprobados"], 1)

        proyecto = self._proyecto("PSAMA")
        self.assertEqual(proyecto.estado, "aprobado")
        self.assertEqual(proyecto.anio_aprobacion, 2)

        sesion = db.SessionLocal()
        try:
            resultado = sesion.query(ProyectoResultado).filter_by(
                proyecto_id=proyecto.id
            ).first()
            self.assertEqual(resultado.resultado, "aprobado")
            self.assertAlmostEqual(resultado.probabilidad, 1.0, places=4)
            rep = sesion.query(Reporte).filter_by(
                equipo_id=self.equipos[0], anio=2
            ).first()
            self.assertGreaterEqual(rep.investigacion_total, 1000.0)
        finally:
            sesion.close()

    def test_ronda_registra_fracaso_automatico(self):
        marca = self._marca()
        atributos = _con_costo(500)
        atributos[1] = 5.1
        salida = ProyectoService.crear_proyecto(
            self.equipos[0], 1,
            self._datos(marca=marca, presupuesto=1000, atributos=atributos),
        )
        self.assertTrue(salida.get("ok"), salida)
        self.assertTrue(salida["estimacion"]["fracaso_automatico"])

        ronda = SimulacionService.procesar_ronda(self.industria_id)
        self.assertTrue(ronda.get("ok"), ronda)
        self.assertEqual(ronda["proyectos"]["aprobados"], 0)
        self.assertEqual(len(ronda["proyectos"]["fallidos"]), 1)

        proyecto = self._proyecto("PSAMA")
        self.assertEqual(proyecto.estado, "fallido")
        sesion = db.SessionLocal()
        try:
            resultado = sesion.query(ProyectoResultado).filter_by(
                proyecto_id=proyecto.id
            ).first()
            self.assertEqual(resultado.resultado, "fallido")
            self.assertEqual(resultado.atributo_fallido, 6)
            self.assertIsNotNone(resultado.costo_minimo)
        finally:
            sesion.close()


class TestAplicacionProyectos(BaseID):
    def _decisiones(self, marca, proyecto_nombre=""):
        decisiones = {}
        for item in self._marcas_equipo(self.equipos[0]):
            decisiones[item.nombre] = {
                "precio": 300, "publicidad": 2500, "produccion": 100,
                "proyecto_id": proyecto_nombre if item.id == marca.id else "",
                "objetivo_x": 0, "objetivo_y": 0,
                "vendedores": {1: 10, 2: 20, 3: 10},
            }
        return decisiones

    def _marcas_equipo(self, equipo_id):
        sesion = db.SessionLocal()
        try:
            return sesion.query(Marca).filter_by(
                equipo_id=equipo_id, activa=True
            ).order_by(Marca.id).all()
        finally:
            sesion.close()

    def test_aplicar_proyecto_a_marca_existente(self):
        marca = self._marca()
        salida = ProyectoService.crear_proyecto(
            self.equipos[0], 1, self._datos(marca=marca, presupuesto=1000)
        )
        self.assertTrue(salida.get("ok"), salida)
        self._aprobar(salida["proyecto_id"], 1)

        resultado = AlumnoService.guardar_decision(
            self.equipos[0], 1, self._decisiones(marca, "PSAMA"),
            canales_ids=[1, 2, 3], estado="enviada",
        )
        self.assertTrue(resultado.get("ok"), resultado)

        ronda = SimulacionService.procesar_ronda(self.industria_id)
        self.assertTrue(ronda.get("ok"), ronda)
        self.assertEqual(len(ronda["proyectos_aplicados"]["aplicados"]), 1)

        proyecto = self._proyecto("PSAMA")
        self.assertEqual(proyecto.estado, "aplicado")
        self.assertEqual(proyecto.anio_aplicacion, 2)

        sesion = db.SessionLocal()
        try:
            actualizada = sesion.query(Marca).filter_by(id=marca.id).first()
            self.assertAlmostEqual(actualizada.costo_unitario, 99.0, places=2)
            self.assertGreater(actualizada.calidad_actual, 0)

            atributos = sesion.query(AtributoFisico).filter_by(
                marca_id=marca.id, anio=2
            ).all()
            self.assertEqual(len(atributos), 6)
            costos = [a.valor for a in atributos if a.numero == 6]
            self.assertAlmostEqual(costos[0], 99.0, places=2)

            detalle = sesion.query(ReporteMarca).filter_by(
                marca_nombre=marca.nombre
            ).join(Reporte).filter(Reporte.anio == 2).first()
            self.assertAlmostEqual(detalle.costo_transferencia, 99.0, places=2)
        finally:
            sesion.close()

    def test_no_se_puede_usar_proyecto_no_aprobado(self):
        marca = self._marca()
        salida = ProyectoService.crear_proyecto(
            self.equipos[0], 1, self._datos(marca=marca)
        )
        self.assertTrue(salida.get("ok"), salida)
        resultado = AlumnoService.guardar_decision(
            self.equipos[0], 1, self._decisiones(marca, "PSAMA"),
            canales_ids=[1, 2, 3], estado="enviada",
        )
        self.assertIn("error", resultado)

    def test_lanzar_marca_nueva_con_proyecto_aprobado(self):
        salida = ProyectoService.crear_proyecto(
            self.equipos[0], 1,
            self._datos(marca_nueva="SAMA", nombre="PSAMA", presupuesto=1000),
        )
        self.assertTrue(salida.get("ok"), salida)
        self._aprobar(salida["proyecto_id"], 1)

        decisiones = self._decisiones(self._marca(), "")
        decisiones["SAMA"] = {
            "precio": 320, "publicidad": 1500, "produccion": 120,
            "proyecto_id": "PSAMA", "objetivo_x": 0, "objetivo_y": 0,
            "vendedores": {1: 5, 2: 10, 3: 5},
        }
        resultado = AlumnoService.guardar_decision(
            self.equipos[0], 1, decisiones,
            canales_ids=[1, 2, 3], estado="enviada",
        )
        self.assertTrue(resultado.get("ok"), resultado)

        ronda = SimulacionService.procesar_ronda(self.industria_id)
        self.assertTrue(ronda.get("ok"), ronda)
        self.assertEqual(len(ronda["proyectos_aplicados"]["marcas_nuevas"]), 1)

        sesion = db.SessionLocal()
        try:
            nueva = sesion.query(Marca).filter_by(
                equipo_id=self.equipos[0], nombre="SAMA"
            ).first()
            self.assertIsNotNone(nueva)
            self.assertTrue(nueva.activa)
            self.assertEqual(nueva.anio_lanzamiento, 2)
            self.assertAlmostEqual(nueva.costo_unitario, 99.0, places=2)
            self.assertEqual(
                sesion.query(FuerzaVentas).filter_by(marca_id=nueva.id).count(),
                3,
            )
            self.assertEqual(
                sesion.query(AtributoFisico).filter_by(
                    marca_id=nueva.id, anio=2
                ).count(),
                6,
            )
            detalle = sesion.query(ReporteMarca).filter_by(
                marca_nombre="SAMA"
            ).join(Reporte).filter(Reporte.anio == 2).first()
            self.assertIsNotNone(detalle)
            self.assertAlmostEqual(detalle.costo_transferencia, 99.0, places=2)
        finally:
            sesion.close()

    def test_marca_nueva_sin_proyecto_es_rechazada(self):
        decisiones = self._decisiones(self._marca(), "")
        decisiones["SAMA"] = {
            "precio": 320, "publicidad": 1500, "produccion": 120,
            "proyecto_id": "", "objetivo_x": 0, "objetivo_y": 0,
            "vendedores": {1: 5, 2: 10, 3: 5},
        }
        resultado = AlumnoService.guardar_decision(
            self.equipos[0], 1, decisiones,
            canales_ids=[1, 2, 3], estado="enviada",
        )
        self.assertIn("error", resultado)


class TestRutasID(BaseWeb):
    def _fijar_anio(self, anio):
        sesion = db.SessionLocal()
        try:
            industria = sesion.query(Industria).filter_by(
                id=self.ids["ind_a"]
            ).first()
            industria.anio_actual = anio
            industria.estado = "en_curso"
            industria.permitir_envio = True
            sesion.commit()
        finally:
            sesion.close()

    def test_pantalla_alumno(self):
        self._fijar_anio(1)
        self.login("alumno_a", rol="alumno")
        respuesta = self.client.get("/alumno/proyectos")
        self.assertEqual(respuesta.status_code, 200)
        html = respuesta.get_data(as_text=True)
        self.assertIn("Centro de I+D", html)
        self.assertIn("Registrar un proyecto", html)

    def test_crear_proyecto_desde_ruta(self):
        self._fijar_anio(1)
        self.login("alumno_a", rol="alumno")
        token = self.csrf()
        datos = {
            "csrf_token": token,
            "nombre": "PSAMA",
            "marca_id": "",
            "marca_nueva": "SAMA",
            "presupuesto": "1000",
            "atributo_1": "10",
            "atributo_2": "5",
            "atributo_3": "50",
            "atributo_4": "20",
            "atributo_5": "20",
            "atributo_6": "99",
        }
        respuesta = self.client.post("/alumno/proyectos/crear", data=datos)
        self.assertEqual(respuesta.status_code, 302)

        sesion = db.SessionLocal()
        try:
            proyecto = sesion.query(ProyectoID).filter_by(
                equipo_id=self.ids["eq_a"], nombre="PSAMA"
            ).first()
            self.assertIsNotNone(proyecto)
            self.assertTrue(proyecto.es_nueva_marca)
            self.assertEqual(proyecto.estado, "en_desarrollo")
        finally:
            sesion.close()

    def test_pantalla_profesor(self):
        self._fijar_anio(1)
        self.login("profe_a", rol="profesor")
        respuesta = self.client.get(
            f"/profesor/simulaciones/{self.ids['ind_a']}/proyectos"
        )
        self.assertEqual(respuesta.status_code, 200)
        html = respuesta.get_data(as_text=True)
        self.assertIn("Proyectos de I+D", html)

    def test_profesor_no_ve_otra_industria(self):
        self.login("profe_a", rol="profesor")
        respuesta = self.client.get(
            f"/profesor/simulaciones/{self.ids['ind_b']}/proyectos"
        )
        self.assertEqual(respuesta.status_code, 302)


if __name__ == "__main__":
    unittest.main()
