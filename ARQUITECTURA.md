# Arquitectura Backend - Servidor de Streams

## 📋 Modelo de Datos

### Tablas Principales

#### 1. **users**
```sql
- id (UUID, PK)
- username (VARCHAR, UNIQUE)
- email (VARCHAR, UNIQUE)
- password_hash (VARCHAR)
- stream_key (VARCHAR, UNIQUE) -- Para autenticación OBS
- is_streaming (BOOLEAN, DEFAULT false)
- created_at (TIMESTAMP)
- updated_at (TIMESTAMP)
```

#### 2. **streams**
```sql
- id (UUID, PK)
- user_id (UUID, FK -> users)
- title (VARCHAR)
- description (TEXT)
- thumbnail_url (VARCHAR)
- stream_url (VARCHAR) -- URL del HLS/RTMP
- is_live (BOOLEAN, DEFAULT false)
- viewer_count (INTEGER, DEFAULT 0)
- started_at (TIMESTAMP)
- ended_at (TIMESTAMP)
- created_at (TIMESTAMP)
```

#### 3. **categories**
```sql
- id (UUID, PK)
- name (VARCHAR, UNIQUE)
- slug (VARCHAR, UNIQUE)
- icon_url (VARCHAR)
- created_at (TIMESTAMP)
```

#### 4. **stream_categories**
```sql
- stream_id (UUID, FK -> streams)
- category_id (UUID, FK -> categories)
- PRIMARY KEY (stream_id, category_id)
```

#### 5. **followers**
```sql
- follower_id (UUID, FK -> users)
- following_id (UUID, FK -> users)
- created_at (TIMESTAMP)
- PRIMARY KEY (follower_id, following_id)
```

#### 6. **chat_messages**
```sql
- id (UUID, PK)
- stream_id (UUID, FK -> streams)
- user_id (UUID, FK -> users)
- message (TEXT)
- created_at (TIMESTAMP)
```

#### 7. **subscriptions**
```sql
- id (UUID, PK)
- user_id (UUID, FK -> users) -- Subscriptor
- streamer_id (UUID, FK -> users) -- Streamer
- tier (ENUM: 'basic', 'pro', 'premium')
- status (ENUM: 'active', 'cancelled', 'expired')
- started_at (TIMESTAMP)
- expires_at (TIMESTAMP)
- created_at (TIMESTAMP)
```

---

## 🔐 Sistema de Autenticación OBS

### Stream Key
Cada usuario tiene un `stream_key` único que se utiliza para:
- Autenticar la conexión desde OBS
- Identificar el streamer
- Validar permisos de transmisión

### Flujo de Conexión OBS
```
OBS → RTMP Server (rtmp://servidor/live/{stream_key})
         ↓
    Validar stream_key en DB
         ↓
    Crear sesión de stream
         ↓
    Transcodificar a HLS
         ↓
    Disponible para viewers
```

---

## 🔌 APIs y Servicios

### 1. **API REST** (Express.js/Fastify)

#### Endpoints de Autenticación
- `POST /api/auth/register` - Registro de usuario
- `POST /api/auth/login` - Login (JWT)
- `POST /api/auth/refresh` - Refresh token
- `GET /api/auth/stream-key` - Obtener stream key

#### Endpoints de Streams
- `GET /api/streams` - Lista de streams en vivo
- `GET /api/streams/:id` - Detalles de un stream
- `POST /api/streams` - Crear stream (metadata)
- `PATCH /api/streams/:id` - Actualizar stream
- `DELETE /api/streams/:id` - Finalizar stream

#### Endpoints de Usuarios
- `GET /api/users/:id` - Perfil de usuario
- `GET /api/users/:id/streams` - Streams del usuario
- `POST /api/users/:id/follow` - Seguir usuario
- `DELETE /api/users/:id/follow` - Dejar de seguir

#### Endpoints de Subscripciones
- `POST /api/subscriptions` - Crear subscripción
- `GET /api/subscriptions/:userId` - Subscripciones del usuario
- `DELETE /api/subscriptions/:id` - Cancelar subscripción
- `GET /api/subscriptions/streamer/:streamerId` - Subscriptores del streamer

#### Endpoints de Chat
- `GET /api/chat/:streamId` - Historial de chat
- WebSocket en `/ws/chat/:streamId`

---

### 2. **WebSocket Server** (Socket.io/ws)

#### Eventos del Cliente
- `join_stream` - Unirse a un stream
- `leave_stream` - Salir de un stream
- `send_message` - Enviar mensaje al chat
- `subscribe_notifications` - Suscribirse a notificaciones

#### Eventos del Servidor
- `viewer_count` - Actualización de espectadores
- `new_message` - Nuevo mensaje de chat
- `stream_started` - Un streamer ha comenzado
- `stream_ended` - Stream finalizado

---

### 3. **RTMP Server** (Node-Media-Server)

#### Configuración
```javascript
{
  rtmp: {
    port: 1935,
    chunk_size: 60000,
    gop_cache: true,
    ping: 30,
    ping_timeout: 60
  },
  http: {
    port: 8000,
    allow_origin: '*'
  },
  trans: {
    ffmpeg: '/usr/bin/ffmpeg',
    tasks: [
      {
        app: 'live',
        hls: true,
        hlsFlags: '[hls_time=2:hls_list_size=3:hls_flags=delete_segments]',
        dash: true,
        dashFlags: '[f=dash:window_size=3:extra_window_size=5]'
      }
    ]
  }
}
```

#### Hooks
- `prePublish` - Validar stream_key antes de publicar
- `postPublish` - Actualizar DB (is_streaming = true)
- `donePublish` - Finalizar stream en DB

---

## 📦 Estructura de Carpetas

```
back-streams/
├── src/
│   ├── config/
│   │   ├── database.js
│   │   ├── rtmp.js
│   │   └── redis.js
│   ├── controllers/
│   │   ├── auth.controller.js
│   │   ├── stream.controller.js
│   │   ├── user.controller.js
│   │   └── subscription.controller.js
│   ├── models/
│   │   ├── User.js
│   │   ├── Stream.js
│   │   ├── Subscription.js
│   │   └── ChatMessage.js
│   ├── middlewares/
│   │   ├── auth.middleware.js
│   │   └── validate.middleware.js
│   ├── routes/
│   │   ├── auth.routes.js
│   │   ├── stream.routes.js
│   │   ├── user.routes.js
│   │   └── subscription.routes.js
│   ├── services/
│   │   ├── rtmp.service.js
│   │   ├── stream.service.js
│   │   ├── notification.service.js
│   │   └── transcode.service.js
│   ├── websocket/
│   │   ├── chat.handler.js
│   │   └── stream.handler.js
│   └── server.js
├── migrations/
├── .env.example
├── package.json
└── README.md
```

---

## 🚀 Stack Tecnológico

### Core
- **Runtime**: Node.js 20+
- **Framework**: Express.js / Fastify
- **Database**: PostgreSQL 15+
- **Cache**: Redis 7+

### Streaming
- **RTMP Server**: node-media-server
- **Transcoding**: FFmpeg
- **Protocol**: HLS (HTTP Live Streaming)

### Real-time
- **WebSocket**: Socket.io
- **Message Queue**: Bull (Redis-based)

### Autenticación
- **JWT**: jsonwebtoken
- **Hashing**: bcrypt

---

## 🔄 Flujo de Subscripción

### 1. Usuario se Suscribe
```javascript
POST /api/subscriptions
{
  "streamerId": "uuid-streamer",
  "tier": "pro", // basic | pro | premium
  "paymentMethod": "card"
}
```

### 2. Procesamiento
- Validar usuario y streamer
- Procesar pago (Stripe/PayPal)
- Crear registro en `subscriptions`
- Emitir evento `new_subscriber` (WebSocket)

### 3. Verificar Subscripción
```javascript
GET /api/subscriptions/:userId
Response: [
  {
    "id": "uuid",
    "streamer": { ... },
    "tier": "pro",
    "status": "active",
    "expiresAt": "2025-11-02T00:00:00Z"
  }
]
```

### 4. Beneficios por Tier
- **Basic**: Sin anuncios, chat sin restricciones
- **Pro**: Emotes exclusivos, badge especial
- **Premium**: Acceso prioritario, contenido exclusivo

---

## 📡 Eventos WebSocket

### Chat
```javascript
// Cliente envía
socket.emit('send_message', {
  streamId: 'uuid',
  message: 'Hola!'
});

// Servidor broadcast
socket.broadcast.to(streamId).emit('new_message', {
  user: { username, avatar },
  message: 'Hola!',
  timestamp: '2025-10-02T23:15:00Z'
});
```

### Notificaciones de Stream
```javascript
// Cuando streamer inicia
io.emit('stream_started', {
  streamId: 'uuid',
  streamer: { username, avatar },
  title: 'Streaming Now!'
});
```

---

## 🔒 Seguridad

### Validaciones
- Stream key único e irrepetible
- Rate limiting en APIs (100 req/min)
- Sanitización de mensajes de chat
- CORS configurado correctamente

### Autenticación
- JWT con refresh tokens
- Stream key hasheado en DB
- HTTPS en producción
- Secure WebSocket (WSS)

---

## 📊 Métricas y Monitoreo

### KPIs
- Viewers concurrentes por stream
- Latencia promedio (target: <3s)
- Uptime del servidor RTMP
- Tasa de conversión a subscripciones

### Logging
- Winston para logs estructurados
- Niveles: error, warn, info, debug
- Rotación diaria de logs

---

## 🧪 Testing

### Unit Tests
- Controllers
- Services
- Middlewares

### Integration Tests
- API endpoints
- WebSocket events
- RTMP hooks

### Load Testing
- Artillery/k6 para simular carga
- Target: 1000 viewers concurrentes

---

## 📝 Variables de Entorno

```env
# Server
PORT=3000
NODE_ENV=production

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/streams_db

# Redis
REDIS_URL=redis://localhost:6379

# JWT
JWT_SECRET=your-secret-key
JWT_EXPIRES_IN=1h
JWT_REFRESH_EXPIRES_IN=7d

# RTMP
RTMP_PORT=1935
HLS_PATH=/var/www/hls

# Storage
AWS_S3_BUCKET=stream-thumbnails
AWS_REGION=us-east-1

# Payments
STRIPE_SECRET_KEY=sk_test_xxx
```

---

## 🎯 Próximos Pasos

1. Configurar base de datos PostgreSQL
2. Implementar modelos y migraciones
3. Configurar servidor RTMP
4. Desarrollar API REST
5. Implementar WebSocket para chat
6. Integrar sistema de subscripciones
7. Testing y optimización
8. Deploy en producción
