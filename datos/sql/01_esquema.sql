-- D1. Esquema de la base de datos espacial (PostgreSQL 15 + PostGIS 3.3), sección 2.5.
-- Cinco esquemas por dominio: sistema, ref, datos, modelo y resultado.
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE SCHEMA IF NOT EXISTS sistema;
CREATE SCHEMA IF NOT EXISTS ref;
CREATE SCHEMA IF NOT EXISTS datos;
CREATE SCHEMA IF NOT EXISTS modelo;
CREATE SCHEMA IF NOT EXISTS resultado;

-- sistema: seguridad, fuentes, procesamientos y bitácora --------------------------------
CREATE TABLE IF NOT EXISTS sistema.rol (
  id_rol       smallint PRIMARY KEY,
  codigo       varchar(20) NOT NULL UNIQUE,
  descripcion  varchar(200) NOT NULL
);
INSERT INTO sistema.rol VALUES
  (1, 'INVESTIGADOR', 'Configura e inicia procesamientos; carga manual de archivos'),
  (2, 'ESPECIALISTA', 'Consulta mapas, indicadores e historial'),
  (3, 'ASESOR', 'Consulta indicadores e historial')
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS sistema.usuario (
  id_usuario         integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  id_rol             smallint NOT NULL REFERENCES sistema.rol,
  nombre             varchar(100) NOT NULL,
  correo             varchar(150) NOT NULL UNIQUE,
  hash_clave         varchar(255) NOT NULL,
  activo             boolean NOT NULL DEFAULT true,
  intentos_fallidos  smallint NOT NULL DEFAULT 0 CHECK (intentos_fallidos >= 0),
  bloqueado_hasta    timestamptz,
  creado_en          timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS sistema.fuente_dato (
  id_fuente   smallint PRIMARY KEY,
  codigo      varchar(20) NOT NULL UNIQUE,
  nombre      varchar(100) NOT NULL,
  host        varchar(100)
);
INSERT INTO sistema.fuente_dato VALUES
  (1, 'ERSST_V5', 'NOAA ERSST v5 (índices Niño)', 'www.cpc.ncep.noaa.gov'),
  (2, 'ERA5_LAND', 'Copernicus ERA5-Land', 'cds.climate.copernicus.eu'),
  (3, 'DEM_GLO30', 'Copernicus DEM GLO-30', 'copernicus-dem-30m.s3.amazonaws.com'),
  (4, 'INVENTARIO', 'Inventario de movimientos en masa (INGEMMET/INDECI)', 'geocatmin.ingemmet.gob.pe')
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS sistema.dataset (
  id_dataset        integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  id_fuente         smallint NOT NULL REFERENCES sistema.fuente_dato,
  version_producto  varchar(50) NOT NULL,
  origen            varchar(10) NOT NULL CHECK (origen IN ('AUTOMATICO', 'MANUAL')),
  ruta_archivo      varchar(300) NOT NULL,
  sha256            char(64) NOT NULL,
  fecha_descarga    timestamptz NOT NULL DEFAULT now(),
  periodo_inicio    date,
  periodo_fin       date CHECK (periodo_fin IS NULL OR periodo_inicio IS NULL OR periodo_fin >= periodo_inicio),
  rango_min         numeric(10,3),
  rango_max         numeric(10,3) CHECK (rango_max IS NULL OR rango_min IS NULL OR rango_max >= rango_min),
  id_usuario        integer REFERENCES sistema.usuario
);

CREATE TABLE IF NOT EXISTS sistema.umbral_version (
  id_umbral_version  integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  limites            numeric(5,4)[] NOT NULL,   -- cortes Baja|Media|Alta|Muy alta
  vigente            boolean NOT NULL DEFAULT false,
  creado_en          timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS sistema.procesamiento (       -- también es la cola de trabajos de E1
  id_procesamiento   integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  id_usuario         integer NOT NULL REFERENCES sistema.usuario,
  id_umbral_version  integer REFERENCES sistema.umbral_version,
  id_modelo_version  integer,
  tipo               varchar(15) NOT NULL CHECK (tipo IN ('INGESTA', 'ENTRENAMIENTO', 'INFERENCIA')),
  fecha_desde        date NOT NULL,
  fecha_hasta        date NOT NULL CHECK (fecha_hasta >= fecha_desde),
  zona               geometry(MultiPolygon, 4326) NOT NULL,
  estado             varchar(15) NOT NULL DEFAULT 'PENDIENTE'
                     CHECK (estado IN ('PENDIENTE', 'EN_CURSO', 'EN_ESPERA', 'COMPLETADO', 'CANCELADO', 'FALLIDO')),
  fase               varchar(20),
  iniciado_en        timestamptz,
  finalizado_en      timestamptz CHECK (finalizado_en IS NULL OR iniciado_en IS NULL OR finalizado_en >= iniciado_en),
  memoria_max_gb     numeric(6,2) CHECK (memoria_max_gb >= 0)
);

CREATE TABLE IF NOT EXISTS sistema.registro_rechazado (
  id_rechazo        bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  id_dataset        integer NOT NULL REFERENCES sistema.dataset,
  regla             varchar(30) NOT NULL,
  registro          jsonb NOT NULL,
  detectado_en      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS sistema.bitacora (            -- D3: solo inserción
  id_evento         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  ocurrido_en       timestamptz NOT NULL DEFAULT now(),
  tipo              varchar(12) NOT NULL CHECK (tipo IN ('INFORMATIVO', 'ADVERTENCIA', 'ERROR')),
  componente        varchar(30) NOT NULL,
  descripcion       text NOT NULL,
  id_usuario        integer REFERENCES sistema.usuario,
  id_procesamiento  integer REFERENCES sistema.procesamiento,
  detalle           jsonb
);
CREATE OR REPLACE FUNCTION sistema.bitacora_inmutable() RETURNS trigger AS $$
BEGIN RAISE EXCEPTION 'la bitácora es de solo inserción'; END $$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS tr_bitacora_inmutable ON sistema.bitacora;
CREATE TRIGGER tr_bitacora_inmutable BEFORE UPDATE OR DELETE ON sistema.bitacora
  FOR EACH ROW EXECUTE FUNCTION sistema.bitacora_inmutable();

-- ref: división política y grilla de análisis ---------------------------------------------
CREATE TABLE IF NOT EXISTS ref.departamento (
  ubigeo_dep  char(2) PRIMARY KEY,
  nombre      varchar(50) NOT NULL UNIQUE,
  geom        geometry(MultiPolygon, 4326) NOT NULL
);
CREATE TABLE IF NOT EXISTS ref.provincia (
  ubigeo_prov  char(4) PRIMARY KEY,
  ubigeo_dep   char(2) NOT NULL REFERENCES ref.departamento,
  nombre       varchar(60) NOT NULL,
  geom         geometry(MultiPolygon, 4326) NOT NULL,
  UNIQUE (ubigeo_dep, nombre)
);
CREATE TABLE IF NOT EXISTS ref.celda_analisis (
  id_celda     integer PRIMARY KEY,
  ubigeo_prov  char(4),
  id_pixel     integer NOT NULL,          -- celda climática ERA5-Land (0.1°) que la cubre
  geom         geometry(Polygon, 32717) NOT NULL
);

-- datos: series verificadas -----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS datos.tsm_mensual (
  periodo     date PRIMARY KEY CHECK (extract(day FROM periodo) = 1),
  tsm_c       numeric(5,2) NOT NULL CHECK (tsm_c BETWEEN -2 AND 40),
  anom_tsm    numeric(5,2) NOT NULL,
  id_dataset  integer REFERENCES sistema.dataset
);
CREATE TABLE IF NOT EXISTS datos.precipitacion_diaria (
  id_pixel    integer NOT NULL,
  fecha       date NOT NULL,
  precip_mm   real NOT NULL CHECK (precip_mm BETWEEN 0 AND 500),
  PRIMARY KEY (id_pixel, fecha)
);
CREATE TABLE IF NOT EXISTS datos.terreno_celda (
  id_celda    integer PRIMARY KEY REFERENCES ref.celda_analisis,
  pend_media_g real NOT NULL CHECK (pend_media_g BETWEEN 0 AND 90),
  pend_p90_g   real NOT NULL CHECK (pend_p90_g BETWEEN 0 AND 90),
  pend_max_g   real NOT NULL CHECK (pend_max_g BETWEEN 0 AND 90)
);
CREATE TABLE IF NOT EXISTS datos.deslizamiento (
  id_deslizamiento  integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  id_dataset        integer NOT NULL REFERENCES sistema.dataset,
  codigo_origen     varchar(50) NOT NULL,
  fecha_evento      date,
  precision_fecha   varchar(5) NOT NULL CHECK (precision_fecha IN ('DIA', 'MES', 'ANIO', 'NULA')),
  id_celda          integer REFERENCES ref.celda_analisis,
  geom              geometry(Point, 4326) NOT NULL,
  UNIQUE (id_dataset, codigo_origen),
  CHECK ((precision_fecha = 'NULA') = (fecha_evento IS NULL))
);

-- modelo: versiones, variables y métricas -----------------------------------------------
CREATE TABLE IF NOT EXISTS modelo.modelo_version (
  id_modelo_version  integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  algoritmo          varchar(20) NOT NULL CHECK (algoritmo IN ('XGBOOST', 'RANDOM_FOREST')),
  version            varchar(20) NOT NULL,
  estado             varchar(10) NOT NULL CHECK (estado IN ('CANDIDATA', 'APROBADA', 'RECHAZADA', 'REVISION')),
  ruta_artefacto     varchar(300) NOT NULL,
  sha256             char(64) NOT NULL,
  hiperparametros    jsonb NOT NULL,
  referencia_psi     jsonb,
  entrenado_en       timestamptz NOT NULL DEFAULT now(),
  UNIQUE (algoritmo, version)
);
CREATE TABLE IF NOT EXISTS modelo.variable (
  id_variable  smallint PRIMARY KEY,
  codigo       varchar(30) NOT NULL UNIQUE,
  descripcion  varchar(200) NOT NULL,
  unidad       varchar(10) NOT NULL,
  grupo        varchar(15) NOT NULL CHECK (grupo IN ('OCEANICA', 'PRECIPITACION', 'TERRENO', 'CALENDARIO')),
  id_fuente    smallint REFERENCES sistema.fuente_dato
);
CREATE TABLE IF NOT EXISTS modelo.modelo_variable (
  id_modelo_version  integer REFERENCES modelo.modelo_version,
  id_variable        smallint REFERENCES modelo.variable,
  orden              smallint NOT NULL,
  importancia_gain   numeric(8,6),
  PRIMARY KEY (id_modelo_version, id_variable)
);
CREATE TABLE IF NOT EXISTS modelo.metrica (
  id_modelo_version  integer REFERENCES modelo.modelo_version,
  conjunto           varchar(12) CHECK (conjunto IN ('VALIDACION', 'PRUEBA')),
  nombre             varchar(12) CHECK (nombre IN ('AUC_ROC', 'ACCURACY', 'RECALL', 'PRECISION', 'F1')),
  valor              numeric(6,5) NOT NULL CHECK (valor BETWEEN 0 AND 1),
  PRIMARY KEY (id_modelo_version, conjunto, nombre)
);

-- resultado: susceptibilidad por celda y mes, particionada por año ---------------------------
CREATE TABLE IF NOT EXISTS resultado.susceptibilidad (
  id_procesamiento  integer NOT NULL,
  id_celda          integer NOT NULL,
  periodo           date NOT NULL CHECK (extract(day FROM periodo) = 1),
  probabilidad      numeric(5,4) NOT NULL CHECK (probabilidad BETWEEN 0 AND 1),
  nivel             smallint NOT NULL CHECK (nivel BETWEEN 1 AND 4),
  precip_mes_mm     numeric(7,1) NOT NULL CHECK (precip_mes_mm >= 0),
  precip_max3d_mm   numeric(7,1) NOT NULL CHECK (precip_max3d_mm >= 0),
  precip_ant90_mm   numeric(8,1) NOT NULL CHECK (precip_ant90_mm >= 0),
  PRIMARY KEY (id_procesamiento, id_celda, periodo)
) PARTITION BY RANGE (periodo);
DO $$ BEGIN
  FOR a IN 2000..2026 LOOP
    EXECUTE format('CREATE TABLE IF NOT EXISTS resultado.susceptibilidad_%s PARTITION OF '
                   'resultado.susceptibilidad FOR VALUES FROM (%L) TO (%L)',
                   a, make_date(a, 1, 1), make_date(a + 1, 1, 1));
  END LOOP;
END $$;

-- índices ---------------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS ix_celda_geom ON ref.celda_analisis USING gist (geom);
CREATE INDEX IF NOT EXISTS ix_deslizamiento_geom ON datos.deslizamiento USING gist (geom);
CREATE INDEX IF NOT EXISTS ix_procesamiento_cola ON sistema.procesamiento (estado, id_procesamiento)
  WHERE estado = 'PENDIENTE';
CREATE INDEX IF NOT EXISTS ix_bitacora_fecha ON sistema.bitacora (ocurrido_en);
