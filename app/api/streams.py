from fastapi import APIRouter, Depends, HTTPException, Form
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.config import settings
from sqlalchemy import text
import boto3
from botocore.exceptions import ClientError
import os
from datetime import datetime

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


@router.post("/upload-recording")
async def upload_recording(
    path: str = Form(...),  # nginx-rtmp envía: /var/www/recordings/stream-20250103-194530.mp4
    name: str = Form(...),  # nginx-rtmp envía: stream_key
    db: Session = Depends(get_db)
):
    """
    Endpoint llamado por nginx-rtmp cuando termina de grabar un stream

    nginx.conf debe tener:
    on_record_done http://appstreamscastadegallos-production.up.railway.app/api/streams/upload-recording;

    Flujo:
    1. Recibe notificación de nginx cuando termina grabación
    2. Descarga video del VPS Contabo (vía HTTP)
    3. Sube video a Cloudflare R2
    4. Actualiza eventos_transmision.video_url con URL pública
    5. Marca evento como "finalizado"
    """
    print(f"📹 [UPLOAD] Iniciando upload de grabación: {path}")
    print(f"📹 [UPLOAD] Stream_key: {name[:20]}...")

    try:
        # 1. Generar nombre único para el video
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = f"streams/{name[:16]}-{timestamp}.mp4"

        # 2. Obtener usuario por stream_key
        user_query = text("""
            SELECT id, email FROM users
            WHERE stream_key = :stream_key
        """)
        user = db.execute(user_query, {"stream_key": name}).fetchone()

        if not user:
            print(f"⚠️ [UPLOAD] Stream_key no encontrado, grabación guardada pero no asociada")
            return {"status": "warning", "message": "Stream_key no encontrado"}

        user_id, user_email = user
        print(f"📹 [UPLOAD] Usuario encontrado: {user_email}")

        # 3. OPCIÓN A: Si nginx-rtmp está en el MISMO servidor que Backend
        # Lee el archivo directamente del filesystem
        # video_data = open(path, 'rb').read()

        # 3. OPCIÓN B: nginx-rtmp está en Contabo VPS (diferente servidor)
        # Descarga el video vía HTTP desde Contabo
        import requests

        # Construir URL pública del archivo grabado
        # path = /var/www/recordings/stream-20250103-194530.mp4
        # URL = http://185.188.249.229/recordings/stream-20250103-194530.mp4
        filename_only = os.path.basename(path)
        video_url_contabo = f"http://{settings.CONTABO_IP}/recordings/{filename_only}"

        print(f"📹 [UPLOAD] Descargando video desde Contabo: {video_url_contabo}")

        response = requests.get(video_url_contabo, timeout=300)  # 5 min timeout

        if response.status_code != 200:
            raise Exception(f"Error descargando video de Contabo: HTTP {response.status_code}")

        video_data = response.content
        video_size_mb = len(video_data) / (1024 * 1024)
        print(f"📹 [UPLOAD] Video descargado: {video_size_mb:.2f} MB")

        # 4. Subir a Cloudflare R2
        print(f"☁️ [UPLOAD] Subiendo a R2: {filename}")

        s3_client = boto3.client(
            's3',
            endpoint_url=settings.R2_ENDPOINT,
            aws_access_key_id=settings.R2_ACCESS_KEY_ID,
            aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
            region_name='auto'
        )

        s3_client.put_object(
            Bucket=settings.R2_BUCKET_NAME,
            Key=filename,
            Body=video_data,
            ContentType='video/mp4'
        )

        # 5. URL pública del video
        public_url = f"{settings.R2_PUBLIC_URL}/{filename}"
        print(f"✅ [UPLOAD] Video subido a R2: {public_url}")

        # 6. Solo subir a R2, no actualizar BD (por ahora)
        print(f"✅ [UPLOAD] Video guardado en R2, no se actualiza BD")

        return {
            "status": "ok",
            "message": "Video subido exitosamente a R2",
            "video_url": public_url,
            "video_size_mb": round(video_size_mb, 2),
            "user_email": user_email
        }

    except Exception as e:
        db.rollback()
        print(f"❌ [UPLOAD] Error subiendo grabación: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error subiendo grabación: {str(e)}"
        )
