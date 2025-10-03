-- ============================================
-- ALTERACIONES A TU BASE DE DATOS EXISTENTE
-- Solo agregar lo mínimo para streaming
-- ============================================

-- Activar extensión necesaria para generar claves aleatorias
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 1. Agregar stream_key a la tabla users (para OBS)
ALTER TABLE users
ADD COLUMN IF NOT EXISTS stream_key VARCHAR(255) UNIQUE;

-- Generar stream_key automático para admins existentes
UPDATE users
SET stream_key = encode(gen_random_bytes(32), 'hex')
WHERE es_admin = true AND stream_key IS NULL;

-- 2. Agregar campos de estadísticas a eventos_transmision
ALTER TABLE eventos_transmision
ADD COLUMN IF NOT EXISTS viewer_count_max INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS total_views INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS hls_url TEXT; -- URL del stream en vivo desde Contabo

-- 3. Crear índices para performance
CREATE INDEX IF NOT EXISTS idx_users_stream_key ON users(stream_key);
CREATE INDEX IF NOT EXISTS idx_eventos_estado ON eventos_transmision(estado);

-- ============================================
-- LISTO! Con esto ya puedes:
-- ============================================
-- ✅ OBS se conecta con: rtmp://tu-servidor/live/{stream_key}
-- ✅ Backend valida el stream_key de la tabla users
-- ✅ eventos_transmision guarda la url_transmision (kick, o tu servidor)
-- ✅ hls_url guarda la URL de tu servidor Contabo cuando transmitas
