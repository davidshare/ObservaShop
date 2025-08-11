from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query, status
from sqlmodel import Session

from src.application.payment_service import PaymentService
from src.config.config import config
from src.config.logger_config import log
from src.core.exceptions import (
    DatabaseError,
    ExternalServiceError,
    IdempotencyError,
    InvalidInputError,
    PaymentAlreadyExistsError,
    PaymentNotFoundError,
    PaymentProcessingError,
)
from src.infrastructure.clients.order_client import OrderClient
from src.infrastructure.database.session import get_session
from src.infrastructure.services import jwt_service
from src.interfaces.http.dependencies import require_permission
from src.interfaces.http.schemas import (
    PaymentCreate,
    PaymentListResponse,
    PaymentResponse,
    PaymentUpdate,
)

router = APIRouter(prefix="/payments", tags=["payments"])


def get_order_client() -> OrderClient:
    """Dependency to get OrderClient."""

    return OrderClient(base_url=config.ORDER_SERVICE_URL)


@router.post("", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def create_payment(
    payment_create: PaymentCreate,
    idempotency_key: str = Header(
        None, description="Idempotency key to prevent duplicate payments"
    ),
    session: Session = Depends(get_session),
    current_user_id_and_token: tuple[UUID, str] = Depends(
        jwt_service.get_current_user_id
    ),
    _: UUID = Depends(require_permission("create", "payment")),
    order_client: OrderClient = Depends(get_order_client),
):
    """
    Create a new payment.
    - Requires: superadmin OR payment:create permission
    - Uses idempotency key to prevent duplicates
    - Validates order status via order-service
    - Returns created payment
    """
    user_id, jwt_token = current_user_id_and_token

    try:
        log.info(
            "Create payment request",
            order_id=str(payment_create.order_id),
            amount=str(payment_create.amount),
            user_id=str(user_id),
            idempotency_key=idempotency_key,
        )

        payment_service = PaymentService(session=session, order_client=order_client)
        payment = await payment_service.create_payment(
            payment_create, idempotency_key, jwt_token
        )

        return PaymentResponse.model_validate(payment)

    except IdempotencyError as e:
        log.warning("Idempotency error", idempotency_key=idempotency_key)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e

    except PaymentAlreadyExistsError as e:
        log.warning(
            "Payment already exists for order", order_id=str(payment_create.order_id)
        )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e

    except InvalidInputError as e:
        log.warning("Invalid input in payment creation", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e

    except PaymentProcessingError as e:
        log.warning("Payment processing failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e

    except ExternalServiceError as e:
        log.critical(
            "External service error during payment creation",
            service=e.service_name,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Service unavailable: {e.service_name}",
        ) from e

    except DatabaseError as e:
        log.critical("Database error during payment creation", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create payment due to internal error",
        ) from e

    except Exception as e:
        log.critical(
            "Unexpected error during payment creation", error=str(e), exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e


@router.get("/{payment_id}", response_model=PaymentResponse)
async def get_payment(
    payment_id: UUID = Path(..., description="The UUID of the payment to retrieve"),
    session: Session = Depends(get_session),
    user_id_and_claims: tuple[UUID, dict] = Depends(
        jwt_service.get_current_user_id_with_claims
    ),
    _: UUID = Depends(require_permission("read", "payment")),
    order_client: OrderClient = Depends(get_order_client),
):
    """
    Retrieve a payment by ID.
    - Requires: superadmin OR payment:read permission
    - Returns full payment details
    """
    user_id, claims = user_id_and_claims
    is_superadmin = claims.get("is_superadmin", False)
    permissions = set(claims.get("permissions", []))

    try:
        log.info(
            "Get payment request", payment_id=str(payment_id), user_id=str(user_id)
        )

        payment_service = PaymentService(session=session, order_client=order_client)
        payment = await payment_service.get_payment_by_id(
            payment_id=payment_id,
            user_id=user_id,
            permissions=permissions,
            is_superadmin=is_superadmin,
        )

        return PaymentResponse.model_validate(payment)

    except PaymentNotFoundError as e:
        log.warning("Payment not found", payment_id=str(payment_id))
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e

    except DatabaseError as e:
        log.critical("Database error during get payment", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve payment due to internal error",
        ) from e

    except Exception as e:
        log.critical("Unexpected error during get payment", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e


@router.get("", response_model=PaymentListResponse)
async def list_payments(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    sort: str = Query("created_at:desc", description="Sort by field:direction"),
    status: Optional[str] = Query(None, description="Filter by payment status"),
    order_id: Optional[UUID] = Query(None, description="Filter by order ID"),
    session: Session = Depends(get_session),
    user_id_and_claims: tuple[UUID, dict] = Depends(
        jwt_service.get_current_user_id_with_claims
    ),
    _: UUID = Depends(require_permission("list", "payment")),
    order_client: OrderClient = Depends(get_order_client),
):
    """
    List payments with pagination and filtering.
    - Requires: superadmin OR payment:list permission
    - Returns paginated list with meta
    """
    user_id, claims = user_id_and_claims
    is_superadmin = claims.get("is_superadmin", False)
    permissions = set(claims.get("permissions", []))

    try:
        log.info(
            "List payments request",
            user_id=str(user_id),
            limit=limit,
            offset=offset,
            status=status,
            order_id=str(order_id) if order_id else None,
        )

        payment_service = PaymentService(session=session, order_client=order_client)
        payments, total = payment_service.list_payments(
            user_id=user_id,
            permissions=permissions,
            is_superadmin=is_superadmin,
            limit=limit,
            offset=offset,
            sort=sort,
            status=status,
            order_id=order_id,
        )

        responses = [PaymentResponse.model_validate(p) for p in payments]
        meta = {
            "total": total,
            "limit": limit,
            "offset": offset,
            "pages": (total + limit - 1) // limit,
        }

        log.info("Payments listed successfully", count=len(responses), total=total)
        return PaymentListResponse(payments=responses, meta=meta)

    except InvalidInputError as e:
        log.warning("Invalid input in list payments", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e

    except Exception as e:
        log.critical(
            "Unexpected error during list payments", error=str(e), exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e


@router.patch("/{payment_id}", response_model=PaymentResponse)
async def update_payment_status(
    payment_update: PaymentUpdate,
    payment_id: UUID = Path(..., description="The UUID of the payment to update"),
    session: Session = Depends(get_session),
    user_id_and_claims: tuple[UUID, dict] = Depends(
        jwt_service.get_current_user_id_with_claims
    ),
    _: UUID = Depends(require_permission("update", "payment")),
    order_client: OrderClient = Depends(get_order_client),
):
    """
    Update the status of an existing payment.
    - Requires: superadmin OR payment:update permission
    - Returns updated payment
    """
    user_id, claims = user_id_and_claims
    is_superadmin = claims.get("is_superadmin", False)
    permissions = set(claims.get("permissions", []))

    try:
        log.info(
            "Update payment status request",
            payment_id=str(payment_id),
            update_data=payment_update.model_dump(exclude_unset=True),
            user_id=str(user_id),
        )

        payment_service = PaymentService(session=session, order_client=order_client)
        payment = await payment_service.update_payment_status(
            payment_id=payment_id,
            payment_update=payment_update,
            user_id=user_id,
            permissions=permissions,
            is_superadmin=is_superadmin,
        )

        return PaymentResponse.model_validate(payment)

    except PaymentNotFoundError as e:
        log.warning("Payment not found", payment_id=str(payment_id))
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e

    except InvalidInputError as e:
        log.warning("Invalid input in update payment", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e

    except Exception as e:
        log.critical(
            "Unexpected error during payment update", error=str(e), exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e


@router.post("/{payment_id}/refund", response_model=PaymentResponse)
async def refund_payment(
    payment_id: UUID = Path(..., description="The UUID of the payment to refund"),
    session: Session = Depends(get_session),
    user_id_and_claims: tuple[UUID, dict] = Depends(
        jwt_service.get_current_user_id_with_claims
    ),
    _: UUID = Depends(require_permission("refund", "payment")),
    order_client: OrderClient = Depends(get_order_client),
):
    """
    Refund an existing payment.
    - Requires: superadmin OR payment:refund permission
    - Returns updated payment
    """
    user_id, claims = user_id_and_claims
    is_superadmin = claims.get("is_superadmin", False)
    permissions = set(claims.get("permissions", []))

    try:
        log.info(
            "Refund payment request", payment_id=str(payment_id), user_id=str(user_id)
        )

        payment_service = PaymentService(session=session, order_client=order_client)
        payment = await payment_service.refund_payment(
            payment_id=payment_id,
            user_id=user_id,
            permissions=permissions,
            is_superadmin=is_superadmin,
        )

        return PaymentResponse.model_validate(payment)

    except PaymentNotFoundError as e:
        log.warning("Payment not found", payment_id=str(payment_id))
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e

    except InvalidInputError as e:
        log.warning("Invalid input in refund payment", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e

    except Exception as e:
        log.critical(
            "Unexpected error during payment refund", error=str(e), exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e
