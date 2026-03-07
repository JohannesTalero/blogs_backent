-- Migración: borrar blocks existentes, crear posts, recrear blocks con post_id
-- Ejecutar en Supabase SQL Editor

-- 1. Borrar bloques existentes (empezar en 0)
DROP TABLE IF EXISTS blocks;

-- 2. Crear tabla posts
CREATE TABLE IF NOT EXISTS posts (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  TEXT        NOT NULL,
    slug        TEXT        NOT NULL,
    title       TEXT        NOT NULL,
    "order"     INT         NOT NULL DEFAULT 0,
    visible     BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (project_id, slug)
);

-- 3. Recrear blocks con post_id obligatorio
CREATE TABLE blocks (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id      UUID        NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    type         TEXT        NOT NULL,
    content_json JSONB       NOT NULL,
    "order"      INT         NOT NULL DEFAULT 0,
    visible      BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 4. Crear bucket de imágenes en Storage (ejecutar solo si no existe)
-- Hacerlo desde el panel de Supabase > Storage > New bucket
-- Nombre: "images", Public: true
