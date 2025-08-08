from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlmodel import Session

from src.application.category_service import CategoryService
from src.config.logger_config import log
from src.core.exceptions import (
    CategoryAlreadyExistsError,
    CategoryNotFoundError,
    InvalidInputError,
)
from src.infrastructure.database.session import get_session
from src.infrastructure.services import jwt_service
from src.interfaces.http.dependencies import require_permission
from src.interfaces.http.schemas import (
    CategoryCreate,
    CategoryListResponse,
    CategoryResponse,
    CategoryUpdate,
)

router = APIRouter(prefix="/categories", tags=["categories"])


@router.post("", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(
    category_create: CategoryCreate,
    session: Session = Depends(get_session),
    current_user_id: UUID = Depends(jwt_service.get_current_user_id),
    _: UUID = Depends(require_permission("create", "category")),
):
    """
    Create a new category.
    - Requires: superadmin OR category:create permission
    - Returns created category
    """
    try:
        log.info(
            "Create category request",
            name=category_create.name,
            parent_id=str(category_create.parent_id)
            if category_create.parent_id
            else None,
            requester_id=str(current_user_id),
        )

        category_service = CategoryService(session=session)
        category = category_service.create_category(category_create)

        return CategoryResponse.model_validate(category)

    except CategoryAlreadyExistsError as e:
        log.warning(
            "Category creation failed: name already exists", name=category_create.name
        )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e

    except InvalidInputError as e:
        log.warning("Category creation failed: invalid input", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e

    except Exception as e:
        log.exception("Unexpected error during category creation", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e


@router.get("/{category_id}", response_model=CategoryResponse)
async def get_category(
    category_id: UUID = Path(..., description="The UUID of the category to retrieve"),
    session: Session = Depends(get_session),
    current_user_id: UUID = Depends(jwt_service.get_current_user_id),
    _: UUID = Depends(require_permission("read", "category")),
):
    """
    Retrieve a category by ID.
    - Requires: superadmin OR category:read permission
    """
    try:
        log.info(
            "Get category request",
            category_id=str(category_id),
            requester_id=str(current_user_id),
        )

        category_service = CategoryService(session=session)
        category = category_service.get_category_by_id(category_id)

        return CategoryResponse.model_validate(category)

    except CategoryNotFoundError as e:
        log.warning("Category not found", category_id=str(category_id))
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e

    except Exception as e:
        log.exception("Unexpected error during get category", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e


@router.get("", response_model=CategoryListResponse)
async def list_categories(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    sort: str = Query(
        "created_at:desc",
        description="Sort by field:direction (e.g., name:asc, created_at:desc)",
    ),
    session: Session = Depends(get_session),
    current_user_id: UUID = Depends(jwt_service.get_current_user_id),
    _: UUID = Depends(require_permission("list", "category")),
):
    """
    List categories with pagination and sorting.
    - Requires: superadmin OR category:list permission
    - Supports sorting, pagination
    - Returns paginated list with meta
    """
    try:
        log.info(
            "List categories request",
            requester_id=str(current_user_id),
            limit=limit,
            offset=offset,
            sort=sort,
        )

        # Validate inputs
        if limit < 1 or limit > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="limit must be between 1 and 100",
            )

        allowed_sort_fields = ["name", "created_at", "updated_at"]
        sort_field, direction = sort.split(":") if ":" in sort else (sort, "asc")
        if sort_field not in allowed_sort_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid sort field: {sort_field}",
            )
        if direction not in ["asc", "desc"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid sort direction: {direction}",
            )

        category_service = CategoryService(session=session)
        categories, total = category_service.list_categories(
            limit=limit, offset=offset, sort=sort
        )

        responses = [CategoryResponse.model_validate(cat) for cat in categories]

        meta = {
            "total": total,
            "limit": limit,
            "offset": offset,
            "pages": (total + limit - 1) // limit,
        }

        log.info("Categories listed successfully", count=len(responses), total=total)
        return CategoryListResponse(categories=responses, meta=meta)

    except HTTPException:
        raise

    except Exception as e:
        log.exception("Unexpected error during list categories", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e


@router.patch("/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_update: CategoryUpdate,
    category_id: UUID = Path(..., description="The UUID of the category to update"),
    session: Session = Depends(get_session),
    current_user_id: UUID = Depends(jwt_service.get_current_user_id),
    _: UUID = Depends(require_permission("update", "category")),
):
    """
    Update an existing category.
    - Requires: superadmin OR category:update permission
    - Returns updated category
    """
    try:
        log.info(
            "Update category request",
            category_id=str(category_id),
            update_data=category_update.model_dump(exclude_unset=True),
            requester_id=str(current_user_id),
        )

        category_service = CategoryService(session=session)
        category = category_service.update_category(category_id, category_update)

        return CategoryResponse.model_validate(category)

    except CategoryNotFoundError as e:
        log.warning("Category not found", category_id=str(category_id))
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e

    except CategoryAlreadyExistsError as e:
        log.warning("Category update failed: name already exists", error=str(e))
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e

    except InvalidInputError as e:
        log.warning("Category update failed: invalid input", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e

    except Exception as e:
        log.exception("Unexpected error during category update", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: UUID = Path(..., description="The UUID of the category to delete"),
    session: Session = Depends(get_session),
    current_user_id: UUID = Depends(jwt_service.get_current_user_id),
    _: UUID = Depends(require_permission("delete", "category")),
):
    """
    Soft-delete a category by setting is_active=False.
    - Requires: superadmin OR category:delete permission
    - Returns 204 No Content
    """
    try:
        log.info(
            "Delete category request",
            category_id=str(category_id),
            requester_id=str(current_user_id),
        )

        category_service = CategoryService(session=session)
        category_service.delete_category(category_id)

    except CategoryNotFoundError as e:
        log.warning("Category not found", category_id=str(category_id))
        raise HTTPException(status_code=status.HTTP_404, detail=str(e)) from e
