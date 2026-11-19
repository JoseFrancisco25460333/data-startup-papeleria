-- Esquema de PostgreSQL (RDS o contenedor en la VM). Correr una vez:
--   psql "host=... dbname=papeleria user=... sslmode=require" -f infra/aws/schema.sql
CREATE TABLE IF NOT EXISTS lotes (
    batch_id       TEXT PRIMARY KEY,
    procesado      TIMESTAMPTZ NOT NULL DEFAULT now(),
    filas_entrada  INTEGER NOT NULL,
    filas_salida   INTEGER NOT NULL,
    correcciones   INTEGER NOT NULL,
    estado         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ventas (
    id              BIGSERIAL PRIMARY KEY,
    batch_id        TEXT NOT NULL REFERENCES lotes (batch_id) DEFERRABLE INITIALLY DEFERRED,
    ticket_id       INTEGER NOT NULL,
    fecha           DATE NOT NULL,
    hora            SMALLINT NOT NULL CHECK (hora BETWEEN 0 AND 23),
    canal           TEXT NOT NULL CHECK (canal IN ('mostrador', 'domicilio', 'web')),
    producto        TEXT NOT NULL,
    cantidad        INTEGER NOT NULL CHECK (cantidad > 0),
    precio_unitario NUMERIC(10, 2) NOT NULL CHECK (precio_unitario > 0),
    total           NUMERIC(12, 2) NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_ventas_fecha ON ventas (fecha);
CREATE INDEX IF NOT EXISTS ix_ventas_producto_fecha ON ventas (producto, fecha);
CREATE INDEX IF NOT EXISTS ix_ventas_batch ON ventas (batch_id);
