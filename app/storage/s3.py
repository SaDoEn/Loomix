import json
import uuid
from http.client import HTTPException

import aioboto3
from fastapi import UploadFile
from enum import unique
from app.core.config import settings

class S3Storage:
    def __init__(self):
        self.session = aioboto3.Session()
        self.endpoint_url = f"http://{settings.MINIO_ENDPOINT}"

    async def init_bucket(self):
        async with self.session.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=settings.MINIO_ACCESS_KEY,
            aws_secret_access_key=settings.MINIO_SECRET_KEY,
        ) as s3:
            try:
                await s3.head_bucket(Bucket=settings.MINIO_BUCKET)
            except Exception:
                await s3.create_bucket(Bucket=settings.MINIO_BUCKET)
                print(f"📦 Бакет '{settings.MINIO_BUCKET}' успішно створено в MinIO!")

            bucket_policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "PublicReadGetObject",
                        "Effect": "Allow",
                        "Principal": "*",
                        "Action": ["s3:GetObject"],
                        "Resource": [f"arn:aws:s3:::{settings.MINIO_BUCKET}/*"]
                    }
                ]
            }

            try:
                await s3.put_bucket_policy(
                    Bucket=settings.MINIO_BUCKET,
                    Policy=json.dumps(bucket_policy)
                )
                print(f"🔓 Політику Public Read успішно застосовано до бакета '{settings.MINIO_BUCKET}'!")
            except Exception as e:
                print(f"❌ Помилка встановлення політики бакета: {e}")

    async def upload_file(self, file: UploadFile, folder: str = "posts") -> str:
        """
        Завантажує файл у MinIO та повертає шлях до нього.
        folder: "avatars" або "posts"
        """
        file_extension = file.filename.split(".")[-1]
        unique_filename = f"{folder}/{uuid.uuid4()}.{file_extension}"

        async with self.session.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=settings.MINIO_ACCESS_KEY,
            aws_secret_access_key=settings.MINIO_SECRET_KEY,
        ) as s3:
            file_content = await file.read()

            await s3.put_object(
                Bucket=settings.MINIO_BUCKET,
                Key=unique_filename,
                Body=file_content,
                ContentType=file.content_type
            )

            return unique_filename

    async def delete_file(self, file_url: str):
        """
        Видаляє файл з MinIO за його шляхом (file_url).
        """
        async with self.session.client(
                "s3",
                endpoint_url=self.endpoint_url,
                aws_access_key_id=settings.MINIO_ACCESS_KEY,
                aws_secret_access_key=settings.MINIO_SECRET_KEY,
        ) as s3:
            try:
                await s3.delete_object(Bucket=settings.MINIO_BUCKET, Key=file_url)
                print(f"🗑️ Файл {file_url} успішно видалено з MinIO")
            except Exception as e:
                print(f"❌ Помилка видалення файлу з MinIO: {e}")
                raise HTTPException(
                    status_code=500,
                    detail="Не вдалося видалити файл зі сховища"
                )

storage = S3Storage()