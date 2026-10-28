"""
Pruebas de la Etapa 4: reporte de Año 0 con unidades coherentes.

No tocan PostgreSQL: usan SQLite temporal.
Ejecutar con:
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m unittest discover -s tests -v
"""
import unittest

import infraestructura.database as db
from aplicacion.profesor_service import ProfesorService
from core.models import (
    AtributoFisico, Industria, Marca, Reporte, ReporteMarca,
    ReporteMarcaCanal, ReporteMarcaSegmento,
)
from core.reportes_anio0 import (
    MERCADO_BASE, factor_participacion, generar_reporte_anio0,
    porciones_equipo,
)
from tests.test_etapa3 import BaseDominio


ATRIBUTOS = {
    "MA1": [11, 9, 20, 25, 10, 100],
    "MB1": [12, 9, 37, 25, 30, 125],
    "MA2": [18, 7, 51, 30, 85, 160],
    "MB2": [14, 5, 65, 40, 90, 200],
}


class TestPorciones(unittest.TestCase):
    def test_porciones_historicas(self):
        self.assertEqual(porciones_equipo(1, 2), [11.0, 4.0])
        self.assertEqual(porciones_equipo(5, 2), [5.0, 2.0])

    def test_marcas_extra_no_roban_participacion(self):
        valores = porciones_equipo(1, 4)
        self.assertEqual(len(valores), 4)
        self.assertEqual(sum(valores), 15.0)


class TestReporteAnio0(BaseDominio):
    def setUp(self):
        super().setUp()
        sesion = db.SessionLocal()
        try:
            for marca in sesion.query(Marca).all():
                for numero, valor in enumerate(ATRIBUTOS[marca.nombre], start=1):
                    sesion.add(AtributoFisico(
                        marca_id=marca.id, numero=numero, valor=valor, anio=0
                    ))
            sesion.commit()
        finally:
            sesion.close()

    def test_unidades_coherentes(self):
        sesion = db.SessionLocal()
        try:
            industria = sesion.query(Industria).filter_by(
                id=self.industria_id
            ).first()
            from core.models import Equipo
            equipo = sesion.query(Equipo).filter_by(id=self.equipos[0]).first()
            rep = generar_reporte_anio0(sesion, equipo, industria)

            self.assertAlmostEqual(rep.mercado_total, MERCADO_BASE)
            ventas = sum(m.unidades_vendidas for m in rep.marcas)
            produccion = sum(m.produccion for m in rep.marcas)
            self.assertAlmostEqual(ventas, produccion)
            esperado = MERCADO_BASE / 1000.0 * sum(
                porciones_equipo(equipo.numero, len(rep.marcas))
            ) * factor_participacion(sesion, industria) / 100.0
            self.assertAlmostEqual(ventas, esperado, places=1)
            for rm in rep.marcas:
                self.assertAlmostEqual(rm.inventario, 0.0)
                self.assertAlmostEqual(
                    rm.ingresos, rm.precio_final * rm.unidades_vendidas, places=1
                )
                costo_fv = sum(c.vendedores for c in rm.canales) * 30.6
                esperada = (
                    rm.ingresos - rm.costo_productos_vendidos
                    - rm.costo_inventario - rm.publicidad - costo_fv
                )
                self.assertAlmostEqual(
                    rm.contribucion_bruta_marketing, esperada, places=1
                )
                self.assertAlmostEqual(
                    sum(c.ventas_unidades for c in rm.canales),
                    rm.unidades_vendidas, places=1,
                )
                self.assertAlmostEqual(
                    sum(s.ventas_unidades for s in rm.segmentos),
                    rm.unidades_vendidas, places=1,
                )
            self.assertAlmostEqual(
                rep.contribucion_neta_total,
                rep.contribucion_bruta_total - 500 * len(rep.marcas),
                places=1,
            )
        finally:
            sesion.close()

    def test_participacion_suma_cien(self):
        sesion = db.SessionLocal()
        try:
            industria = sesion.query(Industria).filter_by(
                id=self.industria_id
            ).first()
            from core.models import Equipo
            total = 0.0
            for equipo in sesion.query(Equipo).filter_by(
                industria_id=industria.id
            ).all():
                rep = generar_reporte_anio0(sesion, equipo, industria)
                total += sum(m.porcion_mercado for m in rep.marcas)
            self.assertAlmostEqual(total, 100.0, places=4)
        finally:
            sesion.close()


class TestCrearIndustria(BaseDominio):
    def test_crear_industria_genera_reporte_consistente(self):
        sesion = db.SessionLocal()
        try:
            from core.models import Usuario
            profe = Usuario(
                username="profe_etapa4", password_hash="x", rol="profesor",
                nombre="Profe 4", activo=True, debe_cambiar_password=False,
            )
            sesion.add(profe)
            sesion.commit()
            profe_id = profe.id
        finally:
            sesion.close()

        salida = ProfesorService.crear_industria(profe_id, "Industria Etapa 4", 3)
        self.assertTrue(salida.get("ok"), salida)

        sesion = db.SessionLocal()
        try:
            reportes = sesion.query(Reporte).filter(
                Reporte.anio == 0,
                Reporte.equipo.has(industria_id=salida["industria_id"]),
            ).all()
            self.assertEqual(len(reportes), 3)
            for rep in reportes:
                self.assertEqual(len(rep.marcas), 2)
                for rm in rep.marcas:
                    self.assertEqual(len(rm.canales), 3)
                    self.assertEqual(len(rm.segmentos), 5)
                    self.assertAlmostEqual(
                        rm.ingresos,
                        rm.precio_final * rm.unidades_vendidas,
                        places=1,
                    )
                    self.assertAlmostEqual(rm.inventario, 0.0)
        finally:
            sesion.close()


if __name__ == "__main__":
    unittest.main()
