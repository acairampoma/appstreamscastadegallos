from fastapi import APIRouter, Depends, HTTPException, Form
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.config import settings
from sqlalchemy import text

router = APIRouter(prefix="/api/streams", tags=["streams"])

@router.post("/validate")
async def validar_stream_key(
    name: str = Form(...),  # nginx-rtmp envía el stream_key como "name"
    db: Session = Depends(get_db)
):
    """
    Endpoint llamado por nginx-rtmp cuando OBS intenta publicar un stream

    nginx.conf debe tener:
    on_publish http://tu-backend.railway.app/api/streams/validate;
    """
    print(f"🔐 [VALIDATE] Validando stream_key: {name[:20]}...")

    try:
        # Consultar si existe un usuario admin con ese stream_key
        query = text("""
            SELECT id, email, es_admin, is_active
            FROM users
            WHERE stream_key = :stream_key
        """)

        result = db.execute(query, {"stream_key": name}).fetchone()

        if not result:
            print(f"❌ [VALIDATE] Stream_key no encontrado")
            raise HTTPException(status_code=403, detail="Stream key inválido")

        # Verificar que sea admin y esté activo
        user_id, email, es_admin, is_active = result

        if not es_admin:
            print(f"❌ [VALIDATE] Usuario {email} no es admin")
            raise HTTPException(status_code=403, detail="Usuario no autorizado para transmitir")

        if not is_active:
            print(f"❌ [VALIDATE] Usuario {email} está desactivado")
            raise HTTPException(status_code=403, detail="Usuario desactivado")

        print(f"✅ [VALIDATE] Stream_key válido para usuario: {email}")

        return {
            "status": "ok",
            "user_id": user_id,
            "email": email
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ [VALIDATE] Error: {e}")
        raise HTTPException(status_code=500, detail=f"Error validando stream key: {str(e)}")


@router.get("/live")
async def obtener_stream_en_vivo(db: Session = Depends(get_db)):
    """
    Obtiene el stream actualmente en vivo

    Tu app Flutter llama este endpoint para obtener la URL del HLS
    """
    try:
        query = text("""
            SELECT
                e.id,
                e.titulo,
                e.descripcion,
                e.thumbnail_url,
                e.estado,
                e.fecha_evento,
                u.email as admin_email
            FROM eventos_transmision e
            JOIN users u ON e.admin_creador_id = u.id
            WHERE e.estado = 'en_vivo'
            ORDER BY e.fecha_evento DESC
            LIMIT 1
        """)

        result = db.execute(query).fetchone()

        if not result:
            return {
                "is_live": False,
                "message": "No hay transmisión en vivo actualmente"
            }

        evento_id, titulo, descripcion, thumbnail_url, estado, fecha_evento, admin_email = result

        # URL del HLS en tu servidor Contabo
        hls_url = f"{settings.HLS_BASE_URL}/stream.m3u8"

        return {
            "is_live": True,
            "evento": {
                "id": evento_id,
                "titulo": titulo,
                "descripcion": descripcion,
                "thumbnail_url": thumbnail_url,
                "hls_url": hls_url,
                "fecha_evento": fecha_evento.isoformat(),
                "admin": admin_email
            }
        }

    except Exception as e:
        print(f"❌ [LIVE] Error: {e}")
        raise HTTPException(status_code=500, detail=f"Error obteniendo stream en vivo: {str(e)}")


@router.post("/start")
async def iniciar_stream(
    evento_id: int,
    db: Session = Depends(get_db)
):
    """
    Marca un evento como "en_vivo"

    Llamar esto cuando nginx-rtmp confirma que el stream comenzó
    """
    try:
        query = text("""
            UPDATE eventos_transmision
            SET estado = 'en_vivo',
                hls_url = :hls_url
            WHERE id = :evento_id
            RETURNING id, titulo
        """)

        hls_url = f"{settings.HLS_BASE_URL}/stream.m3u8"

        result = db.execute(query, {
            "evento_id": evento_id,
            "hls_url": hls_url
        }).fetchone()

        if not result:
            raise HTTPException(status_code=404, detail="Evento no encontrado")

        db.commit()

        print(f"🔴 [START] Stream iniciado para evento #{evento_id}: {result[1]}")

        return {
            "status": "ok",
            "evento_id": result[0],
            "titulo": result[1],
            "hls_url": hls_url
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"❌ [START] Error: {e}")
        raise HTTPException(status_code=500, detail=f"Error iniciando stream: {str(e)}")


@router.post("/stop")
async def detener_stream(
    evento_id: int,
    db: Session = Depends(get_db)
):
    """
    Marca un evento como "finalizado"

    Llamar esto cuando nginx-rtmp detecta que el stream terminó
    """
    try:
        query = text("""
            UPDATE eventos_transmision
            SET estado = 'finalizado',
                fecha_fin_evento = NOW()
            WHERE id = :evento_id
            RETURNING id, titulo
        """)

        result = db.execute(query, {"evento_id": evento_id}).fetchone()

        if not result:
            raise HTTPException(status_code=404, detail="Evento no encontrado")

        db.commit()

        print(f"⏹️ [STOP] Stream finalizado para evento #{evento_id}: {result[1]}")

        return {
            "status": "ok",
            "evento_id": result[0],
            "titulo": result[1]
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"❌ [STOP] Error: {e}")
        raise HTTPException(status_code=500, detail=f"Error deteniendo stream: {str(e)}")
