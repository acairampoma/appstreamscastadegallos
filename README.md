# 🎬 Backend Servidor de Streams

Backend para manejar transmisiones en vivo desde OBS a tu app Flutter.

## 📦 Instalación

```bash
# Crear entorno virtual
python -m venv venv

# Activar entorno virtual
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt
```

## ⚙️ Configuración

1. Copia `.env.example` a `.env`
2. Configura las variables de entorno:
   - `DATABASE_URL`: PostgreSQL de Railway
   - `R2_ACCESS_KEY_ID`: Access Key de Cloudflare R2
   - `R2_SECRET_ACCESS_KEY`: Secret Key de Cloudflare R2
   - `CONTABO_IP`: IP de tu VPS Contabo

## 🚀 Ejecutar

```bash
# Desarrollo (con auto-reload)
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# O simplemente:
python app/main.py
```

El servidor estará en: **http://localhost:8000**

## 📡 Endpoints

### `POST /api/streams/validate`
Valida el stream_key cuando OBS se conecta a nginx-rtmp.

**Usado por:** nginx-rtmp (automático)

**Body:**
```
name={stream_key}
```

**Response:**
```json
{
  "status": "ok",
  "user_id": 1,
  "email": "admin@gallos.pe"
}
```

### `GET /api/streams/live`
Obtiene el stream actualmente en vivo.

**Usado por:** App Flutter

**Response:**
```json
{
  "is_live": true,
  "evento": {
    "id": 123,
    "titulo": "Gran Pelea - Sábado",
    "hls_url": "http://185.188.249.229/hls/stream.m3u8",
    "thumbnail_url": "https://...",
    "fecha_evento": "2025-10-04T20:00:00"
  }
}
```

### `POST /api/streams/start?evento_id=123`
Marca un evento como "en_vivo".

**Usado por:** Webhook de nginx-rtmp o manual

### `POST /api/streams/stop?evento_id=123`
Marca un evento como "finalizado".

**Usado por:** Webhook de nginx-rtmp o manual

## 🗄️ Base de Datos

Usa las tablas existentes de tu Railway PostgreSQL:
- `users` (con `stream_key` agregado)
- `eventos_transmision` (con `hls_url` agregado)

## 📤 Subir a Railway

1. Crear nuevo proyecto en Railway:
   ```bash
   railway login
   railway init
   ```

2. Agregar variables de entorno en Railway Dashboard

3. Deploy:
   ```bash
   railway up
   ```

O conecta tu repositorio GitHub y Railway hará deploy automático.

## 🧪 Probar Localmente

```bash
# 1. Iniciar servidor
python app/main.py

# 2. Probar validación (simular nginx-rtmp)
curl -X POST http://localhost:8000/api/streams/validate \
  -d "name=TU_STREAM_KEY_DE_LA_DB"

# 3. Probar obtener stream en vivo
curl http://localhost:8000/api/streams/live
```

## 📂 Estructura

```
back-streams/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app principal
│   ├── api/
│   │   └── streams.py       # Endpoints de streams
│   ├── core/
│   │   ├── config.py        # Configuración
│   │   └── database.py      # Conexión PostgreSQL
│   └── services/
│       └── r2_service.py    # Servicio Cloudflare R2
├── .env                      # Variables de entorno (NO SUBIR A GIT)
├── .env.example              # Ejemplo de variables
├── requirements.txt          # Dependencias Python
└── README.md                 # Este archivo
```

## 🔗 Stack

- **FastAPI**: Framework web
- **PostgreSQL**: Base de datos (Railway)
- **Cloudflare R2**: Almacenamiento videos
- **Contabo VPS**: Servidor nginx-rtmp
