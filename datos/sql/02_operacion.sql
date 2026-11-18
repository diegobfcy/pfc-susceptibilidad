-- D1. Evolución del esquema para la operación del sistema (actividades 2.3 y 3.2).
-- Geometría en Web Mercator para las teselas, control de concurrencia, tiempos por fase y deriva.
ALTER TABLE ref.celda_analisis
  ADD COLUMN IF NOT EXISTS geom_3857 geometry(Polygon, 3857)
  GENERATED ALWAYS AS (ST_Transform(geom, 3857)) STORED;
CREATE INDEX IF NOT EXISTS ix_celda_geom_3857 ON ref.celda_analisis USING gist (geom_3857);
CREATE INDEX IF NOT EXISTS ix_celda_provincia ON ref.celda_analisis (ubigeo_prov);

ALTER TABLE sistema.procesamiento
  ADD COLUMN IF NOT EXISTS tiempos_s jsonb,
  ADD COLUMN IF NOT EXISTS resumen jsonb,
  -- Zona de la inferencia (RF-01): un departamento de la macrorregión; NULL = macrorregión completa.
  ADD COLUMN IF NOT EXISTS ubigeo_dep char(2) REFERENCES ref.departamento;

-- Un solo procesamiento activo a la vez (RF-04): la base de datos decide ante envíos simultáneos.
CREATE UNIQUE INDEX IF NOT EXISTS ux_procesamiento_activo ON sistema.procesamiento ((1))
  WHERE estado IN ('PENDIENTE', 'EN_CURSO', 'EN_ESPERA');

CREATE TABLE IF NOT EXISTS modelo.deriva (
  id_modelo_version  integer REFERENCES modelo.modelo_version,
  variable           varchar(30) NOT NULL,
  psi                numeric(6,4) NOT NULL CHECK (psi >= 0),
  PRIMARY KEY (id_modelo_version, variable)
);

CREATE INDEX IF NOT EXISTS ix_bitacora_tipo ON sistema.bitacora (tipo, ocurrido_en);
