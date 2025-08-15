from typing import Optional
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Path,
    Query,
    UploadFile,
    status,
)
from sqlmodel import Session

from src.application.media_service import MediaService
from src.config.logger_config import log
from src.core.exceptions import (
    DatabaseError,
    InvalidMediaError,
    MediaAccessDeniedError,
    MediaDeletionError,
    MediaNotFoundError,
    MediaUploadError,
)
from src.infrastructure.database.session import get_session
from src.infrastructure.services import jwt_service
from src.infrastructure.storage.minio import MinioClient
from src.interfaces.http.dependencies import require_permission
from src.interfaces.http.schemas import (
    MediaListResponse,
    MediaResponse,
    MediaUpdate,
    MediaUploadResponse,
)

router = APIRouter(prefix="/media", tags=["media"])


def get_minio_client() -> MinioClient:
    """Dependency to get MinioClient instance."""
    return MinioClient()


@router.post(
    "/upload", response_model=MediaUploadResponse, status_code=status.HTTP_201_CREATED
)
async def upload_media(
    file: UploadFile = File(..., description="The file to upload"),
    owner_id: UUID = Query(..., description="ID of the owning entity"),
    owner_type: str = Query(
        ..., description="Type of the owning entity (e.g., product, user)"
    ),
    session: Session = Depends(get_session),
    user_id_and_claims: tuple[UUID, dict] = Depends(
        jwt_service.get_current_user_id_with_claims
    ),
    _: UUID = Depends(require_permission("upload", "media")),
    minio_client: MinioClient = Depends(get_minio_client),
):
    """
    Upload a new media file.
    - Requires: superadmin OR media:upload permission
    - Returns created media with presigned URL
    """
    user_id, claims = user_id_and_claims
    is_superadmin = claims.get("is_superadmin", False)
    permissions = set(claims.get("permissions", []))

    log.info(
        "Upload media request",
        filename=file.filename,
        content_type=file.content_type,
        owner_id=str(owner_id),
        owner_type=owner_type,
        user_id=str(user_id),
    )

    try:
        # Read file data
        file_data = await file.read()
        if len(file_data) == 0:
            raise InvalidMediaError("Uploaded file is empty")

        # Initialize service
        media_service = MediaService(session=session, minio_client=minio_client)

        # Upload and get media
        media = media_service.upload_media(
            file_data=file_data,
            filename=file.filename,
            content_type=file.content_type,
            owner_id=owner_id,
            owner_type=owner_type,
            user_id=user_id,
            permissions=permissions,
            is_superadmin=is_superadmin,
        )

        # Generate presigned URL
        url = minio_client.get_presigned_url(media.storage_key)

        return MediaUploadResponse(
            media=MediaResponse(
                id=media.id,
                owner_id=media.owner_id,
                owner_type=media.owner_type,
                filename=media.filename,
                media_type=media.media_type,
                file_type=media.file_type,
                file_size=media.file_size,
                url=url,
                created_at=media.created_at,
            ),
            message="Media uploaded successfully",
        )

    except InvalidMediaError as e:
        log.warning("Invalid media upload", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e

    except MediaAccessDeniedError as e:
        log.warning("Media upload access denied", error=str(e))
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e

    except MediaUploadError as e:
        log.critical("Failed to upload media to storage", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        ) from e

    except DatabaseError as e:
        log.critical("Database error during media upload", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        ) from e

    except Exception as e:
        log.critical(
            "Unexpected error during media upload", error=str(e), exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e


@router.get("/{media_id}", response_model=MediaResponse)
async def get_media(
    media_id: UUID = Path(..., description="The UUID of the media to retrieve"),
    session: Session = Depends(get_session),
    user_id_and_claims: tuple[UUID, dict] = Depends(
        jwt_service.get_current_user_id_with_claims
    ),
    _: UUID = Depends(require_permission("read", "media")),
    minio_client: MinioClient = Depends(get_minio_client),
):
    """
    Retrieve a media asset by ID.
    - Requires: superadmin OR media:read permission
    - Returns media with presigned URL
    """
    user_id, claims = user_id_and_claims
    is_superadmin = claims.get("is_superadmin", False)
    permissions = set(claims.get("permissions", []))

    log.info("Get media request", media_id=str(media_id), user_id=str(user_id))

    try:
        media_service = MediaService(session=session, minio_client=minio_client)
        media = media_service.get_media_by_id(
            media_id=media_id,
            user_id=user_id,
            permissions=permissions,
            is_superadmin=is_superadmin,
        )

        url = minio_client.get_presigned_url(media.storage_key)

        return MediaResponse(
            id=media.id,
            owner_id=media.owner_id,
            owner_type=media.owner_type,
            filename=media.filename,
            media_type=media.media_type,
            file_type=media.file_type,
            file_size=media.file_size,
            url=url,
            created_at=media.created_at,
        )

    except MediaNotFoundError as e:
        log.warning("Media not found", media_id=str(media_id))
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e

    except MediaAccessDeniedError as e:
        log.warning("Media access denied", media_id=str(media_id))
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e

    except Exception as e:
        log.critical("Unexpected error during get media", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e


@router.get("", response_model=MediaListResponse)
async def list_media(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    owner_type: Optional[str] = Query(None, description="Filter by owner type"),
    owner_id: Optional[UUID] = Query(None, description="Filter by owner ID"),
    sort: str = Query("created_at:desc", description="Sort by field:direction"),
    session: Session = Depends(get_session),
    user_id_and_claims: tuple[UUID, dict] = Depends(
        jwt_service.get_current_user_id_with_claims
    ),
    _: UUID = Depends(require_permission("list", "media")),
    minio_client: MinioClient = Depends(get_minio_client),
):
    """
    List media assets with pagination and filtering.
    - Requires: superadmin OR media:list permission
    - Returns paginated list with meta
    """
    user_id, claims = user_id_and_claims
    is_superadmin = claims.get("is_superadmin", False)
    permissions = set(claims.get("permissions", []))

    log.info(
        "List media request",
        user_id=str(user_id),
        limit=limit,
        offset=offset,
        owner_type=owner_type,
        owner_id=str(owner_id) if owner_id else None,
        sort=sort,
    )

    try:
        media_service = MediaService(session=session, minio_client=minio_client)
        media_list, total = media_service.list_media(
            user_id=user_id,
            permissions=permissions,
            is_superadmin=is_superadmin,
            limit=limit,
            offset=offset,
            owner_type=owner_type,
            owner_id=owner_id,
            sort=sort,
        )

        responses = []
        for media in media_list:
            try:
                url = minio_client.get_presigned_url(media.storage_key)
                responses.append(
                    MediaResponse(
                        id=media.id,
                        owner_id=media.owner_id,
                        owner_type=media.owner_type,
                        filename=media.filename,
                        media_type=media.media_type,
                        file_type=media.file_type,
                        file_size=media.file_size,
                        url=url,
                        created_at=media.created_at,
                    )
                )
            except Exception as e:
                log.warning(
                    "Failed to generate presigned URL",
                    media_id=str(media.id),
                    error=str(e),
                )
                continue  # Skip media that can't be accessed

        meta = {
            "total": total,
            "limit": limit,
            "offset": offset,
            "pages": (total + limit - 1) // limit,
        }

        return MediaListResponse(media=responses, meta=meta)

    except Exception as e:
        log.critical("Unexpected error during list media", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e


@router.patch("/{media_id}", response_model=MediaResponse)
async def update_media(
    media_update: MediaUpdate,
    media_id: UUID = Path(..., description="The UUID of the media to update"),
    session: Session = Depends(get_session),
    user_id_and_claims: tuple[UUID, dict] = Depends(
        jwt_service.get_current_user_id_with_claims
    ),
    _: UUID = Depends(require_permission("update", "media")),
    minio_client: MinioClient = Depends(get_minio_client),
):
    """
    Update media metadata (e.g., soft-delete).
    - Requires: superadmin OR media:update permission
    - Returns updated media
    """
    user_id, claims = user_id_and_claims
    is_superadmin = claims.get("is_superadmin", False)
    permissions = set(claims.get("permissions", []))

    log.info(
        "Update media request",
        media_id=str(media_id),
        update_data=media_update.model_dump(exclude_unset=True),
        user_id=str(user_id),
    )

    try:
        media_service = MediaService(session=session, minio_client=minio_client)
        media = media_service.update_media(
            media_id=media_id,
            is_active=media_update.is_active,
            user_id=user_id,
            permissions=permissions,
            is_superadmin=is_superadmin,
        )

        url = minio_client.get_presigned_url(media.storage_key)

        return MediaResponse(
            id=media.id,
            owner_id=media.owner_id,
            owner_type=media.owner_type,
            filename=media.filename,
            media_type=media.media_type,
            file_type=media.file_type,
            file_size=media.file_size,
            url=url,
            created_at=media.created_at,
        )

    except MediaNotFoundError as e:
        log.warning("Media not found", media_id=str(media_id))
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e

    except MediaAccessDeniedError as e:
        log.warning("Media access denied", media_id=str(media_id))
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e

    except Exception as e:
        log.critical(
            "Unexpected error during media update", error=str(e), exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e


@router.delete("/{media_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_media(
    media_id: UUID = Path(..., description="The UUID of the media to delete"),
    session: Session = Depends(get_session),
    user_id_and_claims: tuple[UUID, dict] = Depends(
        jwt_service.get_current_user_id_with_claims
    ),
    _: UUID = Depends(require_permission("delete", "media")),
    minio_client: MinioClient = Depends(get_minio_client),
):
    """
    Delete a media asset (soft-delete + remove from MinIO).
    - Requires: superadmin OR media:delete permission
    - Returns 204 No Content
    """
    user_id, claims = user_id_and_claims
    is_superadmin = claims.get("is_superadmin", False)
    permissions = set(claims.get("permissions", []))

    log.info("Delete media request", media_id=str(media_id), user_id=str(user_id))

    try:
        media_service = MediaService(session=session, minio_client=minio_client)
        media_service.delete_media(
            media_id=media_id,
            user_id=user_id,
            permissions=permissions,
            is_superadmin=is_superadmin,
        )

    except MediaNotFoundError as e:
        log.warning("Media not found", media_id=str(media_id))
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e

    except MediaAccessDeniedError as e:
        log.warning("Media access denied", media_id=str(media_id))
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e

    except MediaDeletionError as e:
        log.critical("Media deletion failed", media_id=str(media_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        ) from e

    except Exception as e:
        log.critical(
            "Unexpected error during media deletion", error=str(e), exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e


@router.patch("/{media_id}/restore", response_model=MediaResponse)
async def restore_media(
    media_id: UUID = Path(...),
    session: Session = Depends(get_session),
    user_id_and_claims: tuple[UUID, dict] = Depends(
        jwt_service.get_current_user_id_with_claims
    ),
    _: UUID = Depends(require_permission("update", "media")),
    minio_client: MinioClient = Depends(get_minio_client),
):
    """
    Restore deleted(soft-delete) file.
    - Requires: superadmin OR media:update permission
    - Returns updated media
    """

    user_id, claims = user_id_and_claims
    is_superadmin = claims.get("is_superadmin", False)
    permissions = set(claims.get("permissions", []))

    try:
        media_service = MediaService(session, minio_client)
        media = media_service.restore_media(
            media_id, user_id, permissions, is_superadmin
        )
        url = minio_client.get_presigned_url(media.storage_key)
        return MediaResponse(
            id=media.id,
            owner_id=media.owner_id,
            owner_type=media.owner_type,
            filename=media.filename,
            media_type=media.media_type,
            file_type=media.file_type,
            file_size=media.file_size,
            url=url,
            created_at=media.created_at,
        )
    except Exception as e:
        log.critical(
            "Unexpected error during media restore", error=str(e), exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e


@router.put("/{media_id}/replace", response_model=MediaResponse)
async def replace_media(
    media_id: UUID = Path(..., description="The UUID of the media to replace"),
    file: UploadFile = File(..., description="The new file to upload"),
    session: Session = Depends(get_session),
    user_id_and_claims: tuple[UUID, dict] = Depends(
        jwt_service.get_current_user_id_with_claims
    ),
    _: UUID = Depends(require_permission("update", "media")),
    minio_client: MinioClient = Depends(get_minio_client),
):
    """
    Replace an existing media asset with a new file.
    - Hard-deletes the old file from MinIO
    - Uploads the new file
    - Updates metadata in DB
    - Requires: superadmin OR media:update permission
    - Returns: Updated MediaResponse with new presigned URL
    """
    user_id, claims = user_id_and_claims
    is_superadmin = claims.get("is_superadmin", False)
    permissions = set(claims.get("permissions", []))

    log.info(
        "Replace media request",
        media_id=str(media_id),
        user_id=str(user_id),
        filename=file.filename,
    )

    try:
        # Read file data
        file_data = await file.read()
        if len(file_data) == 0:
            raise InvalidMediaError("Uploaded file is empty")

        # Initialize service
        media_service = MediaService(session=session, minio_client=minio_client)

        # Replace media
        media = media_service.replace_media(
            media_id=media_id,
            file_data=file_data,
            filename=file.filename,
            content_type=file.content_type,
            user_id=user_id,
            permissions=permissions,
            is_superadmin=is_superadmin,
        )

        # Generate presigned URL for new file
        url = minio_client.get_presigned_url(media.storage_key)

        return MediaResponse(
            id=media.id,
            owner_id=media.owner_id,
            owner_type=media.owner_type,
            filename=media.filename,
            media_type=media.media_type,
            file_type=media.file_type,
            file_size=media.file_size,
            url=url,
            created_at=media.created_at,
        )

    except MediaNotFoundError as e:
        log.warning("Media not found", media_id=str(media_id))
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e

    except MediaAccessDeniedError as e:
        log.warning("Access denied", media_id=str(media_id))
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e

    except InvalidMediaError as e:
        log.warning("Invalid media upload", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e

    except MediaUploadError as e:
        log.critical("Failed to upload replacement file", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        ) from e

    except Exception as e:
        log.critical(
            "Unexpected error during media replacement", error=str(e), exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e
