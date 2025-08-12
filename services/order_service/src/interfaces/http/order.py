from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlmodel import Session

from src.application.order_service import OrderService
from src.config.config import config
from src.config.logger_config import log
from src.core.exceptions import (
    ExternalServiceError,
    InsufficientStockError,
    InvalidInputError,
    OrderCancellationError,
    OrderNotFoundError,
    PaymentProcessingError,
    ProductUnavailableError,
    OrderStatusTransitionError,
)
from src.infrastructure.clients.payment_client import PaymentClient
from src.infrastructure.clients.product_client import ProductClient
from src.infrastructure.database.session import get_session
from src.infrastructure.services import jwt_service
from src.interfaces.http.dependencies import require_permission
from src.interfaces.http.schemas import (
    OrderCreate,
    OrderListResponse,
    OrderResponse,
    OrderUpdate,
)

router = APIRouter(prefix="/orders", tags=["orders"])


def get_product_client() -> ProductClient:
    """Dependency to get ProductClient."""
    return ProductClient(base_url=config.PRODUCT_SERVICE_URL)


def get_payment_client() -> PaymentClient:
    """Dependency to get PaymentClient."""
    return PaymentClient(base_url=config.PAYMENT_SERVICE_URL)


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    order_create: OrderCreate,
    session: Session = Depends(get_session),
    current_user_id_and_token: tuple[UUID, str] = Depends(
        jwt_service.get_current_user_id
    ),
    _: UUID = Depends(require_permission("create", "order")),
    product_client: ProductClient = Depends(get_product_client),
    payment_client: PaymentClient = Depends(get_payment_client),
):
    """
    Create a new order.
    - Requires: superadmin OR order:create permission
    - Returns created order with items
    - On success: returns 201 Created
    """
    current_user_id, jwt_token = current_user_id_and_token

    try:
        log.info(
            "Create order request",
            user_id=str(current_user_id),
            item_count=len(order_create.items),
            requester_id=str(current_user_id),
        )

        order_service = OrderService(
            session=session,
            product_client=product_client,
            payment_client=payment_client,
        )
        order = await order_service.create_order(
            current_user_id, order_create, jwt_token
        )

        return OrderResponse.model_validate(order)

    except InvalidInputError as e:
        log.warning("Order creation failed: invalid input", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e

    except ProductUnavailableError as e:
        log.warning("Order creation failed: product unavailable", error=str(e))
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e

    except InsufficientStockError as e:
        log.warning("Order creation failed: insufficient stock", error=str(e))
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e

    except ExternalServiceError as e:
        log.exception("Order creation failed: external service error", error=str(e))
        # Map to 502 Bad Gateway for downstream failures
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Service unavailable: {e.service_name}",
        ) from e

    except PaymentProcessingError as e:
        log.warning("Order creation failed: payment processing error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e

    except Exception as e:
        log.exception("Unexpected error during order creation")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: UUID = Path(..., description="The UUID of the order to retrieve"),
    session: Session = Depends(get_session),
    user_id_and_claims: tuple[UUID, dict] = Depends(
        jwt_service.get_current_user_id_with_claims
    ),
    _: UUID = Depends(require_permission("read", "order")),
    product_client: ProductClient = Depends(get_product_client),
):
    """
    Retrieve an order by ID.
    - Requires: superadmin OR order:read permission
    - Returns full order with items
    """
    current_user_id, claims = user_id_and_claims

    is_superadmin = claims.get("is_superadmin", False)
    permissions = set(claims.get("permissions", []))

    try:
        log.info(
            "Get order request",
            order_id=str(order_id),
            requester_id=str(current_user_id),
        )

        order_service = OrderService(
            session=session, product_client=product_client, payment_client=None
        )
        order = order_service.get_order_by_id(
            order_id, current_user_id, permissions, is_superadmin
        )

        return OrderResponse.model_validate(order)

    except OrderNotFoundError as e:
        log.warning("Order not found", order_id=str(order_id))
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e

    except Exception as e:
        log.exception("Unexpected error during get order")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e


@router.get("", response_model=OrderListResponse)
async def list_orders(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    sort: str = Query(
        "created_at:desc", description="Sort by field:direction (e.g., created_at:desc)"
    ),
    order_status: Optional[str] = Query(
        None,
        description="Filter by order status (pending, confirmed, shipped, delivered, cancelled)",
    ),
    session: Session = Depends(get_session),
    user_id_and_claims: tuple[UUID, dict] = Depends(
        jwt_service.get_current_user_id_with_claims
    ),
    _: UUID = Depends(require_permission("list", "order")),
    product_client: ProductClient = Depends(get_product_client),
):
    """
    List orders for the current user with pagination and filtering.
    - Requires: superadmin OR order:list permission
    - Returns paginated list with meta
    """
    current_user_id, claims = user_id_and_claims
    is_superadmin = claims.get("is_superadmin", False)
    permissions = set(claims.get("permissions", []))

    try:
        log.info(
            "List orders request",
            requester_id=str(current_user_id),
            limit=limit,
            offset=offset,
            sort=sort,
            status=order_status,
        )

        if limit < 1 or limit > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="limit must be between 1 and 100",
            )

        allowed_sort_fields = ["created_at", "updated_at", "total_amount", "status"]
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

        order_service = OrderService(
            session=session, product_client=product_client, payment_client=None
        )
        orders, total = order_service.list_orders(
            user_id=current_user_id,
            permissions=permissions,
            is_superadmin=is_superadmin,
            limit=limit,
            offset=offset,
            sort=sort,
            status=order_status,
        )

        responses = [OrderResponse.model_validate(o) for o in orders]

        meta = {
            "total": total,
            "limit": limit,
            "offset": offset,
            "pages": (total + limit - 1) // limit,
        }

        log.info("Orders listed successfully", count=len(responses), total=total)
        return OrderListResponse(orders=responses, meta=meta)

    except HTTPException:
        raise

    except Exception as e:
        log.exception("Unexpected error during list orders")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e


@router.patch("/{order_id}", response_model=OrderResponse)
async def update_order_status(
    order_update: OrderUpdate,
    order_id: UUID = Path(..., description="The UUID of the order to update"),
    session: Session = Depends(get_session),
    user_id_and_claims: tuple[UUID, dict] = Depends(
        jwt_service.get_current_user_id_with_claims
    ),
    user_id_and_token: tuple[UUID, str] = Depends(jwt_service.get_current_user_id),
    _: UUID = Depends(require_permission("update", "order")),
    claims: dict = Depends(jwt_service.get_current_user_id_with_claims),
    product_client: ProductClient = Depends(get_product_client),
    payment_client: PaymentClient = Depends(get_payment_client),
):
    """
    Update the status of an existing order.
    - Requires: superadmin OR order:update permission
    - Only allowed transitions are permitted (e.g., pending → confirmed)
    - Payment is processed if status is set to 'confirmed'
    - Returns updated order
    """
    current_user_id, claims = user_id_and_claims
    is_superadmin = claims.get("is_superadmin", False)
    permissions = set(claims.get("permissions", []))
    _, raw_token = user_id_and_token


    try:
        log.info(
            "Update order status request",
            order_id=str(order_id),
            update_data=order_update.model_dump(exclude_unset=True),
            requester_id=str(current_user_id),
        )

        # Validate input
        update_data = order_update.model_dump(exclude_unset=True)
        if "status" not in update_data:
            log.warning(
                "Order status update failed: no status provided", order_id=str(order_id)
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Field 'status' is required for order update",
            )

        # Initialize service
        order_service = OrderService(
            session=session,
            product_client=product_client,
            payment_client=payment_client,
        )

        # Perform update
        order = await order_service.update_order_status(
            order_id,
            order_update,
            current_user_id,
            permissions=permissions,
            is_superadmin=is_superadmin,
            jwt_token=raw_token,
        )

        return OrderResponse.model_validate(order)

    except OrderNotFoundError as e:
        log.warning("Order not found", order_id=str(order_id))
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e

    except OrderStatusTransitionError as e:
        log.warning("Order status update failed: invalid transition", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e

    except InsufficientStockError as e:
        log.warning("Order status update failed: insufficient stock", error=str(e))
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e

    except PaymentProcessingError as e:
        log.warning(
            "Order status update failed: payment processing error", error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e

    except ExternalServiceError as e:
        log.exception(
            "Order status update failed: external service error", error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Service unavailable: {e.service_name}",
        ) from e

    except Exception as e:
        log.exception("Unexpected error during order status update")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e


@router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_order(
    order_id: UUID = Path(..., description="The UUID of the order to cancel"),
    session: Session = Depends(get_session),
    user_id_and_claims: tuple[UUID, dict] = Depends(
        jwt_service.get_current_user_id_with_claims
    ),
    _: UUID = Depends(require_permission("cancel", "order")),
    product_client: ProductClient = Depends(get_product_client),
    payment_client: PaymentClient = Depends(get_payment_client),
):
    """
    Cancel an existing order.
    - Requires: superadmin OR order:cancel permission
    - Only allowed if order is in 'pending' or 'confirmed' status
    - Returns 204 No Content
    """
    current_user_id, claims = user_id_and_claims
    is_superadmin = claims.get("is_superadmin", False)
    permissions = set(claims.get("permissions", []))

    try:
        log.info(
            "Cancel order request",
            order_id=str(order_id),
            requester_id=str(current_user_id),
        )

        order_service = OrderService(
            session=session,
            product_client=product_client,
            payment_client=payment_client,
        )
        await order_service.cancel_order(
            order_id,
            current_user_id,
            permissions=permissions,
            is_superadmin=is_superadmin,
        )

    except OrderNotFoundError as e:
        log.warning("Order not found", order_id=str(order_id))
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e

    except OrderCancellationError as e:
        log.warning("Order cancellation failed: invalid status", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e

    except Exception as e:
        log.exception("Unexpected error during order cancellation")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e
