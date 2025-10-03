from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from sqlalchemy import text
import secrets

router = APIRouter(prefix="/api/admin", tags=["admin"])

@router.post("/generate-stream-key")
async def generar_stream_key(
    user_email: str,
    db: Session = Depends(get_db)
):
    """
    Genera un nuevo stream_key para un usuario admin

    Uso: POST /api/admin/generate-stream-key?user_email=admin@gallos.pe
    """
    try:
        # Verificar que el usuario existe y es admin
        query = text("""
            SELECT id, email, es_admin
            FROM users
            WHERE email = :email
        """)

        result = db.execute(query, {"email": user_email}).fetchone()

        if not result:
            raise HTTPException(status_code=404, detail=f"Usuario {user_email} no encontrado")

        user_id, email, es_admin = result

        if not es_admin:
            raise HTTPException(status_code=403, detail=f"Usuario {email} no es admin")

        # Generar nuevo stream_key (64 caracteres hexadecimales)
        new_stream_key = secrets.token_hex(32)

        # Actualizar stream_key en la base de datos
        update_query = text("""
            UPDATE users
            SET stream_key = :stream_key
            WHERE id = :user_id
            RETURNING email, stream_key
        """)

        updated = db.execute(update_query, {
            "stream_key": new_stream_key,
            "user_id": user_id
        }).fetchone()

        db.commit()

        print(f"✅ [ADMIN] Stream key generado para {email}")

        return {
            "status": "ok",
            "user_email": updated[0],
            "stream_key": updated[1],
            "obs_config": {
                "servidor_rtmp": "rtmp://185.188.249.229/live",
                "stream_key": updated[1]
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"❌ [ADMIN] Error generando stream key: {e}")
        raise HTTPException(status_code=500, detail=f"Error generando stream key: {str(e)}")


@router.get("/get-stream-key")
async def obtener_stream_key(
    user_email: str,
    db: Session = Depends(get_db)
):
    """
    Obtiene el stream_key actual de un usuario admin

    Uso: GET /api/admin/get-stream-key?user_email=admin@gallos.pe
    """
    try:
        query = text("""
            SELECT email, stream_key, es_admin
            FROM users
            WHERE email = :email
        """)

        result = db.execute(query, {"email": user_email}).fetchone()

        if not result:
            raise HTTPException(status_code=404, detail=f"Usuario {user_email} no encontrado")

        email, stream_key, es_admin = result

        if not es_admin:
            raise HTTPException(status_code=403, detail=f"Usuario {email} no es admin")

        if not stream_key:
            raise HTTPException(
                status_code=404,
                detail=f"Usuario {email} no tiene stream_key. Genera uno con POST /api/admin/generate-stream-key"
            )

        return {
            "status": "ok",
            "user_email": email,
            "stream_key": stream_key,
            "obs_config": {
                "servidor_rtmp": "rtmp://185.188.249.229/live",
                "stream_key": stream_key
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ [ADMIN] Error obteniendo stream key: {e}")
        raise HTTPException(status_code=500, detail=f"Error obteniendo stream key: {str(e)}")
