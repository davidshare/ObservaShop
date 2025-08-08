from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlmodel import Session

from src.application.product_service import ProductService
from src.config.logger_config import log
from src.core.exceptions import (
    InvalidInputError,
    ProductAlreadyExistsError,
    ProductNotFoundError,
)
from src.infrastructure.database.session import get_session
from src.infrastructure.services import jwt_service
from src.interfaces.http.dependencies import require_permission
from src.interfaces.http.schemas import (
    ProductCreate,
    ProductListResponse,
    ProductResponse,
    ProductUpdate,
)

router = APIRouter(prefix="/products", tags=["products"])


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    product_create: ProductCreate,
    session: Session = Depends(get_session),
    current_user_id: UUID = Depends(jwt_service.get_current_user_id),
    _: UUID = Depends(require_permission("create", "product")),
):
    """
    Create a new product.
    - Requires: superadmin OR product:create permission
    - Returns created product
    """
    try:
        log.info(
            "Create product request",
            name=product_create.name,
            category_id=str(product_create.category_id),
            requester_id=str(current_user_id),
        )

        product_service = ProductService(session=session)
        product = product_service.create_product(product_create)

        return ProductResponse.model_validate(product)

    except ProductAlreadyExistsError as e:
        log.warning(
            "Product creation failed: name already exists", name=product_create.name
        )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e

    except InvalidInputError as e:
        log.warning("Product creation failed: invalid input", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e

    except Exception as e:
        log.exception("Unexpected error during product creation")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: UUID = Path(..., description="The UUID of the product to retrieve"),
    session: Session = Depends(get_session),
    current_user_id: UUID = Depends(jwt_service.get_current_user_id),
    _: UUID = Depends(require_permission("read", "product")),
):
    """
    Retrieve a product by ID.
    - Requires: superadmin OR product:read permission
    """
    try:
        log.info(
            "Get product request",
            product_id=str(product_id),
            requester_id=str(current_user_id),
        )

        product_service = ProductService(session=session)
        product = product_service.get_product_by_id(product_id)

        return ProductResponse.model_validate(product)

    except ProductNotFoundError as e:
        log.warning("Product not found", product_id=str(product_id))
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e

    except Exception as e:
        log.exception("Unexpected error during get product")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e


@router.get("", response_model=ProductListResponse)
async def list_products(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    sort: str = Query(
        "created_at:desc",
        description="Sort by field:direction (e.g., name:asc, created_at:desc)",
    ),
    category_id: Optional[UUID] = Query(None, description="Filter by category ID"),
    session: Session = Depends(get_session),
    current_user_id: UUID = Depends(jwt_service.get_current_user_id),
    _: UUID = Depends(require_permission("list", "product")),
):
    """
    List products with pagination, sorting, and optional category filter.
    - Requires: superadmin OR product:list permission
    - Returns paginated list with meta
    """
    try:
        log.info(
            "List products request",
            requester_id=str(current_user_id),
            limit=limit,
            offset=offset,
            sort=sort,
            category_id=str(category_id) if category_id else None,
        )

        # Validate inputs
        if limit < 1 or limit > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="limit must be between 1 and 100",
            )

        allowed_sort_fields = ["name", "price", "stock", "created_at", "updated_at"]
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

        product_service = ProductService(session=session)
        products, total = product_service.list_products(
            limit=limit, offset=offset, sort=sort, category_id=category_id
        )

        responses = [ProductResponse.model_validate(p) for p in products]

        meta = {
            "total": total,
            "limit": limit,
            "offset": offset,
            "pages": (total + limit - 1) // limit,
        }

        log.info("Products listed successfully", count=len(responses), total=total)
        return ProductListResponse(products=responses, meta=meta)

    except HTTPException:
        raise

    except Exception as e:
        log.exception("Unexpected error during list products")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e


@router.patch("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_update: ProductUpdate,
    product_id: UUID = Path(..., description="The UUID of the product to update"),
    session: Session = Depends(get_session),
    current_user_id: UUID = Depends(jwt_service.get_current_user_id),
    _: UUID = Depends(require_permission("update", "product")),
):
    """
    Update an existing product.
    - Requires: superadmin OR product:update permission
    - Returns updated product
    """
    try:
        log.info(
            "Update product request",
            product_id=str(product_id),
            update_data=product_update.model_dump(exclude_unset=True),
            requester_id=str(current_user_id),
        )

        product_service = ProductService(session=session)
        product = product_service.update_product(product_id, product_update)

        return ProductResponse.model_validate(product)

    except ProductNotFoundError as e:
        log.warning("Product not found", product_id=str(product_id))
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e

    except ProductAlreadyExistsError as e:
        log.warning("Product update failed: name already exists", error=str(e))
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e

    except InvalidInputError as e:
        log.warning("Product update failed: invalid input", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e

    except Exception as e:
        log.exception("Unexpected error during product update")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: UUID = Path(..., description="The UUID of the product to delete"),
    session: Session = Depends(get_session),
    current_user_id: UUID = Depends(jwt_service.get_current_user_id),
    _: UUID = Depends(require_permission("delete", "product")),
):
    """
    Soft-delete a product by setting is_active=False.
    - Requires: superadmin OR product:delete permission
    - Returns 204 No Content
    """
    try:
        log.info(
            "Delete product request",
            product_id=str(product_id),
            requester_id=str(current_user_id),
        )

        product_service = ProductService(session=session)
        product_service.delete_product(product_id)

    except ProductNotFoundError as e:
        log.warning("Product not found", product_id=str(product_id))
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e

    except Exception as e:
        log.exception("Unexpected error during product deletion")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e
