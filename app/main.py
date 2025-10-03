from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api import streams

app = FastAPI(
    title="Gallos Streaming Server",
    description="Backend para servidor de transmisiones en vivo",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(streams.router)

@app.get("/")
async def root():
    return {
        "message": "🎬 Gallos Streaming Server API",
        "version": "1.0.0",
        "endpoints": {
            "validate_stream": "POST /api/streams/validate",
            "get_live_stream": "GET /api/streams/live",
            "start_stream": "POST /api/streams/start",
            "stop_stream": "POST /api/streams/stop"
        }
    }

@app.get("/health")
async def health_check():
    """Endpoint para verificar que el servidor está funcionando"""
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "contabo_ip": settings.CONTABO_IP,
        "hls_base_url": settings.HLS_BASE_URL
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8004, reload=True)
