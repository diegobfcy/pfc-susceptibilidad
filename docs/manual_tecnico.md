# Manual técnico

**Sistema de estimación de la susceptibilidad a deslizamientos por El Niño en el norte del Perú**
Versión 1.0.0 · noviembre de 2026 · Licencia MIT

Este manual sirve para instalar, desplegar, operar, mantener y extender el sistema. El uso desde el
navegador se describe en el [manual de usuario](manual_usuario.md).

## Contenido

1. [Arquitectura](#1-arquitectura)
2. [Estructura del repositorio](#2-estructura-del-repositorio)
3. [Requisitos](#3-requisitos)
4. [Configuración](#4-configuración)
5. [Instalación y despliegue](#5-instalación-y-despliegue)
6. [Administración de cuentas](#6-administración-de-cuentas)
7. [Carga de datos de referencia](#7-carga-de-datos-de-referencia)
8. [Pipeline de datos (ETL)](#8-pipeline-de-datos-etl)
9. [Modelo predictivo](#9-modelo-predictivo)
10. [API REST](#10-api-rest)
11. [Base de datos](#11-base-de-datos)
12. [Seguridad](#12-seguridad)
13. [Respaldo y restauración](#13-respaldo-y-restauración)
14. [Pruebas y calidad](#14-pruebas-y-calidad)
15. [Integración y despliegue continuos](#15-integración-y-despliegue-continuos)
16. [Operación y solución de problemas](#16-operación-y-solución-de-problemas)
17. [Extender el sistema](#17-extender-el-sistema)

## 1. Arquitectura

Monolito modular en cinco capas. Cada capa solo depende de las inferiores; el contrato lo verifica
`import-linter` (sección `[tool.importlinter]` de `pyproject.toml`).

| Capa | Carpeta | Componentes |
|---|---|---|
| Presentación | `presentacion/` | P1 visor de mapas (Leaflet + VectorGrid), P2 panel de control |
| Servicios | `servicios/pfc_servicios` | S1 API REST (Flask), S2 seguridad (Argon2id, RBAC, CSRF), S3 teselas MVT |
| Ingesta y ETL | `etl/pfc_etl` | E1 orquestador y cola, E2 conectores, E3 verificación, E4 transformación |
| Predictiva | `predictiva/pfc_predictiva` | M1 entrenamiento, M2 inferencia, M3 evaluación y deriva |
| Datos | `datos/` | D1 PostgreSQL 18 + PostGIS 3.7, D2 archivos y artefactos, D3 bitácora |

**Procesos en ejecución.**

| Proceso | Comando | Función |
|---|---|---|
| app | `gunicorn 'pfc_servicios:crear_app()'` | API y sesiones |
| worker (ETL) | `python -m pfc_etl.orquestador --cola` | Atiende ingestas y entrenamientos de la cola de D1 |
| worker-m2 | `python -m pfc_predictiva.inferencia.trabajador` | Atiende inferencias |
| proxy | nginx 1.30.6 | TLS, cabeceras de seguridad, archivos estáticos de `presentacion/` y proxy a la API |
| db | PostgreSQL 18.6 + PostGIS 3.7.0 | D1 |

La cola de trabajos vive en la tabla `sistema.procesamiento`: la API encola con estado `PENDIENTE` y
los workers toman los trabajos con `SELECT … FOR UPDATE SKIP LOCKED`. El índice único parcial
`ux_procesamiento_activo` (`datos/sql/02_operacion.sql`) garantiza **un solo procesamiento activo** (`PENDIENTE`, `EN_CURSO` o `EN_ESPERA`).

## 2. Estructura del repositorio

```
api/openapi.yaml           Contrato de la API (OpenAPI 3)
config/config.yaml         Parámetros ajustables (dominio, fuentes, reglas, partición, umbrales)
datos/pfc_datos            Acceso a D1, D2 y D3 (almacén Parquet, repositorios, bitácora, modelos)
datos/sql                  01_esquema.sql (esquema) y 02_operacion.sql (roles y datos de operación)
datos/respaldo             respaldar.sh y restaurar.sh
despliegue/                Dockerfile de las 4 imágenes, nginx, staging y entorno de pruebas
etl/pfc_etl                Conectores, verificación, transformación y orquestador
predictiva/pfc_predictiva  Entrenamiento, inferencia y evaluación
presentacion/              Visor y panel (HTML, CSS y JavaScript sin compilación)
servicios/pfc_servicios    API, seguridad, teselas y consola de administración
pruebas/                   unitarias, integracion, sistema (Playwright) y carga (Locust)
scripts/                   Evaluación, informes, figuras y utilidades de prueba
resultados/                Evidencias de entrenamiento y de las pruebas
docs/                      Manuales
```

## 3. Requisitos

**Servidor de despliegue (VPS).** 2 vCPU, 4 GB de RAM sin intercambio, 40 GB de disco, Docker
Engine con Compose v2, acceso HTTPS saliente a las fuentes de la lista blanca y un certificado TLS.

**Estación de entrenamiento (opcional).** GPU NVIDIA con CUDA para XGBoost (`PFC_DISPOSITIVO_XGB=cuda`)
y unos 20 GB para los datos crudos y la matriz Parquet (34.4 millones de filas).

**Desarrollo.** Python 3.11, conda o venv, PostgreSQL 18 con PostGIS 3.7 y, para las pruebas de
sistema, Playwright con Chromium, Firefox y Microsoft Edge.

```bash
conda create -n pfc python=3.11 && conda activate pfc
pip install -e ".[dev,geo]"
```

**Cuentas externas.** Una clave del Climate Data Store de Copernicus en `~/.cdsapirc` para descargar
ERA5-Land. NOAA, Copernicus DEM y GEOCATMIN no requieren clave.

## 4. Configuración

### 4.1 Variables de entorno

Copie `.env.example` a `.env`. El archivo `.env` nunca se versiona.

| Variable | Uso |
|---|---|
| `POSTGRES_PASSWORD` | Clave del superusuario de la base en la pila Docker |
| `PFC_BD_URL` | URL SQLAlchemy de D1 (`postgresql+psycopg://usuario:clave@host:puerto/pfc`) |
| `PFC_SECRETO_SESION` | Secreto de firma de las cookies de sesión (cadena aleatoria larga) |
| `PFC_D2` | Carpeta de D2: matriz Parquet, cargas manuales, artefactos del modelo |
| `PFC_DATOS_ORIGEN` | Carpeta de los datos crudos descargados (solo lectura para el worker) |
| `PFC_DISPOSITIVO_XGB` | `cuda` en la estación con GPU, `cpu` en el VPS y en CI |
| `PFC_CONFIG` | Ruta alternativa a `config/config.yaml` |
| `PFC_VERSION`, `PFC_REGISTRO` | Etiqueta y registro de las imágenes que levanta Compose |
| `PFC_CLAVE_NUEVA` | Clave para la consola de administración sin pedirla por teclado |

Genere los secretos con `openssl rand -hex 32`.

### 4.2 `config/config.yaml`

| Sección | Contenido |
|---|---|
| `periodo`, `dominio`, `celda_m` | Ventana 2000–2026, caja de la macrorregión y celda de 1 000 m |
| `hosts_permitidos` | Lista blanca de dominios de descarga (OWASP A10) |
| `verificacion.fuentes` | Columnas requeridas, rangos y frecuencia por fuente (RF-06) |
| `particion` | Entrenamiento 2000–2016, validación 2017–2019, prueba sellada 2020–2026 |
| `modelo` | AUC-ROC mínimo de 0.80, bloques espaciales de 50 km, 5 pliegues y grilla de hiperparámetros |
| `deriva` | Variables vigiladas y umbrales de PSI (0.10 vigilancia y 0.25 alerta) |

Si una fuente cambia de dominio de entrega, agréguelo a `hosts_permitidos`. El conector rechaza
cualquier dominio no listado antes de abrir la conexión.

## 5. Instalación y despliegue

### 5.1 Pila Docker (VPS)

```bash
git clone https://github.com/diegobfcy/pfc-susceptibilidad.git && cd pfc-susceptibilidad
git checkout v1.0.0
cp .env.example .env            # completar los valores
# Certificado TLS en despliegue/nginx/tls/ (pfc.crt y pfc.key)
./despliegue/construir_y_publicar.sh v1.0.0      # construye app, worker, db y proxy
PFC_VERSION=v1.0.0 docker compose up -d --wait
curl -fsk https://localhost:8443/api/salud       # {"estado":"ok"}
```

Las imágenes `app` y `worker` se endurecen con `despliegue/endurecer_imagen.sh`: retiran los paquetes
base que la aplicación no usa y que tienen CVE sin corrección, y el worker compila libexpat 2.10.0
con su huella SHA-256 y su firma GPG verificadas. El visor no está dentro de ninguna imagen: el proxy
monta `./presentacion` en modo solo lectura, de modo que un cambio en el visor se despliega con el
repositorio.

### 5.2 Despliegue con reversión (staging)

```bash
./despliegue/staging/desplegar.sh <commit>
```

El script descarga la versión, aplica el esquema, levanta los contenedores y ejecuta la prueba de humo:
`/api/salud` a través del proxy, una consulta a la cola y el worker en ejecución. Si la prueba falla,
vuelve a la versión registrada en `despliegue/staging/.version_actual`.

### 5.3 Entorno nativo con los límites del VPS (sin Docker)

`despliegue/pruebas/entorno.sh` levanta PostGIS, gunicorn, los dos workers y nginx dentro de un grupo
de control de systemd con 2 CPU y 4 GB sin intercambio, en `https://127.0.0.1:8444`.

```bash
./despliegue/pruebas/entorno.sh iniciar | detener | esquema
eval "$(./despliegue/pruebas/entorno.sh entorno)"   # exporta PFC_BD_URL, PFC_D2 y PYTHONPATH
```

## 6. Administración de cuentas

Las cuentas solo se crean por consola, nunca desde la web. Con el mismo comando se cambia la clave y se
desbloquea una cuenta existente.

```bash
python -m pfc_servicios.admin correo@dominio ESPECIALISTA --nombre "Nombre Apellido"
# Roles: INVESTIGADOR, ESPECIALISTA, ASESOR. La clave se pide sin mostrarla
# (o se toma de PFC_CLAVE_NUEVA). Use al menos 12 caracteres.
docker compose exec app python -m pfc_servicios.admin correo@dominio ASESOR   # en la pila Docker
```

La clave se guarda solo como hash Argon2id. Tras cinco intentos fallidos la cuenta se bloquea 15
minutos.

## 7. Carga de datos de referencia

```bash
python scripts/cargar_referencias.py
```

Carga en D1 la grilla de 108 461 celdas, la división política del INEI, el terreno por celda, la TSM
mensual, el inventario de deslizamientos, la versión del modelo con sus métricas y los umbrales de los
cuatro niveles (0.25, 0.50 y 0.75). Comprobaciones posteriores:

```sql
SELECT count(*) FROM ref.celda_analisis;                         -- 108461
SELECT count(*) FROM ref.departamento;                           -- 7
SELECT limites FROM sistema.umbral_version WHERE vigente;        -- {0.25,0.5,0.75}
```

## 8. Pipeline de datos (ETL)

| Paso | Componente | Detalle |
|---|---|---|
| Obtener | E2 conectores | NOAA ERSST v5 (Niño 1+2), Copernicus ERA5-Land (precipitación diaria, CDS API), Copernicus DEM GLO-30 (teselas COG en S3) e inventario GEOCATMIN (descarga por bloques de 1 000 OBJECTID, TLS con el intermedio Sectigo fijado) |
| Verificar | E3 | Campos requeridos, nulos, rangos por fuente, pendiente en [0°, 90°], continuidad diaria y TSM mensual |
| Transformar | E4 | Grilla UTM 17S de 1 km, pendiente media, p90 y máxima por celda, anomalía de TSM con rezagos de 1 a 3 meses y media móvil, precipitación mensual, máximo de 3 días y antecedente de 90 días |
| Guardar | D2 | Matriz Parquet particionada por año (`anio=AAAA/parte.parquet`) con huella SHA-256 en `catalogo.json` |

Cada archivo descargado queda registrado con su huella SHA-256 y un evento en la bitácora. Si una
fuente falla, el procesamiento pasa a `EN_ESPERA` con el motivo `FUENTE_NO_DISPONIBLE`; si un dato
incumple una regla, con `DATOS_RECHAZADOS`. Se reanuda con una carga manual
(`POST /ingestas/{id}/archivos`) o se cancela.

Ejecución directa, sin la cola: `python -m pfc_etl.orquestador --desde 2000 --hasta 2026 --tipo INGESTA`.

## 9. Modelo predictivo

### 9.1 Variables

`tsm_c`, `anom_tsm`, `anom_tsm_l1` a `anom_tsm_l3`, `anom_tsm_mm3`, `precip_mes_mm`,
`precip_max3d_mm`, `precip_ant90_mm`, `pend_media_g`, `pend_p90_g`, `pend_max_g` y `mes`. El objetivo
vale 1 si la celda tiene un evento del inventario con fecha de día o de mes en ese mes.

### 9.2 Entrenamiento (M1)

```bash
PFC_DISPOSITIVO_XGB=cuda python -m pfc_predictiva
```

Búsqueda de 12 combinaciones con validación cruzada espacial (bloques de 50 km, 5 pliegues, parada
temprana) y modelo final con `scale_pos_weight` igual al cociente entre negativos y positivos. La
partición de prueba 2020–2026 no se lee. El artefacto se guarda en `D2/modelos/xgboost_<versión>.ubj`
con su tarjeta JSON (huella SHA-256, hiperparámetros, métricas, importancias y referencias de PSI).
Una versión con AUC-ROC de validación menor de 0.80 se registra como `RECHAZADA`.

Versión 1 en uso: SHA-256 `0c5321b414748f0f7ad07f18078d654c98c4aab61356930ed18c73bfad786a56`.

### 9.3 Inferencia (M2)

`POST /inferencias` encola el trabajo. El worker verifica la huella del artefacto antes de cargarlo
(si no coincide, responde 422 y no escribe nada), predice por lotes anuales, clasifica en cuatro
niveles y reemplaza con `COPY` solo los meses y la zona de la ventana pedida. La inferencia completa de
317 meses tarda unos 2 minutos en la estación con los límites del VPS.

### 9.4 Evaluación (M3)

| Script | Resultado |
|---|---|
| `scripts/cp14_evaluacion_sellada.py` | AUC-ROC único sobre la partición sellada; se niega a ejecutarse dos veces |
| `scripts/precision_balanceada.py` | Precisión, sensibilidad, F1 y exactitud en 1 000 muestras caso-control 1:1 por año (umbral 0.5) y precisión operativa; ejecución única |

Resultados de la versión 1 en 2020–2026: AUC-ROC de 0.902 (IC 95 %: 0.891 a 0.913) y precisión 1:1 de
0.834 (IC 95 %: 0.816 a 0.852). La precisión sobre todas las celdas-mes es de 0.001 por la baja
prevalencia: el puntaje ordena las celdas, pero no está calibrado como probabilidad.

**Deriva.** M3 calcula el PSI de las variables vigiladas frente a los deciles de entrenamiento. Por
encima de 0.25 el panel lo marca en alerta; antes de una nueva inferencia debe revisarse el AUC-ROC
en la ventana etiquetada más reciente.

**Recomendaciones para una versión 2:** incluir los positivos de 2017–2019, calibrar las probabilidades,
agregar variables espaciales (litología, cobertura, distancia a ríos y fallas, curvatura y elevación),
optimizar también la precisión promedio y definir una unidad de alerta, como provincia-mes.

## 10. API REST

Base `/api`. El contrato completo está en `api/openapi.yaml`. Todas las rutas, salvo `/salud`,
`/auth/login` y `/sesion/csrf`, requieren sesión. Las solicitudes que cambian estado requieren la
cabecera `X-CSRFToken`.

| Método y ruta | Roles | Función |
|---|---|---|
| `POST /auth/login`, `GET` y `DELETE /sesion`, `GET /sesion/csrf` | Todos | Sesión y token CSRF |
| `POST /ingestas`, `POST /entrenamientos`, `POST /inferencias` | INV | Encolar un procesamiento (409 si ya hay uno activo) |
| `GET /ingestas/{id}`, `GET /inferencias/{id}` | INV, ASE | Estado, fase, tiempos y memoria |
| `GET /procesamientos/activo` | INV, ASE | Procesamiento activo y su motivo de espera (204 si no hay) |
| `POST /ingestas/{id}/archivos` | INV | Carga manual (hasta 2 GB; extensión y contenido verificados) |
| `POST /procesamientos/{id}/cancelar` | INV | Cancelación |
| `GET /mapas/{capa}/{periodo}/{z}/{x}/{y}.pbf` | INV, ESP | Teselas MVT: `susceptibilidad`, `precipitacion`, `tsm`, `pendiente`, `inventario`; filtros `departamento` y `provincia` |
| `GET /consulta-punto?periodo&lat&lon` | INV, ESP | Nivel, puntaje y variables de la celda |
| `GET /periodos`, `GET /ambitos`, `GET /capas/limites` | INV, ESP | Catálogos del visor |
| `GET /indicadores` | INV, ASE | Métricas, deriva, tiempos, memoria y distribución |
| `GET /bitacora?desde&hasta&tipo` | INV, ASE | Historial filtrado |
| `GET /salud` | Público | Prueba de humo |

INV: Equipo Investigador; ESP: Especialista; ASE: Asesor. Un rol no autorizado recibe 403 antes de
cualquier validación, y una solicitud sin sesión, 401.

## 11. Base de datos

Esquemas de D1 (`datos/sql/01_esquema.sql`):

| Esquema | Tablas principales |
|---|---|
| `sistema` | `rol`, `usuario`, `fuente_dato`, `dataset`, `umbral_version`, `procesamiento` (cola), `registro_rechazado`, `bitacora` (solo inserción) |
| `ref` | `departamento`, `provincia`, `celda_analisis` (geometrías UTM 17S y 3857) |
| `datos` | `tsm_mensual`, `precipitacion_diaria`, `terreno_celda`, `deslizamiento` |
| `modelo` | `modelo_version` (con las referencias de PSI), `variable`, `modelo_variable`, `metrica` |
| `resultado` | `susceptibilidad`, particionada por año (108 461 filas por mes) |

La tabla `sistema.bitacora` tiene el disparador `tr_bitacora_inmutable`, que rechaza `UPDATE` y
`DELETE`. Las teselas se generan con `ST_AsMVT` sobre índices GiST de `geom_3857`.

## 12. Seguridad

- Contraseñas con Argon2id, bloqueo a los 5 intentos y límite de solicitudes en `/auth/login` (429).
- Cookies `HttpOnly`, `Secure` y `SameSite=Strict`; CSRF en toda solicitud que cambia estado.
- RBAC en cada endpoint, según la tabla de la sección 10.
- Lista blanca de dominios y solo HTTPS en las descargas; sin redirecciones a dominios no listados.
- Cargas manuales con extensión permitida, firma de contenido verificada y tope de 2 GB.
- Cabeceras CSP, HSTS, X-Frame-Options, X-Content-Type-Options y Referrer-Policy en nginx.
- Huella SHA-256 del artefacto del modelo verificada antes de cada inferencia.
- Escaneos: Bandit, pip-audit, OWASP ZAP y Trivy. Con las imágenes endurecidas, 0 críticas y 0 altas.

## 13. Respaldo y restauración

```bash
export PFC_BD_URL_PG=postgresql://postgres:<clave>@localhost:5432/pfc
export PFC_CLAVE_RESPALDO=/ruta/segura/clave_respaldo   # archivo con la frase de cifrado
./datos/respaldo/respaldar.sh       # pg_dump custom + GPG AES-256 + .sha256; conserva 7 copias
./datos/respaldo/restaurar.sh       # verifica la huella y restaura el último respaldo
```

Política: RPO de 24 h (respaldo diario con cron) y RTO de 4 h; regla 3-2-1. Respalde también el
volumen D2 (artefactos del modelo y matriz Parquet).

## 14. Pruebas y calidad

| Nivel | Comando | Requisitos |
|---|---|---|
| Unitarias | `pytest pruebas/unitarias` | Ninguno |
| Integración | `pytest pruebas/integracion` | `PFC_BD_URL` hacia una base **exclusiva** de pruebas (por ejemplo `pfc_it`), `PFC_DATOS_ORIGEN` y, para las descargas reales, `PFC_FUENTES_EN_LINEA=1` |
| Sistema | `PFC_SISTEMA=1 PYTHONPATH=pruebas/sistema:$PYTHONPATH pytest pruebas/sistema` | Entorno en `https://127.0.0.1:8444`, `PFC_BD_URL_SISTEMA` y Playwright (entorno `pfc-pruebas`) |
| Carga | `scripts/correr_escalonada.sh solo` | Locust |
| Pipeline local | `python scripts/pipeline_local.py` | black, ruff, import-linter, OpenAPI, docstrings, pip-audit y pytest con cobertura |
| Informe por caso | `python scripts/informe_casos.py resultados/pruebas/<regresión>` | Resultados JUnit de la regresión |

Las pruebas de integración vacían tablas de resultados. Por eso se detienen solas si `PFC_BD_URL`
apunta a la base `pfc`.

Criterios vigentes: cobertura ≥ 80 % de líneas y ramas (84.0 % y 81.3 % en la quinta regresión),
puerta de calidad PFC de SonarQube y 38 de 38 casos de prueba aprobados.

## 15. Integración y despliegue continuos

`.github/workflows/ci-cd.yml` ejecuta en cada push la calidad estática, las pruebas con PostGIS como
servicio, el análisis de SonarQube y, en `main`, la construcción de las imágenes y el despliegue a
staging. Configure estos secretos del repositorio:

| Secreto | Uso |
|---|---|
| `PG_PRUEBAS` | Clave del PostGIS de las pruebas de CI |
| `SONAR_TOKEN`, `SONAR_HOST_URL` | Servidor de SonarQube |

El despliegue requiere un entorno `staging` con acceso al registro de imágenes y al servidor.

## 16. Operación y solución de problemas

| Síntoma | Causa probable | Acción |
|---|---|---|
| `/api/salud` no responde | app o proxy detenidos | `docker compose ps` y `docker compose logs app proxy` |
| Procesamiento en `EN_ESPERA` | Fuente caída o dato rechazado | Ver `resumen.motivo` en `GET /procesamientos/activo`; carga manual o cancelación |
| `HostNoPermitidoError` | La fuente entrega desde otro dominio | Agregar el dominio a `hosts_permitidos` tras verificar que es oficial |
| `SSLError` en GEOCATMIN | Cadena TLS incompleta del servidor | Revisar el intermedio fijado en el conector del inventario |
| 422 en `POST /inferencias` | La huella del artefacto no coincide | Restaurar el artefacto de D2 desde un respaldo |
| Worker reiniciándose | La base no está disponible | Levantar `db` y comprobar `PFC_BD_URL` |
| Mapa vacío | Mes sin inferencia | `GET /periodos`; ejecutar la inferencia de ese mes |
| Alerta de PSI | Deriva de datos | Evaluar el AUC-ROC reciente y decidir si reentrenar |

Registros: `docker compose logs <servicio>` y la bitácora (`GET /bitacora` o `sistema.bitacora`).

## 17. Extender el sistema

- **Nueva fuente:** implemente un conector en `etl/pfc_etl/conectores` con el contrato común de
  descarga (huella y evento de bitácora), agregue su dominio a `hosts_permitidos` y sus reglas en
  `verificacion.fuentes`.
- **Nueva variable:** calcúlela en E4, agréguela a `VARIABLES` de `pfc_predictiva/__main__.py`,
  reentrene y registre una nueva versión del modelo.
- **Nueva capa del visor:** agregue la consulta MVT en `servicios/pfc_servicios/teselas`, su rampa de
  colores y su casilla en `presentacion/visor`.
- Mantenga el contrato de capas (`lint-imports`), los docstrings públicos (`scripts/medir_docstrings.py`)
  y la cobertura ≥ 80 %.
