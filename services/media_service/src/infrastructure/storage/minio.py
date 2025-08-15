import io
from datetime import timedelta
from typing import Optional
from uuid import uuid4

from minio import Minio
from minio.error import S3Error

from src.config.config import config
from src.config.logger_config import log
from src.core.exceptions import ExternalServiceError, InvalidInputError


class MinioClient:
    """
    Client for interacting with MinIO.
    Handles file uploads and presigned URL generation.
    Designed to work with the media-service and MinIO server.
    Uses synchronous minio-py (no async support).
    """

    def __init__(self):
        """
        Initialize the MinIO client with connection details from config.
        """
        try:
            self.client = Minio(
                config.MINIO_ENDPOINT,
                access_key=config.MINIO_ACCESS_KEY,
                secret_key=config.MINIO_SECRET_KEY,
                secure=config.MINIO_SECURE,  # Set to False for local development
            )
            self.bucket_name = config.MINIO_BUCKET_NAME or "observashop-media"
            self._ensure_bucket()
        except Exception as e:
            log.critical("Failed to initialize MinIO client", error=str(e))
            raise ExternalServiceError(
                service_name="minio", message="Failed to connect to storage service"
            ) from e

    def _ensure_bucket(self):
        """
        Ensure the target bucket exists.
        Creates it if it doesn't.
        """
        try:
            if not self.client.bucket_exists(self.bucket_name):
                log.info("Creating MinIO bucket", bucket=self.bucket_name)
                self.client.make_bucket(self.bucket_name)
                log.info("MinIO bucket created", bucket=self.bucket_name)
            else:
                log.debug("MinIO bucket already exists", bucket=self.bucket_name)
        except S3Error as e:
            log.critical(
                "Failed to ensure MinIO bucket exists",
                bucket=self.bucket_name,
                error=str(e),
            )
            if e.code == "InvalidBucketName":
                raise InvalidInputError(
                    f"Invalid bucket name: {self.bucket_name}"
                ) from e
            raise ExternalServiceError(
                service_name="minio", message="Failed to connect to storage service"
            ) from e
        except Exception as e:
            log.critical(
                "Unexpected error ensuring MinIO bucket",
                bucket=self.bucket_name,
                error=str(e),
            )
            raise ExternalServiceError(
                service_name="minio", message="Unexpected error during bucket setup"
            ) from e

    def upload_file(self, file_data: bytes, file_name: str, content_type: str) -> str:
        """
        Upload a file to MinIO.
        Args:
            file_data: Raw bytes of the file.
            file_name: Original filename.
            content_type: MIME type (e.g., image/jpeg).
        Returns:
            storage_key: The path where the file was stored (e.g., media/uuid.jpg)
        Raises:
            InvalidInputError: If file is empty or invalid.
            ExternalServiceError: If upload fails.
        """
        if not file_data:
            raise InvalidInputError("File data is empty")

        if not file_name:
            raise InvalidInputError("File name is required")

        if not content_type:
            raise InvalidInputError("Content type is required")

        # Generate a unique storage key
        file_extension = file_name.split(".")[-1] if "." in file_name else ""
        object_name = (
            f"media/{uuid4()}.{file_extension}"
            if file_extension
            else f"media/{uuid4()}"
        )

        try:
            self.client.put_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                data=io.BytesIO(file_data),
                length=len(file_data),
                content_type=content_type,
            )
            log.info(
                "File uploaded to MinIO",
                bucket=self.bucket_name,
                object_name=object_name,
                size=len(file_data),
            )
            return object_name

        except S3Error as e:
            log.warning(
                "S3Error during file upload",
                bucket=self.bucket_name,
                object_name=object_name,
                error=str(e),
            )
            if e.code == "NoSuchBucket":
                raise ExternalServiceError(
                    service_name="minio", message="Media storage bucket not found"
                ) from e
            raise ExternalServiceError(
                service_name="minio", message=f"Failed to upload file: {str(e)}"
            ) from e

        except Exception as e:
            log.critical(
                "Unexpected error during file upload",
                bucket=self.bucket_name,
                object_name=object_name,
                error=str(e),
            )
            raise ExternalServiceError(
                service_name="minio",
                message="Failed to upload file due to internal error",
            ) from e

    def get_presigned_url(self, object_name: str, expires: int = 3600) -> str:
        """
        Generate a presigned URL for accessing a file.
        Args:
            object_name: Path to the file in MinIO (e.g., media/uuid.jpg)
            expires: Time in seconds until the URL expires (default: 1 hour)
        Returns:
            Presigned URL string
        Raises:
            ExternalServiceError: If URL generation fails
        """
        try:
            presigned_url = self.client.presigned_get_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                expires=timedelta(seconds=expires),
            )
            log.info(
                "Presigned URL generated", object_name=object_name, expires_in=expires
            )
            return presigned_url

        except S3Error as e:
            log.warning(
                "S3Error during presigned URL generation",
                object_name=object_name,
                error=str(e),
            )
            raise ExternalServiceError(
                service_name="minio",
                message=f"Failed to generate presigned URL: {str(e)}",
            ) from e

        except Exception as e:
            log.critical(
                "Unexpected error during presigned URL generation",
                object_name=object_name,
                error=str(e),
            )
            raise ExternalServiceError(
                service_name="minio",
                message="Failed to generate presigned URL due to internal error",
            ) from e
