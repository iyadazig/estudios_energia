# Estudios Energía GEYPE

Aplicación web (Django) para elaborar **estudios comparativos de renovación de contratos
eléctricos**: compara el coste anual estimado del contrato actual de un cliente frente a
las ofertas de varias comercializadoras, calculando la factura anual sin IVA a partir del
consumo histórico y de los parámetros regulados vigentes (peajes, cargos, pérdidas,
impuesto local, IEE, SSAA). Exporta el resultado a **Excel** y **PDF**.

## Funcionalidades principales

- **Expedientes** por cliente, con código automático (`EXP-AAAA-NNNN`) y estado **abierto /
  cerrado**. Al cerrar un expediente se indica la **oferta adjudicataria** (o «sin
  adjudicación» si se cierra sin aceptar ninguna).
- **Puntos de suministro (CUPS)**: tarifas 2.0TD–6.4TD, potencias y precios por periodo
  (P1–P6), contrato actual a precio fijo. La potencia del contrato actual puede ir «según
  ATR» (se aplican los peajes + cargos regulados) o con precios propios.
- **Consumos mensuales** por periodo (12 meses por CUPS).
- **Importación desde plantilla Excel** (hojas Cliente / Suministros / Consumos), con
  validación de CUPS (letras de control) y coherencia tarifa↔periodos. Dos vías:
  - crear un **expediente nuevo** completo desde la plantilla;
  - **añadir CUPS y consumos a un expediente existente** (añade los nuevos y omite los
    que ya estén, informando). La plantilla en blanco se descarga desde la propia app.
- **Ofertas** de comercializadoras: comercializadora, duración, GdO, validez y gestor
  comercial. Precios por **tarifa** (un bloque por cada tarifa del expediente) o, como
  opción, **distintos por cada CUPS**.
- **Servicios de ajuste (SSAA)** por oferta, con sección propia:
  - Tipo: incluidos en energía / con **techo** / con **banda** (ref. mínima y máxima) /
    **indexados** completos.
  - Modo **promedio mensual** o **horario** (reparte el SSAA por periodos con los
    *profile factors*).
  - **Pérdidas** por Circular 3/2020 o porcentaje fijo, **apuntamiento** (constante) e
    **impuesto municipal** (×1,015) opcionales. La regularización de banda puede ser un
    abono (negativo).
- **Conceptos adicionales** configurables (€/MWh sobre consumo, € fijo/mes, % sobre
  subtotal), con opción de **pérdidas** y **× impuesto local**, indicando si entran en la
  base del IEE. Se pueden añadir varios sin salir del formulario.
- **Catálogo de ofertas reutilizables**: una oferta creada en un expediente se puede
  guardar en el catálogo (★ A catálogo) con su configuración, conceptos y precios por
  tarifa. Al crear una oferta en otro expediente, se puede **cargar desde el catálogo**
  para prerrellenar el formulario (los precios se aplican a las tarifas del expediente).
  Menú **Catálogo** para listarlas, renombrarlas y borrarlas.
- **Motor de cálculo** (`estudios/calculo.py`): término de potencia, energía, conceptos
  adicionales e IEE. Comparativo **agregado del expediente y por CUPS**, con ahorro frente
  al contrato actual, ranking, €/kWh medio y orden de más barata a más cara. Usa parámetros
  regulados versionados por fecha de vigencia.
- **Comparativo en pantalla**: tabla con la oferta ganadora destacada, banner de mejor
  oferta, ahorros en color y **gráfico de barras** del coste anual.
- **Exportación** del comparativo a **Excel** (openpyxl) y **PDF** (xhtml2pdf), con el logo
  corporativo y, si es multipunto, el desglose por CUPS en página aparte.
- **Panel de parámetros** (solo personal/staff): carga masiva por plantilla Excel de
  peajes, cargos, pérdidas, **impuesto local**, IEE, la **serie SSAA mensual** (un valor
  por mes, independiente del año) y los **profile factors** (perfiles horarios por mes y
  periodo). Los retoques puntuales se hacen en el panel de administración de Django.
- **Copia de seguridad** de la base de datos con un comando (ver más abajo).
- **Autenticación**. Dos perfiles: **administrador** (staff: gestiona parámetros, usuarios
  y el panel de administración) y **usuario normal** (trabaja con expedientes y ofertas).
  Todos los usuarios ven y editan todos los expedientes (decisión para uso interno con
  pocos usuarios de confianza).

## Requisitos

- Python 3.12 o superior.
- Dependencias en `requirements.txt` (Django 6.0, openpyxl, xhtml2pdf, python-decouple…).

## Instalación

```bash
# 1. Crear y activar entorno virtual
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/Mac

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Configurar variables de entorno
copy .env.example .env          # Windows
# cp .env.example .env          # Linux/Mac
#   Edita .env y pon una SECRET_KEY real:
#   python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# 4. Migraciones y usuario administrador
python manage.py migrate
python manage.py createsuperuser

# 5. (Opcional) Cargar parámetros regulados vigentes 2026
python manage.py cargar_parametros_2026

# 6. Arrancar
python manage.py runserver 127.0.0.1:8000
#   También puedes usar ARRANCAR APP.bat (Windows)
```

Abre <http://127.0.0.1:8000> e inicia sesión.

## Comandos de gestión

```bash
# Cargar peajes, cargos, pérdidas, impuesto local e IEE vigentes 2026
python manage.py cargar_parametros_2026

# Copia de seguridad de la base de datos (en la carpeta backups/)
python manage.py copia_seguridad
#   En Windows también con doble clic en COPIA SEGURIDAD.bat
```

Las copias se guardan fechadas en `backups/` (se conservan las últimas 30). Conviene
sincronizar esa carpeta a un sitio externo (OneDrive, otro disco) para no depender del
mismo equipo.

## Variables de entorno (`.env`)

| Variable                | Descripción                                              | Por defecto |
|-------------------------|----------------------------------------------------------|-------------|
| `SECRET_KEY`            | Clave secreta de Django (obligatoria).                   | —           |
| `DEBUG`                 | `True` solo en desarrollo local.                         | `False`     |
| `ALLOWED_HOSTS`         | Hosts permitidos, separados por comas.                   | (vacío)     |
| `CSRF_TRUSTED_ORIGINS`  | Orígenes de confianza para CSRF (esquema+dominio).       | (vacío)     |

## Estructura del proyecto

```
estudios-energia-geype/
├── config/                 # Proyecto Django (settings, urls, wsgi)
│   └── settings.py         # Configuración (lee variables de entorno)
├── estudios/               # Aplicación principal
│   ├── models.py           # Expediente, PuntoSuministro, Oferta, parámetros...
│   ├── calculo.py          # Motor de cálculo del comparativo
│   ├── views.py            # Vistas (expedientes, ofertas, parámetros, importar, export)
│   ├── forms.py            # Formularios
│   ├── importador.py       # Importación de la plantilla de estudio (.xlsx)
│   ├── parametros_excel.py # Plantilla e importación de parámetros regulados
│   ├── exportar.py         # Exportación del comparativo a Excel y PDF
│   ├── admin.py            # Configuración del panel de administración
│   ├── tests.py            # Tests del motor de cálculo y validaciones
│   ├── plantillas/         # Plantilla de estudio en blanco (.xlsx) que sirve la app
│   ├── management/commands/ # cargar_parametros_2026, copia_seguridad
│   └── migrations/
├── templates/              # Plantillas HTML (base + por página)
├── static/                 # Estáticos (logo, CSS)
├── backups/                # Copias de seguridad de la BD (no se versiona)
├── requirements.txt        # Dependencias de producción
├── requirements-dev.txt    # Dependencias de desarrollo y tests
├── .env.example            # Plantilla de variables de entorno
├── .gitignore
├── manage.py
├── ARRANCAR APP.bat        # Arranque rápido en Windows
└── COPIA SEGURIDAD.bat     # Copia de seguridad de la BD en Windows
```

## Tests

```bash
pip install -r requirements-dev.txt
python manage.py test estudios     # runner de Django
# o, con pytest-django:
pytest
```

Los tests verifican al céntimo el motor de cálculo (línea base, conceptos con pérdidas y
SSAA, impuesto local, agregado por CUPS, ranking, precios por tarifa) y la validación de
CUPS.

## Notas

- Uso previsto: **entorno interno con pocos usuarios**.
- Base de datos: **SQLite** (suficiente para el volumen esperado en uso interno). Si en el
  futuro crece la concurrencia, se puede migrar a PostgreSQL sin cambiar la aplicación.
- La modalidad de oferta soportada es **precio fijo**; el **precio indexado** queda como
  fase futura.
