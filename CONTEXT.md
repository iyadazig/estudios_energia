# CONTEXT.md — Guía de continuación del proyecto (para desarrolladores e IAs)

Este documento reúne el conocimiento necesario para **continuar el desarrollo** de la
aplicación: arquitectura, lógica de dominio, decisiones tomadas (y por qué), trampas conocidas,
cómo verificar los cambios y qué queda pendiente. El `README.md` cubre instalación y uso; este
documento cubre el "cómo está hecho y por qué".

---

## 1. Qué es y para quién

Aplicación web interna de **GE&PE Ingeniería** (geype.com) para hacer **estudios de renovación
de contratos eléctricos**: compara el coste **anual sin IVA** del contrato actual de un cliente
frente a las ofertas de varias comercializadoras, a partir del consumo histórico y de los
parámetros regulados vigentes. Exporta a Excel y PDF. Uso interno, pocos usuarios de confianza.

Sustituye a un proceso manual en hojas de Excel gigantes (una por cliente).

## 2. Estado actual

- **Fase 1 COMPLETA y verificada**: expedientes, importación Excel, motor de cálculo, comparativo,
  exportación Excel/PDF, catálogo de ofertas, parámetros regulados, SSAA por oferta, rediseño
  visual corporativo, portada con KPIs/filtros/roles, gestión de usuarios in-app.
- **31 tests** en verde (`python manage.py test estudios`).
- **Despliegue preparado** (WhiteNoise + Gunicorn + `render.yaml` + `build.sh`); aún no publicado.
- **Solo precio fijo**. El **precio indexado** (OMIE/ESIOS) es fase futura y NO está implementado.

## 3. Stack y arranque rápido

Python 3.12 · Django 6.0 · SQLite · openpyxl (Excel) · xhtml2pdf+Pillow (PDF) · python-decouple
(.env) · WhiteNoise+Gunicorn (prod). Front: HTML + CSS propio (`static/css/app.css`, sistema de
diseño con variables) + JS vanilla. Sin framework de front ni Node.

Arranque: ver `README.md`. En corto: crear venv, `pip install -r requirements.txt`, copiar
`.env.example`→`.env` con `SECRET_KEY`, `migrate`, `cargar_parametros_2026` (o `seed_demo`),
`runserver`. Datos y credenciales de prueba: `python manage.py seed_demo` (usuarios `demo` y
`tecnico`, contraseña `Demo.2026`).

## 4. Mapa de módulos (`estudios/`)

| Archivo | Responsabilidad |
|---|---|
| `models.py` | Entidades (ver §5). |
| `calculo.py` | **Motor de cálculo** del comparativo (núcleo de dominio, ver §6). |
| `consumo.py` | Prepara los datos de consumo (agrega por mes/periodo) para informes. |
| `exportar.py` | Genera el **Excel** (openpyxl) y el **PDF** (xhtml2pdf) del comparativo. |
| `graficos.py` | Dibuja con Pillow el gráfico de barras apilado que se incrusta en el PDF. |
| `importador.py` | Lee la plantilla Excel del estudio (Cliente/Suministros/Consumos); valida CUPS. |
| `parametros_excel.py` | Plantilla e importación masiva de parámetros regulados. |
| `forms.py` | Formularios (Expediente, Oferta, conceptos formset, catálogo, **usuarios**). |
| `views.py` | Vistas: inicio (KPIs/filtros), expedientes, ofertas, catálogo, parámetros, usuarios, export. |
| `admin.py` | Panel de administración de Django (alta de usuarios y retoques de parámetros). |
| `tests.py` | 31 tests: motor de cálculo al céntimo, validación CUPS, portada, usuarios. |
| `management/commands/` | `cargar_parametros_2026`, `copia_seguridad`, `seed_demo`. |
| `templatetags/estudios_extras.py` | Filtros `dict_get` e `incluye` (para el comparativo). |

Plantillas en `templates/` (base + una por pantalla; `informe_pdf.html` es SOLO para el PDF, no
comparte el CSS de `app.css`). Config Django en `config/` (`settings.py`, `urls.py`, `wsgi.py`).

## 5. Modelo de datos

- **Expediente** (código auto `EXP-AAAA-NNNN`, cliente, `gestor` = técnico FK a User, `estado`
  abierto/cerrado, `oferta_adjudicataria`, `archivo_original` = copia del Excel subido).
- **PuntoSuministro** (CUPS): tarifa 2.0TD–6.4TD, potencias P1–P6, contrato actual (precios de
  energía, `potencia_segun_atr`, `energia_peajes_incluidos`).
- **ConsumoMensual**: por punto, año + mes + P1–P6 (kWh).
- **Oferta** y **OfertaCatalogo** heredan de `CondicionesOfertaBase` (abstracta): comercializadora,
  duración, GdO, flags ATR y **toda la configuración SSAA** (`ssaa_tipo`, `ssaa_modo`, referencias,
  pérdidas, apuntamiento, impuesto municipal).
- **PrecioOferta** / **PrecioCatalogo**: precios P1–P6 por **tarifa** (y PrecioOferta también por
  CUPS concreto).
- **ConceptoAdicional** / **ConceptoCatalogo** heredan de `ConceptoBase`: nombre, tipo
  (€/MWh, €/mes, %), con_perdidas, con_impuesto_local, entra_en_iee.
- Parámetros regulados: **ParametroRegulado** (peaje/cargo/pérdidas/imp_local por tarifa+término+
  vigencia), **ParametroGeneral** (IEE), **SerieSSAA** (estimado mensual, `mes` único), **ProfileFactor**
  (perfiles horarios por mes y periodo). Todos con **vigencia** / versionados; se validan en el admin.

Las clases base abstractas evitan duplicar los ~13 campos entre Oferta y OfertaCatalogo. **Ojo:**
al tocar esos campos, `makemigrations` no debe alterar la tabla `oferta` (verificarlo).

## 6. El motor de cálculo (`calculo.py`) — lo más importante

Para cada oferta y cada CUPS calcula un `Desglose(potencia, energia, conceptos, ssaa, iee, total)`:

- **`total = potencia + energia + conceptos_total + ssaa + iee`** (sin IVA).
- **Potencia**: si el contrato va "según ATR" se aplican los peajes+cargos regulados vigentes;
  si no, precios propios. Coste anual.
- **Energía**: precio × consumo por periodo; si los peajes NO van incluidos se suman los ATR.
- **Parámetros vigentes por fecha**: `_parametro_vigente(tipo, término, tarifa, fecha)` elige el
  valor con `vigencia_inicio ≤ fecha` (y `vigencia_fin` nula o posterior).
- **SSAA** (Servicios de Ajuste), `coste_ssaa`: 0 si `ssaa_tipo == "incluido"`. Si no, por cada mes
  y periodo:
  `dif × (1 + pérdidas_p) × apuntamiento × (kWh_p / 1000) × HL`, donde
  - `dif` (`_diferencia_ssaa`): **techo** = `SSAA − ref_sup` si `SSAA > ref_sup` (si no 0);
    **banda** = `SSAA − ref_sup` si supera, `SSAA − ref_inf` si baja, 0 dentro; **indexado** = `SSAA`.
    Puede ser **negativo** (abono) en banda.
  - `pérdidas_p`: fijas (% que teclea el técnico) o Circular CNMC 3/2020 por periodo.
  - `apuntamiento`: constante sin unidades (vacío = 1).
  - `HL = (1 + impuesto_local)` (= ×1,015) si `ssaa_impuesto_municipal`, si no 1.
  - `SSAA` base = `SerieSSAA` del mes; en **modo horario** se reparte por periodos multiplicando por
    el `ProfileFactor(mes, periodo)`.
  El SSAA entra en la **base del IEE** y se muestra como línea propia "Regularización SSAA".
- **Conceptos adicionales**: €/MWh sobre consumo (con pérdidas opcional), €/mes fijo, o % sobre
  subtotal; con `× impuesto_local` opcional; `entra_en_iee` decide si suma a la base del IEE.
- **IEE**: impuesto especial (≈5,11 %) sobre la base (energía + potencia + conceptos/SSAA que
  entren en IEE).
- `comparativo_expediente(expediente)` devuelve el comparativo **agregado** y **por CUPS**, con
  ranking (más barata primero), ahorro y % frente al contrato actual, y `avisos`. **Es costoso**
  (recorre consumos y parámetros): NO llamarlo en bucles ni en la portada.

Convención: pérdidas, IEE e impuesto local se guardan en **tanto por uno** (0,015 = 1,5 %), no en %.

## 7. Decisiones de diseño (y por qué)

- **Acceso "todos ven todo"**: no hay aislamiento por gestor a nivel de permisos; cualquier usuario
  puede ver/editar cualquier expediente (uso interno). El filtro "Mis expedientes" de la portada es
  solo una vista por defecto, NO control de acceso. Roles = `is_staff` (admin) vs normal (técnico).
- **SSAA estimada por mes** (no por año): la `SerieSSAA` es un perfil mensual con `mes` único.
- **Solo precio fijo** en Fase 1. Indexado = Fase 3.
- **Impuesto local (1,5 %) NO se aplica** al comparativo de precio fijo (la metodología del Excel
  real solo lo usa en indexado). Queda almacenado. **Decisión pendiente** de la usuaria.
- **SQLite** (suficiente para el volumen interno; migrable a PostgreSQL sin tocar la app).
- **CSS externalizado** a `static/css/app.css` con sistema de tokens; el PDF (`informe_pdf.html`)
  tiene su propio estilo embebido (xhtml2pdf no comparte ese CSS).
- **Gama pastel** en los gráficos (Excel, PDF y pantalla), con contrato actual en gris y mejor
  oferta en verde.

## 8. Trampas conocidas (gotchas)

- **Localización es-ES**: `USE_THOUSAND_SEPARATOR=True`. Cuidado al escribir números en CSS o en
  `value` de inputs: la coma decimal puede romper cosas (`_parse_precio_post` convierte coma→punto).
- **StatReloader en Windows** a veces no recarga al cambiar `config/urls.py` → reiniciar `runserver`.
- **xhtml2pdf es limitado**: ignora `width` en `<div>` y revienta con tablas anidadas estrechas;
  por eso el gráfico del PDF se dibuja con Pillow (`graficos.py`) y se incrusta como imagen, y las
  tablas usan anchos fijos.
- **`build.sh` debe ir con saltos de línea LF** (lo fuerza `.gitattributes`); con CRLF fallaría en Linux.
- **Despliegue en plan gratuito** = disco efímero (SQLite se reinicia en cada deploy); por eso
  `build.sh` ejecuta `seed_demo` en cada build. Para producción real: servidor con disco persistente.
- `seed_demo` es **solo para demo**; crea datos sintéticos. No usar en la instalación de la empresa.

## 9. Cómo verificar los cambios

- **Tests**: `python manage.py test estudios` (31; deben seguir en verde). El motor de cálculo se
  verifica **al céntimo** contra una aritmética de referencia independiente escrita en el propio test.
- **Comprobación de despliegue**: `python manage.py check --deploy` (con `DEBUG=False`).
- **Verificación visual sin Selenium/Playwright** (no instalados): renderizar el HTML con el *test
  client* de Django y capturar con **Chrome headless**
  (`%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe --headless=new --screenshot`). Para que el
  CSS cargue en la captura, reescribir las rutas `/static/` a `file://` absolutas, o capturar contra
  `runserver`.
- **Excel/PDF a imagen** para revisarlos: en este entorno Windows se usa **Excel/PowerPoint COM**
  (`win32com`) para exportar a PDF y luego **PyMuPDF (`fitz`)** para rasterizar (fitz está en el
  Python de Anaconda, no en el venv del proyecto).

## 10. Roadmap / pendientes

- **Prueba con factura real** (criterio de aceptación Fase 1: desviación < 1 %).
- **KPI de ahorro adjudicado** en la portada: requiere materializar `ahorro_adjudicado` en
  `Expediente` al adjudicar (para no recalcular comparativos en el listado). Diseñado, no hecho.
- **Precio indexado** (OMIE/ESIOS) — Fase 3.
- **APIs de datos**: Datadis y la API de facturas de la empresa (Fase 2), con capa de adaptadores.
- **Profile factors** de 2.0TD y de Canarias/Baleares (solo están los de Península 3.0/6.xTD).
- **Decisión pendiente**: ¿aplicar el impuesto local 1,5 % al precio fijo o solo al indexado?
- **Automatizar copia diaria** y **despliegue en servidor de la empresa** (Waitress como servicio
  Windows, o PythonAnywhere) — pendientes a propuesta de la usuaria.

## 11. Convenciones

- **Todo en español** (código, comentarios, UI, commits).
- Commits en español, descriptivos. Repo git local (rama `main`); sin remoto todavía.
- No versionar: `.env`, `db.sqlite3`, `.venv`, `backups/`, `media/`, `staticfiles/` (ya en `.gitignore`).
- **No exponer datos de clientes reales** en material público (repo/slides/despliegue): la base de
  datos no se versiona, pero las capturas pueden contener nombres reales — revisar.
