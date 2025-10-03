-- ============================================
-- SCHEMA DE BASE DE DATOS - SERVIDOR STREAMS
-- ============================================

-- Extensiones necesarias
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================
-- TABLA 1: USERS
-- ============================================
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    stream_key VARCHAR(255) UNIQUE NOT NULL DEFAULT encode(gen_random_bytes(32), 'hex'),
    avatar_url VARCHAR(500),
    bio TEXT,
    is_streaming BOOLEAN DEFAULT false,
    is_verified BOOLEAN DEFAULT false,
    follower_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Índices para users
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_stream_key ON users(stream_key);
CREATE INDEX idx_users_is_streaming ON users(is_streaming);

-- ============================================
-- TABLA 2: STREAMS
-- ============================================
CREATE TABLE streams (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    thumbnail_url VARCHAR(500),
    stream_url VARCHAR(500),
    is_live BOOLEAN DEFAULT false,
    viewer_count INTEGER DEFAULT 0,
    peak_viewers INTEGER DEFAULT 0,
    total_views INTEGER DEFAULT 0,
    started_at TIMESTAMP,
    ended_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Índices para streams
CREATE INDEX idx_streams_user_id ON streams(user_id);
CREATE INDEX idx_streams_is_live ON streams(is_live);
CREATE INDEX idx_streams_started_at ON streams(started_at DESC);
CREATE INDEX idx_streams_viewer_count ON streams(viewer_count DESC);

-- ============================================
-- TABLA 3: CATEGORIES
-- ============================================
CREATE TABLE categories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) UNIQUE NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    icon_url VARCHAR(500),
    description TEXT,
    stream_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Índices para categories
CREATE INDEX idx_categories_slug ON categories(slug);
CREATE INDEX idx_categories_stream_count ON categories(stream_count DESC);

-- ============================================
-- TABLA 4: STREAM_CATEGORIES (Relación N:M)
-- ============================================
CREATE TABLE stream_categories (
    stream_id UUID NOT NULL REFERENCES streams(id) ON DELETE CASCADE,
    category_id UUID NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (stream_id, category_id)
);

-- Índices para stream_categories
CREATE INDEX idx_stream_categories_stream_id ON stream_categories(stream_id);
CREATE INDEX idx_stream_categories_category_id ON stream_categories(category_id);

-- ============================================
-- TABLA 5: FOLLOWERS (Relación N:M)
-- ============================================
CREATE TABLE followers (
    follower_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    following_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (follower_id, following_id),
    CONSTRAINT no_self_follow CHECK (follower_id != following_id)
);

-- Índices para followers
CREATE INDEX idx_followers_follower_id ON followers(follower_id);
CREATE INDEX idx_followers_following_id ON followers(following_id);
CREATE INDEX idx_followers_created_at ON followers(created_at DESC);

-- ============================================
-- TABLA 6: CHAT_MESSAGES
-- ============================================
CREATE TABLE chat_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    stream_id UUID NOT NULL REFERENCES streams(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    message TEXT NOT NULL,
    is_deleted BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Índices para chat_messages
CREATE INDEX idx_chat_messages_stream_id ON chat_messages(stream_id);
CREATE INDEX idx_chat_messages_user_id ON chat_messages(user_id);
CREATE INDEX idx_chat_messages_created_at ON chat_messages(created_at DESC);

-- ============================================
-- TABLA 7: SUBSCRIPTIONS
-- ============================================
CREATE TYPE subscription_tier AS ENUM ('basic', 'pro', 'premium');
CREATE TYPE subscription_status AS ENUM ('active', 'cancelled', 'expired');

CREATE TABLE subscriptions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    streamer_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tier subscription_tier NOT NULL DEFAULT 'basic',
    status subscription_status NOT NULL DEFAULT 'active',
    amount DECIMAL(10, 2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'USD',
    payment_method VARCHAR(50),
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    cancelled_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT no_self_subscribe CHECK (user_id != streamer_id)
);

-- Índices para subscriptions
CREATE INDEX idx_subscriptions_user_id ON subscriptions(user_id);
CREATE INDEX idx_subscriptions_streamer_id ON subscriptions(streamer_id);
CREATE INDEX idx_subscriptions_status ON subscriptions(status);
CREATE INDEX idx_subscriptions_expires_at ON subscriptions(expires_at);
CREATE INDEX idx_subscriptions_tier ON subscriptions(tier);

-- ============================================
-- TRIGGERS
-- ============================================

-- Trigger para actualizar updated_at en users
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_subscriptions_updated_at
    BEFORE UPDATE ON subscriptions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger para actualizar follower_count
CREATE OR REPLACE FUNCTION update_follower_count()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE users SET follower_count = follower_count + 1 WHERE id = NEW.following_id;
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE users SET follower_count = follower_count - 1 WHERE id = OLD.following_id;
        RETURN OLD;
    END IF;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER followers_count_trigger
    AFTER INSERT OR DELETE ON followers
    FOR EACH ROW
    EXECUTE FUNCTION update_follower_count();

-- Trigger para actualizar stream_count en categories
CREATE OR REPLACE FUNCTION update_category_stream_count()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE categories SET stream_count = stream_count + 1 WHERE id = NEW.category_id;
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE categories SET stream_count = stream_count - 1 WHERE id = OLD.category_id;
        RETURN OLD;
    END IF;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER category_stream_count_trigger
    AFTER INSERT OR DELETE ON stream_categories
    FOR EACH ROW
    EXECUTE FUNCTION update_category_stream_count();

-- ============================================
-- VISTAS ÚTILES
-- ============================================

-- Vista de streams en vivo con información del streamer
CREATE OR REPLACE VIEW live_streams_view AS
SELECT
    s.id,
    s.title,
    s.description,
    s.thumbnail_url,
    s.stream_url,
    s.viewer_count,
    s.started_at,
    u.id as user_id,
    u.username,
    u.avatar_url,
    u.is_verified,
    ARRAY_AGG(c.name) as categories
FROM streams s
JOIN users u ON s.user_id = u.id
LEFT JOIN stream_categories sc ON s.id = sc.stream_id
LEFT JOIN categories c ON sc.category_id = c.id
WHERE s.is_live = true
GROUP BY s.id, u.id;

-- Vista de subscripciones activas
CREATE OR REPLACE VIEW active_subscriptions_view AS
SELECT
    sub.id,
    sub.tier,
    sub.amount,
    sub.started_at,
    sub.expires_at,
    u.id as subscriber_id,
    u.username as subscriber_username,
    streamer.id as streamer_id,
    streamer.username as streamer_username,
    streamer.avatar_url as streamer_avatar
FROM subscriptions sub
JOIN users u ON sub.user_id = u.id
JOIN users streamer ON sub.streamer_id = streamer.id
WHERE sub.status = 'active' AND sub.expires_at > CURRENT_TIMESTAMP;

-- ============================================
-- DATOS INICIALES (SEED)
-- ============================================

-- Categorías iniciales
INSERT INTO categories (name, slug, icon_url) VALUES
('Gaming', 'gaming', 'https://example.com/icons/gaming.svg'),
('Just Chatting', 'just-chatting', 'https://example.com/icons/chat.svg'),
('Music', 'music', 'https://example.com/icons/music.svg'),
('Art', 'art', 'https://example.com/icons/art.svg'),
('Programming', 'programming', 'https://example.com/icons/code.svg'),
('Sports', 'sports', 'https://example.com/icons/sports.svg'),
('Cooking', 'cooking', 'https://example.com/icons/cooking.svg'),
('Education', 'education', 'https://example.com/icons/education.svg');

-- ============================================
-- FUNCIONES ÚTILES
-- ============================================

-- Función para obtener streams recomendados
CREATE OR REPLACE FUNCTION get_recommended_streams(p_user_id UUID, p_limit INTEGER DEFAULT 10)
RETURNS TABLE (
    stream_id UUID,
    title VARCHAR,
    viewer_count INTEGER,
    streamer_username VARCHAR,
    streamer_avatar VARCHAR
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        s.id,
        s.title,
        s.viewer_count,
        u.username,
        u.avatar_url
    FROM streams s
    JOIN users u ON s.user_id = u.id
    LEFT JOIN followers f ON u.id = f.following_id AND f.follower_id = p_user_id
    WHERE s.is_live = true
    ORDER BY
        CASE WHEN f.following_id IS NOT NULL THEN 0 ELSE 1 END,
        s.viewer_count DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- Función para verificar si un usuario está subscrito
CREATE OR REPLACE FUNCTION is_subscribed(p_user_id UUID, p_streamer_id UUID)
RETURNS BOOLEAN AS $$
DECLARE
    sub_exists BOOLEAN;
BEGIN
    SELECT EXISTS(
        SELECT 1 FROM subscriptions
        WHERE user_id = p_user_id
        AND streamer_id = p_streamer_id
        AND status = 'active'
        AND expires_at > CURRENT_TIMESTAMP
    ) INTO sub_exists;

    RETURN sub_exists;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- COMENTARIOS Y DOCUMENTACIÓN
-- ============================================

COMMENT ON TABLE users IS 'Tabla principal de usuarios/streamers';
COMMENT ON TABLE streams IS 'Tabla de streams activos e históricos';
COMMENT ON TABLE categories IS 'Categorías de contenido';
COMMENT ON TABLE stream_categories IS 'Relación muchos a muchos entre streams y categorías';
COMMENT ON TABLE followers IS 'Relación de seguidores entre usuarios';
COMMENT ON TABLE chat_messages IS 'Mensajes del chat de cada stream';
COMMENT ON TABLE subscriptions IS 'Subscripciones de usuarios a streamers';

COMMENT ON COLUMN users.stream_key IS 'Clave única para autenticación desde OBS';
COMMENT ON COLUMN streams.peak_viewers IS 'Número máximo de espectadores concurrentes';
COMMENT ON COLUMN subscriptions.tier IS 'Nivel de subscripción: basic, pro o premium';
