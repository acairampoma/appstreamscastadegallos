from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from sqlalchemy import text
import secrets
import boto3
from botocore.exceptions import ClientError
from app.core.config import settings

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


@router.get("/test-r2")
async def test_cloudflare_r2():
    """
    Testea la conexión a Cloudflare R2

    Uso: GET /api/admin/test-r2
    """
    try:
        print("🔍 [ADMIN] Testeando conexión a Cloudflare R2...")

        # Crear cliente S3 para R2
        s3_client = boto3.client(
            's3',
            endpoint_url=settings.R2_ENDPOINT,
            aws_access_key_id=settings.R2_ACCESS_KEY_ID,
            aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
            region_name='auto'
        )

        # Test 1: Listar buckets
        try:
            buckets = s3_client.list_buckets()
            print(f"✅ [ADMIN] Buckets encontrados: {[b['Name'] for b in buckets['Buckets']]}")
        except ClientError as e:
            print(f"⚠️ [ADMIN] Error listando buckets: {e}")
            buckets = None

        # Test 2: Verificar bucket específico existe
        bucket_exists = False
        try:
            s3_client.head_bucket(Bucket=settings.R2_BUCKET_NAME)
            bucket_exists = True
            print(f"✅ [ADMIN] Bucket '{settings.R2_BUCKET_NAME}' existe y es accesible")
        except ClientError as e:
            print(f"❌ [ADMIN] Bucket '{settings.R2_BUCKET_NAME}' no existe o no es accesible: {e}")

        # Test 3: Listar objetos en el bucket (primeros 10)
        objects = []
        total_objects = 0
        if bucket_exists:
            try:
                response = s3_client.list_objects_v2(
                    Bucket=settings.R2_BUCKET_NAME,
                    MaxKeys=10
                )
                total_objects = response.get('KeyCount', 0)
                objects = [obj['Key'] for obj in response.get('Contents', [])]
                print(f"✅ [ADMIN] Primeros objetos en bucket: {objects}")
            except ClientError as e:
                print(f"⚠️ [ADMIN] Error listando objetos: {e}")

        # Test 4: Subir archivo de prueba
        test_upload = False
        test_file_key = "test/connection-test.txt"
        test_url = None
        try:
            s3_client.put_object(
                Bucket=settings.R2_BUCKET_NAME,
                Key=test_file_key,
                Body=b"Test de conexion desde backend - " + str(secrets.token_hex(8)).encode(),
                ContentType='text/plain'
            )
            test_upload = True
            test_url = f"{settings.R2_PUBLIC_URL}/{test_file_key}"
            print(f"✅ [ADMIN] Archivo de prueba subido: {test_url}")
        except ClientError as e:
            print(f"❌ [ADMIN] Error subiendo archivo de prueba: {e}")

        return {
            "status": "ok",
            "r2_connection": "successful",
            "config": {
                "endpoint": settings.R2_ENDPOINT,
                "bucket_name": settings.R2_BUCKET_NAME,
                "public_url": settings.R2_PUBLIC_URL
            },
            "tests": {
                "list_buckets": "ok" if buckets else "failed",
                "bucket_exists": bucket_exists,
                "list_objects": "ok" if total_objects >= 0 else "failed",
                "upload_test_file": test_upload
            },
            "bucket_info": {
                "total_objects_shown": total_objects,
                "sample_objects": objects[:5] if objects else []
            },
            "test_file": {
                "uploaded": test_upload,
                "url": test_url
            }
        }

    except Exception as e:
        print(f"❌ [ADMIN] Error crítico testeando R2: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error conectando a Cloudflare R2: {str(e)}"
        )
