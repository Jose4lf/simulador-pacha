# Fase 0 — Inventario y clasificación de referencias heredadas

**Fecha:** 2026-10-28
**Alcance:** referencias a `LABSAG`, `Markestrated`, `SONITE` y `VODITE` en
código, plantillas, datos y documentación del repositorio.

## Respaldos previos

| Origen | Archivo |
|---|---|
| PostgreSQL local (`pacha_db`) | `PACHA_SIMULADOR_BACKUPS\transformacion_bolivia_20261028_193811\pacha_local_pre_transformacion.dump` |
| PostgreSQL de Render | `PACHA_SIMULADOR_BACKUPS\transformacion_bolivia_20261028_193811\pacha_render_pre_transformacion.dump` |

Ningún paso de la transformación hace `DROP`. La migración es aditiva.

## Conteo

165 ocurrencias en 19 archivos:

| Archivo | Ocurrencias | Categoría | Acción |
|---|---:|---|---|
| `presentacion/web/templates/alumno/manual.html` | 58 | C. Texto visible | Reescribir manual |
| `scripts/cargar_estudios_mercado.py` | 27 | B. Semilla | Reemplazar por el escenario |
| `inicializar_sistema.py` | 22 | B. Semilla | Cambiar código y nombre del simulador |
| `core/generador_nombres.py` | 12 | A. Código activo | Sustituir por nombres del catálogo |
| `core/modelo_id.py` | 8 | A. Código activo | Redefinir atributos y rangos |
| `aplicacion/proyecto_service.py` | 6 | A. Código activo | Adaptar a atributos de helado |
| `tests/test_etapa3.py` | 5 | E. Pruebas | Actualizar expectativas |
| `core/motor_simulacion.py` | 5 | A. Código activo | Reescribir el motor |
| `presentacion/web/templates/profesor/nueva_simulacion.html` | 4 | C. Texto visible | Identidad nueva |
| `core/models.py` | 4 | A. Código activo | Documentación y valores por defecto |
| `core/escenarios.py` | 4 | A. Código muerto | Retirar |
| `aplicacion/profesor_service.py` | 3 | A. Código activo | Semillas y valores por defecto |
| `presentacion/web/templates/alumno/reporte.html` | 2 | C. Texto visible | Identidad nueva |
| `AGENTS.md` | 2 | D. Documentación | Actualizar |
| `presentacion/web/templates/profesor/manual.html` | 1 | C. Texto visible | Identidad nueva |
| `presentacion/web/templates/alumno/panel.html` | 1 | C. Texto visible | Identidad nueva |
| `presentacion/web/blueprints/profesor/routes.py` | 1 | A. Código activo | Código por defecto del escenario |
| `core/reportes_anio0.py` | 1 | A. Código activo | Participaciones iniciales |
| `core/generador_estudios.py` | 1 | A. Código activo | Nombres de estudio |

## Clasificación por naturaleza

### A. Código activo (se ejecuta y define valores)

| Archivo | Qué fija hoy | Destino |
|---|---|---|
| `core/motor_simulacion.py` | Mercado base 1.300.000, constantes de costo, fórmulas de atractivo | Motor nuevo leído de `core/escenario.py` |
| `core/modelo_id.py` | Rangos SONITE (peso, diseño, volumen, frecuencia, potencia) | Rangos de helado (composición, porción, calidad, cremosidad, empaque, costo) |
| `aplicacion/profesor_service.py` | `DEFAULT_SEGMENTOS`, `DEFAULT_CANALES`, `PERFILES_MARKETING`, `ATRIBUTOS_FISICOS_INICIALES`, `crear_industria` | Leer del escenario y del catálogo |
| `core/generador_nombres.py` | Nombres `SAKA`, `SATO`, `SERI`… | Nombres del catálogo |
| `core/generador_estudios.py` | Estudio 7 reutiliza el 1 (VODITE) | 15 estudios propios, 1:1 |
| `core/models.py` | `tipo="SONITE"`, `simulador_codigo="markestrated"` | `HELADO`, `mundo_markestrat_bolivia` |
| `core/reportes_anio0.py` | Participaciones históricas 11/4, 8/6, 15/10, 20/15, 5/2 | Participaciones del escenario |
| `aplicacion/simulacion_service.py` | `mercado_total: 1300000` hardcodeado | `escenario.mercado_potencial()` |
| `core/escenarios.py` | Preset no leído con datos heredados | Retirar en Fase 4 |
| `presentacion/web/blueprints/profesor/routes.py` | `"markestrated"` por defecto en el formulario | Código del escenario |

### B. Dato almacenado o en semilla

| Archivo / tabla | Dato | Acción |
|---|---|---|
| `inicializar_sistema.py` → `simuladores` | `codigo="markestrated"`, nombre «Markestrated - Estrategia de Marketing» | Insertar `mundo_markestrat_bolivia` y conservar el anterior |
| `scripts/cargar_estudios_mercado.py` → `estudios_mercado` | 15 estudios SONITE/VODITE | Upsert con los 15 estudios de helado |
| `industrias.simulador_codigo` | `markestrated` en industrias existentes | No se toca (simulaciones viejas intactas) |

### C. Texto visible en plantillas

| Archivo | Texto | Acción |
|---|---|---|
| `alumno/manual.html` | «MARKESTRATED», marca, instrucciones SONITE/VODITE | Reescribir para helados |
| `alumno/panel.html`, `alumno/reporte.html` | Subtítulo «MARKESTRATED» | «EL MUNDO DE MARKESTRAT BOLIVIA» |
| `profesor/manual.html` | Referencia al Año 0 de Markestrated | Adaptar |
| `profesor/nueva_simulacion.html` | Opción única «Markestrated» y bloque de escenario | Escenario de helados |

### D. Documentación

| Archivo | Acción |
|---|---|
| `AGENTS.md` | Actualizar tras la Fase 4 |
| `docs/transformacion/*` | Documento histórico; conserva las menciones a propósito |

### E. Pruebas

| Archivo | Acción |
|---|---|
| `tests/test_etapa3.py` | Nombres de marca y valores esperados del escenario nuevo |

## Referencias que se conservan a propósito

- `docs/transformacion/fase0_referencias.md`: este inventario debe poder nombrar
  lo que se retiró.
- Historial de Git y respaldos: no se reescribe.
- Comentarios que documentan una decisión de diseño («no reproduce fórmulas de
  LABSAG») se reemplazan por la descripción del motor propio; no se mantiene la
  comparación.

## Criterio de cierre de la fase

1. `grep -ri "labsag\|markestrated\|sonite\|vodite"` no devuelve resultados en
   `aplicacion/`, `core/`, `presentacion/`, `scripts/`, `tests/` ni
   `inicializar_sistema.py`.
2. Las únicas coincidencias permitidas están en `docs/transformacion/`,
   `AGENTS.md` (si documenta el cambio) y el historial de Git.
3. La suite completa pasa y `alembic check` no detecta diferencias.
