# Manual de usuario

**Sistema de estimación de la susceptibilidad a deslizamientos por El Niño en el norte del Perú**
Versión 1.0.0 · noviembre de 2026

Este manual explica cómo usar el sistema desde el navegador. Está organizado por rol. El sistema es
una prueba de concepto académica: **no es un sistema de alerta** y no sustituye las funciones de
CENEPRED ni de INDECI.

## Contenido

1. [Qué hace el sistema](#1-qué-hace-el-sistema)
2. [Requisitos y acceso](#2-requisitos-y-acceso)
3. [Roles y permisos](#3-roles-y-permisos)
4. [Equipo Investigador: panel de control (CU-01)](#4-equipo-investigador-panel-de-control-cu-01)
5. [Especialista: visor de mapas (CU-02 y CU-04)](#5-especialista-visor-de-mapas-cu-02-y-cu-04)
6. [Asesor e Investigador: indicadores (CU-03)](#6-asesor-e-investigador-indicadores-cu-03)
7. [Asesor e Investigador: historial de operaciones (CU-05)](#7-asesor-e-investigador-historial-de-operaciones-cu-05)
8. [Cómo leer los resultados](#8-cómo-leer-los-resultados)
9. [Mensajes del sistema y qué hacer](#9-mensajes-del-sistema-y-qué-hacer)
10. [Preguntas frecuentes](#10-preguntas-frecuentes)

## 1. Qué hace el sistema

El sistema estima, mes a mes, la susceptibilidad a deslizamientos de cada celda de 1 km × 1 km de la
macrorregión norte (Tumbes, Piura, Lambayeque, Cajamarca, La Libertad, Amazonas y la vertiente del
Pacífico de Áncash): 108 461 celdas entre 2000 y 2026. Para ello combina:

- la temperatura superficial del mar (TSM) de la región Niño 1+2 y su anomalía (NOAA ERSST v5);
- la precipitación diaria (Copernicus ERA5-Land);
- la pendiente del terreno (Copernicus DEM GLO-30);
- el inventario histórico de deslizamientos (INGEMMET y CENEPRED).

Un modelo XGBoost asigna a cada celda y mes un puntaje entre 0 y 1, que se clasifica en cuatro
niveles: **Baja** (0 a 25 %), **Media** (25 a 50 %), **Alta** (50 a 75 %) y **Muy alta** (75 a 100 %).

## 2. Requisitos y acceso

- Navegador actualizado: Google Chrome, Mozilla Firefox o Microsoft Edge. No hace falta instalar
  ningún programa ni complemento.
- Una cuenta entregada por el administrador del sistema. Las cuentas no se crean desde la web.
- La dirección del sistema que le indique el equipo (por ejemplo, `https://<servidor>/visor/` o
  `https://<servidor>/panel/`).

**Iniciar sesión (IU-01).** Escriba su correo y su clave y pulse **Entrar**. Según su rol, el sistema
lo lleva al panel o al visor (IU-02).

- Si se equivoca, verá un aviso (IU-03). Al **quinto intento fallido** la cuenta se bloquea durante
  15 minutos; el administrador puede desbloquearla antes.
- Si envía demasiados intentos seguidos, el sistema pide esperar antes de volver a intentarlo.
- Para salir, pulse **Cerrar sesión**. La sesión también termina al cerrar el navegador.

## 3. Roles y permisos

| Función | Equipo Investigador | Especialista en Gestión de Riesgos | Asesor del Proyecto |
|---|:---:|:---:|:---:|
| Iniciar, seguir y cancelar procesamientos (CU-01) | Sí | — | — |
| Cargar archivos cuando una fuente falla (CU-01, flujo 4a) | Sí | — | — |
| Ver el estado del procesamiento activo | Sí | — | Sí |
| Visor de mapas, filtros y consulta por clic (CU-02) | Sí | Sí | — |
| Capas de información del visor (CU-04) | Sí | Sí | — |
| Panel de indicadores y exportación (CU-03) | Sí | — | Sí |
| Historial de operaciones (CU-05) | Sí | — | Sí |

Si intenta abrir una pantalla que su rol no permite, el sistema lo redirige a la que le corresponde.

## 4. Equipo Investigador: panel de control (CU-01)

Abra `https://<servidor>/panel/`.

### 4.1 Iniciar un procesamiento (flujo normal)

1. En **Procesamiento**, elija el tipo:
   - **INGESTA**: descarga y verifica los datos de las fuentes oficiales para el rango de fechas.
   - **ENTRENAMIENTO**: entrena el modelo con datos ya verificados (uso del equipo técnico).
   - **INFERENCIA**: calcula la susceptibilidad con la versión aprobada del modelo.
2. Ingrese el rango de fechas (**desde** y **hasta**).
3. En **Zona**, elija un departamento o deje **Macrorregión norte completa**. La zona solo aplica a la
   inferencia: la ingesta siempre cubre toda la macrorregión.
4. Pulse **Iniciar procesamiento**. Se abre el resumen (IU-05) con el tipo, las fechas, la zona, las
   variables y el número de estimaciones que se harán.
5. Revise el resumen y pulse **Confirmar e iniciar**, o **Volver** para corregir sin crear nada.
6. El panel muestra el estado y la fase en curso (IU-06). Puede cerrar la página: al volver a
   abrirla, el panel recupera el procesamiento activo.
7. Al terminar aparece **«El procesamiento finalizó correctamente»** con el tiempo y el número de
   registros (IU-07). Los mapas ya pueden consultarse en el visor.

Solo puede haber **un procesamiento activo a la vez**. Si ya hay uno, el resumen muestra «Ya existe un
procesamiento en curso» y no se crea otro.

### 4.2 Una fuente no responde (flujo 4a, IU-08 e IU-09)

Si una fuente oficial no responde o su archivo no está disponible, el procesamiento queda **en
espera** y el panel muestra la alerta **«Fuente externa no disponible»**, con el nombre de la fuente.

1. Descargue usted el archivo desde el portal oficial de esa fuente.
2. En el formulario de la alerta, la fuente ya viene seleccionada. Elija el archivo y pulse
   **Cargar archivo y reanudar**.
3. El sistema verifica el tipo y el tamaño (hasta 2 GB; NetCDF `.nc`, GeoTIFF `.tif`, GeoPackage `.gpkg`, Parquet `.parquet`, CSV `.csv` o
   texto `.ascii`, con un contenido que corresponda a la extensión),
   registra su huella SHA-256 y reanuda la verificación. Un archivo de otro tipo se rechaza con un
   mensaje y no se guarda.

El error queda registrado en el historial de operaciones.

### 4.3 Datos que no cumplen las reglas (flujo 6a, IU-10 e IU-11)

Si los datos no cumplen alguna regla de verificación (campos completos, sin nulos, rangos de cada
fuente, pendiente entre 0° y 90°, precipitación diaria continua y TSM para cada mes), el panel muestra
**«Datos rechazados en la verificación»** con la fuente, la regla incumplida y el detalle (por
ejemplo, los días faltantes).

El procesamiento **no continúa** hasta que usted:

- reemplace el archivo con la carga manual (como en 4.2), o
- pulse **Cancelar procesamiento** y confirme con **Sí, cancelar**. Los resultados parciales no se
  guardan y la cancelación queda en el historial.

## 5. Especialista: visor de mapas (CU-02 y CU-04)

Abra `https://<servidor>/visor/`.

### 5.1 Consultar y filtrar el mapa (CU-02, IU-12)

1. En **Periodo**, elija el **mes** que desea consultar.
2. En **Departamento** y, si quiere, **Provincia**, elija la zona. El mapa se encuadra en ella y
   muestra solo sus celdas.
3. El mapa colorea cada celda según su nivel. La **leyenda** indica el nombre y el rango de cada nivel.
4. Si el mes elegido no tiene mapas procesados, aparece el mensaje **«No existen datos procesados para
   el periodo seleccionado»** (IU-15). Elija otro mes.

### 5.2 Consultar una zona con un clic (IU-14)

Haga **un clic** sobre una celda coloreada. Se abre una ventana con:

- la celda, su provincia y su departamento;
- el **nivel** y el **puntaje del modelo** (valor exacto con cuatro decimales);
- la precipitación del mes, el máximo de tres días y el acumulado de los 90 días anteriores;
- la anomalía de TSM de la región Niño 1+2;
- la pendiente media y su percentil 90.

La consulta no modifica ningún dato.

### 5.3 Capas de información (CU-04, IU-13)

En el panel **Capas** marque o desmarque:

| Capa | Qué muestra |
|---|---|
| Susceptibilidad | Nivel de cada celda en el mes elegido |
| Inventario de deslizamientos | Eventos registrados hasta el fin del mes; los del propio mes, en rojo |
| Precipitación mensual | Lluvia acumulada del mes por celda |
| Anomalía de TSM (Niño 1+2) | Anomalía del mes respecto de 1991–2020 |
| Pendiente del terreno | Pendiente media por celda |
| Límites provinciales | Contorno de las provincias |

El mapa se actualiza al instante, sin recargar la página, y la leyenda muestra solo las capas activas.
Si una capa no puede mostrarse, aparece un aviso junto a su nombre y las demás siguen visibles.

### 5.4 Paleta accesible

En **Paleta** elija **Accesible (amarillo a marrón)** si tiene dificultad para distinguir el verde del
rojo. El nivel Muy alta lleva además una trama diagonal. El navegador recuerda su elección.

## 6. Asesor e Investigador: indicadores (CU-03)

En el panel, la sección **Indicadores de rendimiento** (IU-16) muestra:

- las métricas del modelo por versión y conjunto (AUC-ROC de validación y de prueba, y las métricas
  que se registren);
- la **deriva de datos** (índice PSI) de la precipitación máxima de tres días, el acumulado de 90 días
  y la anomalía de TSM;
- el tiempo total, el tiempo por fase y la memoria del último procesamiento de cada tipo;
- la distribución de las celdas por nivel.

Cuando un indicador no alcanza su umbral aprobado, su tarjeta se resalta con el aviso **«Rendimiento
por debajo del nivel esperado»**. Por ejemplo, un PSI mayor de 0.25 indica que los datos recientes se
alejan de los de entrenamiento y que conviene revisar el modelo.

Pulse **Exportar indicadores (CSV)** para descargar los valores mostrados y adjuntarlos a un informe.

## 7. Asesor e Investigador: historial de operaciones (CU-05)

La sección **Historial de operaciones** (IU-17) lista lo que hizo el sistema: fecha y hora, tipo
(**INFORMATIVO**, **ADVERTENCIA** o **ERROR**), componente, descripción y usuario.

1. Filtre por rango de fechas y por tipo, y pulse **Filtrar**.
2. Revise cada operación. Por ejemplo, filtre por **ERROR** para ver todas las fallas registradas.
3. Si ningún registro cumple el filtro, aparece **«No existen registros para el criterio
   seleccionado»**.

El historial no puede modificarse ni borrarse.

## 8. Cómo leer los resultados

- El **puntaje** ordena las celdas de mayor a menor susceptibilidad. **No es una probabilidad
  calibrada**: un puntaje de 0.80 no significa un 80 % de probabilidad de deslizamiento.
- En la validación con datos de 2020 a 2026 que el modelo nunca vio, el AUC-ROC fue de 0.902. Además,
  en muestras con igual número de celdas con y sin deslizamiento, el 83 % de las celdas que el modelo
  marcó como susceptibles tuvieron un evento (precisión 1:1 de 0.834).
- Como los deslizamientos son raros (1 de cada 6 300 celdas-mes en ese periodo), la mayoría de las
  celdas en nivel Alto o Muy alto **no** tendrán un deslizamiento ese mes. Use los niveles para priorizar
  zonas de análisis, no como pronóstico de eventos.
- El modelo es válido para condiciones asociadas a El Niño y para la resolución de 1 km. No representa
  laderas individuales ni lluvias estacionales ordinarias fuera de ese contexto.

## 9. Mensajes del sistema y qué hacer

| Mensaje | Qué significa | Qué hacer |
|---|---|---|
| Correo o clave incorrectos | Las credenciales no coinciden | Revise mayúsculas y vuelva a intentar |
| Cuenta bloqueada | Cinco intentos fallidos | Espere 15 minutos o pida el desbloqueo al administrador |
| Demasiadas solicitudes | Límite de intentos por minuto | Espere un minuto |
| Ya existe un procesamiento en curso | Solo se permite uno a la vez | Espere a que termine o cancélelo |
| Fuente externa no disponible | Una fuente oficial no respondió | Cargue el archivo manualmente (4.2) |
| Datos rechazados en la verificación | Una regla de calidad no se cumple | Reemplace el archivo o cancele (4.3) |
| No existen datos procesados para el periodo seleccionado | El mes no tiene mapas | Elija otro mes o pida su procesamiento |
| Esta capa no está disponible; las demás siguen visibles | Falló una capa del visor | Vuelva a activarla más tarde |
| Rendimiento por debajo del nivel esperado | Un indicador superó su umbral | Informe al equipo para revisar el modelo |
| No existen registros para el criterio seleccionado | El filtro del historial no tiene resultados | Amplíe las fechas o el tipo |
| Error del servidor (IU-18) | Falla interna | Recargue la página; si persiste, avise al equipo |

## 10. Preguntas frecuentes

**¿Puedo ver varios meses a la vez?** No: el visor muestra un mes. Cambie el periodo para comparar.

**¿Por qué no veo el panel?** El Especialista solo tiene acceso al visor. Use la cuenta de su rol.

**¿Se pierde el procesamiento si cierro el navegador?** No. Corre en el servidor y el panel lo
recupera al volver.

**¿Quién crea las cuentas o cambia las claves?** El administrador, por la consola del servidor
(manual técnico, sección 6).
