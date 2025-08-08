# src/application/product_service.py

from datetime import datetime
from typing import List, Optional
from uuid import UUID
from sqlmodel import Session, select

from src.config.logger_config import log
from src.core.exceptions import (
    ProductNotFoundError,
    ProductAlreadyExistsError,
    InvalidInputError,
    DatabaseError,
)
from src.domain.models import Product, Category
from src.interfaces.http.schemas import ProductCreate, ProductUpdate


class ProductService:
    """
    Service class for handling product-related business logic.
    Encapsulates CRUD operations for products with category association.
    """

    def __init__(self, session: Session):
        """
        Initialize the service with a database session.
        Args:
            session: SQLModel session for database operations.
        """
        self.session = session

    def create_product(self, product_create: ProductCreate) -> Product:
        """
        Create a new product.
        Args:
            product_create: ProductCreate schema with validated data.
        Returns:
            Created Product object.
        Raises:
            ProductAlreadyExistsError: If product with same name exists.
            InvalidInputError: If input data is invalid (e.g., invalid category).
        """
        log.debug("Creating product", name=product_create.name)

        # Check name uniqueness
        existing = self.session.exec(
            select(Product).where(Product.name == product_create.name)
        ).first()
        if existing:
            log.warning("Product with name already exists", name=product_create.name)
            raise ProductAlreadyExistsError(
                f"Product with name '{product_create.name}' already exists"
            )

        # Validate category exists and is active
        if product_create.category_id:
            category = self.session.get(Category, product_create.category_id)
            if not category:
                log.warning(
                    "Category not found", category_id=str(product_create.category_id)
                )
                raise InvalidInputError(
                    f"Category with ID {product_create.category_id} not found"
                )
            if not category.is_active:
                raise InvalidInputError("Cannot assign to an inactive category")

        # Create product
        product = Product(
            name=product_create.name,
            description=product_create.description,
            price=product_create.price,
            stock=product_create.stock,
            category_id=product_create.category_id,
        )

        try:
            self.session.add(product)
            self.session.commit()
            self.session.refresh(product)
            log.info(
                "Product created successfully",
                product_id=str(product.id),
                name=product.name,
            )
            return product

        except Exception as e:
            log.exception(
                "Unexpected error during product creation",
                name=product_create.name,
                error=str(e),
            )
            raise DatabaseError("Failed to create product due to internal error") from e

    def get_product_by_id(self, product_id: UUID) -> Product:
        """
        Retrieve a product by ID.
        Args:
            product_id: UUID of the product to retrieve.
        Returns:
            Product object.
        Raises:
            ProductNotFoundError: If product does not exist or is inactive.
        """
        log.debug("Fetching product by ID", product_id=str(product_id))
        product = self.session.get(Product, product_id)
        if not product:
            log.warning("Product not found", product_id=str(product_id))
            raise ProductNotFoundError(f"Product with ID {product_id} not found")
        if not product.is_active:
            log.warning("Product is inactive", product_id=str(product_id))
            raise ProductNotFoundError(f"Product with ID {product_id} is inactive")
        return product

    def list_products(
        self,
        limit: int = 10,
        offset: int = 0,
        sort: str = "created_at:desc",
        category_id: Optional[UUID] = None,
    ) -> tuple[List[Product], int]:
        """
        List products with pagination, sorting, and optional category filter.
        Args:
            limit: Number of products to return.
            offset: Number of products to skip.
            sort: Sort by field:direction (e.g., name:asc, created_at:desc).
            category_id: Optional filter by category.
        Returns:
            Tuple of (list of products, total count).
        """
        log.debug(
            "Listing products",
            limit=limit,
            offset=offset,
            sort=sort,
            category_id=str(category_id) if category_id else None,
        )

        query = select(Product).where(Product.is_active)

        if category_id:
            query = query.where(Product.category_id == category_id)

        # Parse sort
        sort_field, direction = (
            sort.split(":") if ":" in sort else ("created_at", "desc")
        )
        allowed_sort_fields = ["name", "price", "stock", "created_at", "updated_at"]
        if sort_field not in allowed_sort_fields:
            raise InvalidInputError(f"Invalid sort field: {sort_field}")
        if direction not in ["asc", "desc"]:
            raise InvalidInputError(f"Invalid sort direction: {direction}")

        column = getattr(Product, sort_field)
        if direction == "desc":
            column = column.desc()
        query = query.order_by(column)

        # Get total count
        count_query = query.with_only_columns(Product.id).order_by()
        total = len(self.session.exec(count_query).all())

        # Apply pagination
        query = query.offset(offset).limit(limit)
        products = self.session.exec(query).all()

        log.info("Products listed successfully", count=len(products), total=total)
        return products, total

    def update_product(
        self, product_id: UUID, product_update: ProductUpdate
    ) -> Product:
        """
        Update an existing product.
        Args:
            product_id: UUID of the product to update.
            product_update: ProductUpdate schema with new data.
        Returns:
            Updated Product object.
        Raises:
            ProductNotFoundError: If product does not exist.
            ProductAlreadyExistsError: If new name is taken.
            InvalidInputError: If input data is invalid.
        """
        log.debug(
            "Updating product",
            product_id=str(product_id),
            update_data=product_update.model_dump(exclude_unset=True),
        )

        product = self.get_product_by_id(product_id)
        update_data = product_update.model_dump(exclude_unset=True)

        if not update_data:
            log.debug("No fields to update", product_id=str(product_id))
            return product

        # Handle name update
        if "name" in update_data:
            new_name = update_data["name"]
            if new_name == product.name:
                del update_data["name"]
            else:
                existing = self.session.exec(
                    select(Product).where(Product.name == new_name)
                ).first()
                if existing:
                    log.warning(
                        "Cannot update product: name already exists", new_name=new_name
                    )
                    raise ProductAlreadyExistsError(
                        f"Product with name '{new_name}' already exists"
                    )
                product.name = new_name

        # Handle other fields
        if "description" in update_data:
            product.description = update_data["description"]
        if "price" in update_data:
            product.price = update_data["price"]
        if "stock" in update_data:
            product.stock = update_data["stock"]
        if "category_id" in update_data:
            category_id = update_data["category_id"]
            if category_id:
                category = self.session.get(Category, category_id)
                if not category:
                    raise InvalidInputError(f"Category with ID {category_id} not found")
                if not category.is_active:
                    raise InvalidInputError("Cannot assign to an inactive category")
                product.category_id = category_id

        product.updated_at = datetime.utcnow()

        try:
            self.session.add(product)
            self.session.commit()
            self.session.refresh(product)
            log.info("Product updated successfully", product_id=str(product.id))
            return product
        except Exception as e:
            log.exception(
                "Unexpected error during product update",
                product_id=str(product.id),
                error=str(e),
            )
            raise DatabaseError("Failed to update product due to internal error") from e

    def delete_product(self, product_id: UUID) -> None:
        """
        Soft-delete a product by setting is_active=False.
        Args:
            product_id: UUID of the product to delete.
        Raises:
            ProductNotFoundError: If product does not exist.
        """
        log.info("Soft-deleting product", product_id=str(product_id))
        product = self.get_product_by_id(product_id)
        product.is_active = False
        product.updated_at = datetime.utcnow()
        self.session.add(product)
        self.session.commit()
        log.info("Product soft-deleted", product_id=str(product.id))
