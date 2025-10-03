import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from app.core.config import settings
import os
from datetime import datetime

class R2Service:
    """Servicio para subir videos a Cloudflare R2"""

    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            endpoint_url=settings.R2_ENDPOINT,
            aws_access_key_id=settings.R2_ACCESS_KEY_ID,
            aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
            config=Config(signature_version='s3v4')
        )
        self.bucket_name = settings.R2_BUCKET_NAME
        self.public_url = settings.R2_PUBLIC_URL

    def subir_video(self, archivo_local: str, evento_id: int) -> str:
        """
        Sube un video a Cloudflare R2

        Args:
            archivo_local: Ruta del archivo en el servidor (ej: /var/recordings/stream.flv)
            evento_id: ID del evento de la base de datos

        Returns:
            URL pública del video en R2
        """
        try:
            # Generar nombre único para el video
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            extension = os.path.splitext(archivo_local)[1]  # .flv, .mp4, etc
            nombre_archivo = f"eventos/{evento_id}_{timestamp}{extension}"

            print(f"📤 [R2] Subiendo video a R2: {nombre_archivo}")

            # Subir archivo
            self.s3_client.upload_file(
                archivo_local,
                self.bucket_name,
                nombre_archivo,
                ExtraArgs={
                    'ContentType': 'video/mp4',
                    'CacheControl': 'max-age=31536000',  # Cache por 1 año
                }
            )

            # URL pública del video
            video_url = f"{self.public_url}/{nombre_archivo}"

            print(f"✅ [R2] Video subido exitosamente: {video_url}")
            return video_url

        except ClientError as e:
            print(f"❌ [R2] Error subiendo video: {e}")
            raise Exception(f"Error subiendo video a R2: {str(e)}")
        except FileNotFoundError:
            print(f"❌ [R2] Archivo no encontrado: {archivo_local}")
            raise Exception(f"Archivo no encontrado: {archivo_local}")

    def eliminar_video(self, nombre_archivo: str) -> bool:
        """
        Elimina un video de R2

        Args:
            nombre_archivo: Ruta del archivo en R2 (ej: eventos/123_20251004_120000.mp4)

        Returns:
            True si se eliminó correctamente
        """
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=nombre_archivo
            )
            print(f"🗑️ [R2] Video eliminado: {nombre_archivo}")
            return True
        except ClientError as e:
            print(f"❌ [R2] Error eliminando video: {e}")
            return False

    def listar_videos(self, prefix: str = "eventos/") -> list:
        """
        Lista todos los videos en R2

        Args:
            prefix: Prefijo para filtrar (ej: "eventos/")

        Returns:
            Lista de objetos en R2
        """
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )

            if 'Contents' not in response:
                return []

            videos = []
            for obj in response['Contents']:
                videos.append({
                    'key': obj['Key'],
                    'size': obj['Size'],
                    'last_modified': obj['LastModified'],
                    'url': f"{self.public_url}/{obj['Key']}"
                })

            return videos
        except ClientError as e:
            print(f"❌ [R2] Error listando videos: {e}")
            return []

# Singleton
r2_service = R2Service()
