from datetime import datetime
from io import BytesIO
from typing import List, Optional, Tuple
from uuid import UUID, uuid4
from sqlmodel import Session, select
from sqlalchemy.exc import (
    IntegrityError,
    DataError,
    StatementError,
)
from minio.error import S3Error
from urllib3.exceptions import ProtocolError, ConnectionError, ReadTimeoutError

from src.config.logger_config import log
from src.core.exceptions import (
    MediaNotFoundError,
    MediaUploadError,
    InvalidMediaError,
    MediaAccessDeniedError,
    MediaDeletionError,
    DatabaseError,
)
from src.domain.models import Media
from src.infrastructure.storage.minio import MinioClient


class MediaService:
    """
    Service class for handling media-related business logic.
    Encapsulates upload, retrieval, listing, and deletion of media assets.
    Uses MinIO for storage and PostgreSQL for metadata.
    Designed to work behind Kong with JWT validation.
    """

    def __init__(self, session: Session, minio_client: MinioClient):
        """
        Initialize the service with a database session and MinIO client.
        Args:
            session: SQLModel session for database operations.
            minio_client: Client to interact with MinIO for file storage.
        """
        self.session = session
        self.minio_client = minio_client

    def upload_media(
        self,
        file_data: bytes,
        filename: str,
        content_type: str,
        owner_id: UUID,
        owner_type: str,
        user_id: UUID,
        permissions: set[str],
        is_superadmin: bool,
    ) -> Media:
        """
        Upload a new media file.
        Args:
            file_ Raw bytes of the file.
            filename: Original filename.
            content_type: MIME type (e.g., image/jpeg).
            owner_id: ID of the owning entity (e.g., product ID).
            owner_type: Type of owner (e.g., product, user).
            user_id: UUID of the uploading user.
            permissions: Set of permissions from JWT.
            is_superadmin: Whether the user is a superadmin.
        Returns:
            Created Media object.
        Raises:
            InvalidMediaError: If file is invalid.
            MediaUploadError: If upload fails.
            DatabaseError: If DB operation fails.
        """
        log.info(
            "Uploading media",
            filename=filename,
            content_type=content_type,
            owner_id=str(owner_id),
            owner_type=owner_type,
            user_id=str(user_id),
        )

        try:
            # ✅ 1. Validate input
            self._validate_upload_input(file_data, filename, content_type)
            self._ensure_user_can_upload(
                user_id, owner_type, permissions, is_superadmin
            )
            self._validate_media_type(content_type)

            # ✅ 2. Upload to MinIO
            storage_key = self._upload_to_minio(file_data, filename, content_type)

            # ✅ 3. Create and save metadata
            media = self._create_and_save_media(
                filename=filename,
                content_type=content_type,
                storage_key=storage_key,
                owner_id=owner_id,
                owner_type=owner_type,
                file_size=len(file_data),
            )

            log.info("Media uploaded successfully", media_id=str(media.id))
            return media

        except (InvalidMediaError, MediaAccessDeniedError) as e:
            log.warning("Media upload rejected", error=str(e))
            raise

        except MediaUploadError as e:
            log.critical("Failed to upload to MinIO", error=str(e))
            raise

        except DatabaseError as e:
            log.critical("Database error during media upload", error=str(e))
            raise

        except Exception as e:
            log.critical(
                "Unexpected error during media upload", error=str(e), exc_info=True
            )
            raise MediaUploadError("An unexpected error occurred during upload") from e

    def get_media_by_id(
        self, media_id: UUID, user_id: UUID, permissions: set[str], is_superadmin: bool
    ) -> Media:
        """
        Retrieve a media asset by ID with ownership/permission checks.
        Args:
            media_id: UUID of the media to retrieve.
            user_id: UUID of the requesting user.
            permissions: Set of permissions from JWT.
            is_superadmin: Whether the user is a superadmin.
        Returns:
            Media object.
        Raises:
            MediaNotFoundError: If media does not exist.
            MediaAccessDeniedError: If user is not authorized.
        """
        log.debug("Fetching media by ID", media_id=str(media_id), user_id=str(user_id))

        try:
            media = self.session.get(Media, media_id)
        except (DataError, StatementError) as e:
            log.critical("Database query error", media_id=str(media_id), error=str(e))
            raise DatabaseError("Invalid media ID format") from e
        except Exception as e:
            log.critical(
                "Unexpected database error", media_id=str(media_id), error=str(e)
            )
            raise DatabaseError("Failed to retrieve media") from e

        if not media:
            log.warning("Media not found", media_id=str(media_id))
            raise MediaNotFoundError(str(media_id))

        if not is_superadmin and media.owner_id != user_id:
            log.warning(
                "Media access denied", media_id=str(media.id), user_id=str(user_id)
            )
            raise MediaAccessDeniedError(str(media.id))

        log.info("Media fetched successfully", media_id=str(media.id))
        return media

    def list_media(
        self,
        user_id: UUID,
        permissions: set[str],
        is_superadmin: bool,
        limit: int = 10,
        offset: int = 0,
        owner_type: Optional[str] = None,
        owner_id: Optional[UUID] = None,
        sort: str = "created_at:desc",
    ) -> Tuple[List[Media], int]:
        """
        List media assets with pagination, filtering, and sorting.
        Args:
            user_id: UUID of the requesting user.
            permissions: Set of permissions from JWT.
            is_superadmin: Whether the user is a superadmin.
            limit: Number of items to return.
            offset: Number of items to skip.
            owner_type: Filter by owner type.
            owner_id: Filter by owner ID.
            sort: Sort by field:direction (e.g., created_at:desc).
        Returns:
            Tuple of (list of media, total count).
        """
        log.debug("Listing media", user_id=str(user_id), is_superadmin=is_superadmin)

        try:
            query = select(Media)

            # Superadmin sees all, others see only their own
            if not is_superadmin:
                query = query.where(Media.owner_id == user_id)

            if owner_type:
                query = query.where(Media.owner_type == owner_type)
            if owner_id:
                query = query.where(Media.owner_id == owner_id)

            # Sort
            sort_field, direction = (
                sort.split(":") if ":" in sort else ("created_at", "desc")
            )
            allowed_sort_fields = ["created_at", "filename", "file_size"]
            if sort_field not in allowed_sort_fields:
                raise InvalidMediaError(f"Invalid sort field: {sort_field}")
            if direction not in ["asc", "desc"]:
                raise InvalidMediaError(f"Invalid sort direction: {direction}")

            column = getattr(Media, sort_field)
            if direction == "desc":
                column = column.desc()
            query = query.order_by(column)

            # Count total
            count_query = query.with_only_columns(Media.id).order_by()
            total = len(self.session.exec(count_query).all())

            # Paginate
            query = query.offset(offset).limit(limit)
            media_list = self.session.exec(query).all()

            log.info("Media listed successfully", count=len(media_list), total=total)
            return media_list, total

        except InvalidMediaError:
            raise
        except Exception as e:
            log.critical(
                "Unexpected error during list media", error=str(e), exc_info=True
            )
            raise DatabaseError("Failed to list media due to internal error") from e

    def update_media(
        self,
        media_id: UUID,
        is_active: bool,
        user_id: UUID,
        permissions: set[str],
        is_superadmin: bool,
    ) -> Media:
        """
        Update media metadata (e.g., soft-delete).
        Args:
            media_id: UUID of the media to update.
            is_active: New active status.
            user_id: UUID of the requesting user.
            permissions: Set of permissions from JWT.
            is_superadmin: Whether the user is a superadmin.
        Returns:
            Updated Media object.
        """
        log.info(
            "Updating media",
            media_id=str(media_id),
            is_active=is_active,
            user_id=str(user_id),
        )

        media = self.get_media_by_id(media_id, user_id, permissions, is_superadmin)

        if not is_superadmin and media.owner_id != user_id:
            log.warning("User not authorized to update media", media_id=str(media_id))
            raise MediaAccessDeniedError(str(media_id))

        media.is_active = is_active
        media.updated_at = datetime.utcnow()

        try:
            self.session.add(media)
            self.session.commit()
            self.session.refresh(media)
            log.info("Media updated successfully", media_id=str(media.id))
            return media
        except Exception as e:
            log.critical(
                "Unexpected error during media update",
                media_id=str(media.id),
                error=str(e),
                exc_info=True,
            )
            raise DatabaseError("Failed to update media due to internal error") from e

    def delete_media(
        self, media_id: UUID, user_id: UUID, permissions: set[str], is_superadmin: bool
    ):
        """
        Delete a media asset (soft-delete).
        Args:
            media_id: UUID of the media to delete.
            user_id: UUID of the requesting user.
            permissions: Set of permissions from JWT.
            is_superadmin: Whether the user is a superadmin.
        Raises:
            MediaDeletionError: If deletion fails.
        """
        log.info("Deleting media", media_id=str(media_id), user_id=str(user_id))

        media = self.get_media_by_id(media_id, user_id, permissions, is_superadmin)

        if not is_superadmin and media.owner_id != user_id:
            log.warning("User not authorized to delete media", media_id=str(media_id))
            raise MediaAccessDeniedError(str(media_id))

        # Soft-delete in DB
        try:
            media.is_active = False
            self.session.add(media)
            self.session.commit()
            log.info("Media soft-deleted in database", media_id=str(media.id))
        except Exception as e:
            log.critical(
                "Database error during media deletion",
                media_id=str(media.id),
                error=str(e),
            )
            raise MediaDeletionError(
                str(media.id), "Failed to delete from database"
            ) from e

    def restore_media(
        self, media_id: UUID, user_id: UUID, permissions: set[str], is_superadmin: bool
    ) -> Media:
        """
        Restore a soft-deleted media asset.
        Args:
            media_id: UUID of the media to restore.
            user_id: UUID of the requesting user.
            permissions: Set of permissions from JWT.
            is_superadmin: Whether the user is a superadmin.
        Returns:
            Restored Media object.
        Raises:
            MediaNotFoundError: If media does not exist.
            MediaAccessDeniedError: If user is not authorized.
        """
        log.info("Restoring media", media_id=str(media_id), user_id=str(user_id))

        media = self.get_media_by_id(media_id, user_id, permissions, is_superadmin)

        if not is_superadmin and media.owner_id != user_id:
            log.warning("User not authorized to restore media", media_id=str(media_id))
            raise MediaAccessDeniedError(str(media_id))

        if media.is_active:
            log.debug("Media already active", media_id=str(media.id))
            return media

        try:
            media.is_active = True
            media.updated_at = datetime.utcnow()
            self.session.add(media)
            self.session.commit()
            self.session.refresh(media)
            log.info("Media restored successfully", media_id=str(media.id))
            return media
        except Exception as e:
            log.critical(
                "Unexpected error during media restore",
                media_id=str(media.id),
                error=str(e),
            )
            raise DatabaseError("Failed to restore media due to internal error") from e

    def replace_media(
        self,
        media_id: UUID,
        file_data: bytes,
        filename: str,
        content_type: str,
        user_id: UUID,
        permissions: set[str],
        is_superadmin: bool,
    ) -> Media:
        """
        Replace an existing media asset with a new file.
        Hard-deletes the old file from MinIO and uploads the new one.
        """
        log.info("Replacing media", media_id=str(media_id), user_id=str(user_id))

        media = self.get_media_by_id(media_id, user_id, permissions, is_superadmin)

        if not is_superadmin and media.owner_id != user_id:
            log.warning("User not authorized to replace media", media_id=str(media_id))
            raise MediaAccessDeniedError(str(media_id))

        try:
            storage_key = self._upload_to_minio(file_data, filename, content_type)
        except Exception as e:
            log.critical("Failed to upload replacement file", error=str(e))
            raise MediaUploadError("Failed to upload replacement file") from e

        try:
            self.minio_client.client.remove_object(
                bucket_name=self.minio_client.bucket_name, object_name=media.storage_key
            )
            log.info("Old media removed from MinIO", media_id=str(media.id))
        except Exception as e:
            log.warning(
                "Failed to delete old media from MinIO",
                media_id=str(media.id),
                error=str(e),
            )
            # Continue — old file can be cleaned up later

        media.filename = filename
        media.file_type = content_type
        media.file_size = len(file_data)
        media.storage_key = storage_key
        media.updated_at = datetime.utcnow()

        try:
            self.session.add(media)
            self.session.commit()
            self.session.refresh(media)
            log.info("Media replaced successfully", media_id=str(media.id))
            return media
        except Exception as e:
            log.critical(
                "Unexpected error during media replacement",
                media_id=str(media.id),
                error=str(e),
            )
            raise DatabaseError("Failed to replace media due to internal error") from e

    # --- Private Helper Methods ---

    def _validate_upload_input(
        self, file_data: bytes, filename: str, content_type: str
    ):
        """Validate basic upload input."""
        if not file_data:
            raise InvalidMediaError("File data is empty")
        if not filename:
            raise InvalidMediaError("Filename is required")
        if not content_type:
            raise InvalidMediaError("Content type is required")

    def _ensure_user_can_upload(
        self, user_id: UUID, owner_type: str, permissions: set[str], is_superadmin: bool
    ):
        """
        Ensure user can upload for this owner type.
        Requires: superadmin OR {owner_type}:upload permission
        """
        if is_superadmin:
            return

        required_permission = f"{owner_type}:upload"

        if required_permission not in permissions:
            log.warning(
                "User lacks permission to upload for owner type",
                user_id=str(user_id),
                owner_type=owner_type,
                required_permission=required_permission,
                available_permissions=list(permissions),
            )
            raise MediaAccessDeniedError(
                f"User does not have permission to upload for {owner_type}"
            )

        log.debug(
            "User has permission to upload",
            user_id=str(user_id),
            owner_type=owner_type,
            permission=required_permission,
        )

    def _validate_media_type(self, content_type: str):
        """Validate that the media type is allowed."""
        allowed_types = [
            "image/jpeg",
            "image/png",
            "image/webp",
            "image/gif",
            "video/mp4",
            "video/webm",
        ]
        if content_type not in allowed_types:
            raise InvalidMediaError(f"Unsupported media type: {content_type}")

    def _upload_to_minio(
        self, file_data: bytes, filename: str, content_type: str
    ) -> str:
        """Upload file to MinIO and return storage key."""
        try:
            # Generate unique storage key
            file_extension = filename.split(".")[-1] if "." in filename else "bin"
            object_name = f"media/{uuid4()}.{file_extension}"

            # Wrap bytes in BytesIO
            data = BytesIO(file_data)
            length = len(file_data)

            # Upload to MinIO
            self.minio_client.client.put_object(
                bucket_name=self.minio_client.bucket_name,
                object_name=object_name,
                data=data,
                length=length,
                content_type=content_type,
            )
            log.info("File uploaded to MinIO", object_name=object_name)
            return object_name

        except S3Error as e:
            if e.code == "NoSuchBucket":
                log.critical(
                    "MinIO bucket does not exist", bucket=self.minio_client.bucket_name
                )
                raise MediaUploadError("Media storage is not configured") from e
            if e.code == "AccessDenied":
                log.critical(
                    "MinIO access denied", bucket=self.minio_client.bucket_name
                )
                raise MediaUploadError("Insufficient permissions to upload") from e
            log.warning("S3Error during upload", extra={"error": str(e)})
            raise MediaUploadError(f"Failed to upload to storage: {e.message}") from e

        except (ConnectionError, ProtocolError) as e:
            log.critical("MinIO connection failed", extra={"error": str(e)})
            raise MediaUploadError("Storage service is unreachable") from e

        except ReadTimeoutError as e:
            log.critical("MinIO upload timeout", extra={"error": str(e)})
            raise MediaUploadError("Storage service timed out") from e

        except Exception as e:
            log.critical(
                "Unexpected error during MinIO upload", extra={"error": str(e)}
            )
            raise MediaUploadError("Failed to upload file due to internal error") from e

    def _create_and_save_media(
        self,
        filename: str,
        content_type: str,
        storage_key: str,
        owner_id: UUID,
        owner_type: str,
        file_size: int,
    ) -> Media:
        """Create and save media metadata in DB."""
        media_type = "image" if content_type.startswith("image/") else "video"
        media = Media(
            owner_id=owner_id,
            owner_type=owner_type,
            filename=filename,
            media_type=media_type,
            file_type=content_type,
            file_size=file_size,
            storage_key=storage_key,
        )

        try:
            self.session.add(media)
            self.session.commit()
            self.session.refresh(media)
            return media
        except IntegrityError as e:
            self.session.rollback()
            log.warning("Database integrity error", extra={"error": str(e)})
            raise InvalidMediaError("Duplicate media entry or invalid owner") from e
        except DataError as e:
            self.session.rollback()
            log.warning("Database data error", extra={"error": str(e)})
            raise InvalidMediaError("Invalid data provided") from e
        except Exception as e:
            self.session.rollback()
            log.critical("Unexpected database error", extra={"error": str(e)})
            raise DatabaseError("Failed to save media due to internal error") from e
