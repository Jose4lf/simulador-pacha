# Informe de cierre — Etapa 1: integridad y estabilidad

**Fecha:** 2026-10-28
**Alcance:** copia de seguridad, detección visible de BD, FK en SQLite, sesiones, Alembic base, auditoría y pruebas de humo.
**Restricción respetada:** sin commits ni push; todos los cambios quedaron en el working tree local.

---

## 1. Respaldos creados

| Elemento | Ruta | Tamaño | Verificación |
|---|---|---|---|
| Proyecto (sin `.venv`, `.git`, `instance`) | `B:\Proyectos\PACHA_SIMULADOR_BACKUPS\etapa1_20261028_141348\proyecto.tar.gz` | 974 KB | `tar -tzf` correcto |
| PostgreSQL `pacha_db` | `B:\Proyectos\PACHA_SIMULADOR_BACKUPS\etapa1_20261028_141348\pacha_db.dump` | 117 KB | formato custom, `pg_restore --list` OK |

Restauración de la BD:

```
"C:\Program Files\PostgreSQL\16\bin\pg_restore.exe" -h localhost -U pacha_user -d pacha_db --clean --if-exists pacha_db.dump
```

---

## 2. Cambios implementados

### 2.1 `infraestructura/database.py`
- `enmascarar_url()`: oculta la contraseña en logs y en la UI (`postgresql://pacha_user:***@localhost:5432/pacha_db`).
- `DB_ES_FALLBACK`: distingue explícitamente el modo respaldo.
- `get_db_info()`: información segura del motor para plantillas y `/health`.
- `PRAGMA foreign_keys=ON` en cada conexión SQLite mediante listener de SQLAlchemy.
- `_crear_sqlite_fallback(url=None)`: permite inyectar una URL (usado por las pruebas).
- Aviso visible en consola cuando se activa el respaldo SQLite.
- `close_session()` documentado como liberación de la sesión `scoped_session`.

### 2.2 `presentacion/web/__init__.py`
- Context processor `db_info` disponible en todas las plantillas.
- `teardown_appcontext` que llama a `close_session()`.
- Endpoint `GET /health` → `{"ok", "motor", "fallback"}`, sin credenciales.

### 2.3 Plantillas
- `presentacion/web/templates/partials/db_badge.html`: indicador fijo con el motor activo; amarillo y con el texto «RESPALDO SQLITE» cuando corresponde.
- Incluido en `alumno/panel.html`, `profesor/panel.html`, `decano/panel.html` y `auth/login.html`.

### 2.4 Auditoría de integridad
- `infraestructura/auditoria.py`: verificaciones de solo lectura (esquema, columnas, huérfanos, catálogos, reportes, decisiones, compras y logs).
- `scripts/auditar_integridad.py`: CLI con salida de texto y `--json` (JSON puro; los mensajes de arranque van a stderr). Devuelve código 1 si hay `FAIL`.

### 2.5 Alembic
- `alembic.ini`, `migrations/env.py`, `migrations/script.py.mako`, `migrations/README`.
- `migrations/versions/8dc8813663d2_baseline.py`: migración base con las 35 tablas, ajustada para el ciclo `usuarios`–`equipos`–`industrias` y para `proyectos`.
- `migrations/versions/3aa04a4f8466_fk_proyectos.py`: agrega las dos FK que faltaban en `proyectos`.
- Esquema marcado con `alembic stamp head`; revisión actual: `3aa04a4f8466`.
- `alembic check` → «No new upgrade operations detected.» (solo emite un `SAWarning` por el ciclo de FK, esperado).

> **Excepción documentada:** se aplicó DDL sobre la tabla existente `proyectos` (2 FK). La tabla tenía **0 filas**, por lo que el riesgo era nulo. Reversión puntual:
> `.venv/Scripts/alembic.exe downgrade 8dc8813663d2`
> No ejecutar `downgrade base` sobre la BD real: la base está marcada con `stamp`, no creada por Alembic, y el downgrade base borraría las tablas.

### 2.6 Pruebas
- `tests/__init__.py` y `tests/test_etapa1.py` (10 pruebas, `unittest`, SQLite temporal; no tocan PostgreSQL).
- Cobertura: enmascarado de URL, `/health`, FK activas, rechazo de huérfanos, estructura de la auditoría, detección de tablas faltantes y ausencia de credenciales en `/health`.

---

## 3. Evidencia de ejecución real

```
$ PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m unittest discover -s tests
Ran 10 tests in 19.022s
OK

$ PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/auditar_integridad.py
Resumen: 14 OK | 12 advertencias | 0 fallos
RC=0

$ PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -c "import run; ..."
HEALTH: 200 {'fallback': False, 'motor': 'postgresql', 'ok': True}
RAIZ: 200
BADGE_OK: True

$ .venv/Scripts/alembic.exe current
3aa04a4f8466 (head)
```

Estado de datos tras la Etapa 1 (sin cambios respecto del inicio):

| Tabla | Filas |
|---|---|
| usuarios | 8 |
| equipos | 3 |
| marcas | 6 |
| industrias | 1 |
| segmentos | 5 |
| canales | 3 |
| reportes | 3 |
| reporte_marca | 6 |
| reporte_marca_canal | 18 |
| reporte_marca_segmento | 0 |
| decisiones / decision_marca | 0 / 0 |
| compras_estudios | 0 |
| logs_actividad | 0 |
| proyectos | 0 |

---

## 4. Advertencias de la auditoría (no bloqueantes)

1. **Ingresos incoherentes** en los reportes de Año 0 (SAKA, SATO, SEKA, SETO, SIKA, SITO): `ingresos` no equivale a `precio × unidades`. Es un dato heredado del estado actual, no generado por esta etapa.
2. **Contribución incoherente** en SETO (diferencia de 20.000).
3. **Participación de mercado** de CREAD Año 0 suma 54% en lugar de ~100%.
4. **Sin reportes por segmento** (`reporte_marca_segmento` vacío): funcionalidad pendiente de Etapas 4–5.
5. **Sin decisiones, compras de estudios ni logs**: flujos aún no ejercitados.

Ninguna de estas advertencias es un fallo de integridad referencial: los 12 chequeos de huérfanos y el esquema dieron `OK`.

---

## 5. Archivos creados / modificados

Creados:
- `infraestructura/auditoria.py`
- `scripts/auditar_integridad.py`
- `alembic.ini`
- `migrations/` (env, script, README, 2 versiones)
- `presentacion/web/templates/partials/db_badge.html`
- `tests/__init__.py`, `tests/test_etapa1.py`

Modificados:
- `infraestructura/database.py`
- `presentacion/web/__init__.py`
- `presentacion/web/templates/{alumno,profesor,decano}/panel.html` (1 línea cada uno)
- `presentacion/web/templates/auth/login.html` (1 línea)

Sin cambios en los archivos locales previos del propietario (`aplicacion/profesor_service.py`, `core/motor_simulacion.py`, `inicializar_sistema.py`, `manual.html`, `reporte.html`).

---

## 6. Riesgos y observaciones

- La migración base está pensada para PostgreSQL; SQLite se sigue creando con `create_all` y ahora tiene FK activas.
- `alembic check` emite `SAWarning` por el ciclo `equipos`–`industrias`–`usuarios`. No impide operar, pero conviene resolverlo en una etapa posterior (por ejemplo, `use_alter` o FKs diferidas).
- `/health` responde `ok: false` si se crea la app sin inicializar la BD (por ejemplo, `flask --app presentacion.web`). Con `run.py`/Gunicorn siempre reporta el motor real.
- Las contraseñas fijas (`Admin/321`, `alumno123`, `PASSWORD`, `123`, `pacha2026`) siguen vigentes: se corrigen en la Etapa 2.
- `requirements.txt` permanece en UTF-16 LE con CRLF, sin conversión.

---

## 7. Pendientes para la Etapa 2

1. Hash de contraseñas y cambio obligatorio en el primer login.
2. Contraseñas temporales aleatorias, sin exponerlas en logs.
3. Aislamiento estricto profesor/estudiante y verificación de rol en todas las rutas.
4. Protección CSRF y política de sesiones.
5. Documentar la regla de ausencia y decisión efectiva única.

---

## 8. Estado

**Etapa 1 cerrada.** Sin fallos de integridad, 10 pruebas en verde, aplicación arrancando contra PostgreSQL y respaldos verificados. Se detiene aquí a la espera de autorización para la Etapa 2.
