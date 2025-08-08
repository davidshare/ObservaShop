from datetime import datetime
from typing import List
from uuid import UUID
from sqlmodel import Session, select

from src.config.logger_config import log
from src.core.exceptions import (
    CategoryAlreadyExistsError,
    CategoryNotFoundError,
    InvalidInputError,
    DatabaseError,
)
from src.domain.models import Category
from src.interfaces.http.schemas import CategoryCreate, CategoryUpdate


class CategoryService:
    """
    Service class for handling category-related business logic.
    Encapsulates CRUD operations for categories with hierarchical support.
    """

    def __init__(self, session: Session):
        """
        Initialize the service with a database session.
        Args:
            session: SQLModel session for database operations.
        """
        self.session = session

    def create_category(self, category_create: CategoryCreate) -> Category:
        """
        Create a new category.
        Args:
            category_create: CategoryCreate schema with new data.
        Returns:
            Created Category object.
        Raises:
            CategoryAlreadyExistsError: If category with same name exists.
            InvalidInputError: If input data is invalid.
        """
        log.debug("Creating category", name=category_create.name)

        if not category_create.name or not category_create.name.strip():
            raise InvalidInputError("Category name is required and cannot be empty")

        name = category_create.name.strip()
        description = (
            category_create.description.strip() if category_create.description else None
        )
        parent_id = category_create.parent_id

        # Check name uniqueness
        existing = self.session.exec(
            select(Category).where(Category.name == name)
        ).first()
        if existing:
            log.warning("Category with name already exists", name=name)
            raise CategoryAlreadyExistsError(
                f"Category with name '{name}' already exists"
            )

        # Validate parent exists
        if parent_id:
            parent = self.session.get(Category, parent_id)
            if not parent:
                log.warning("Parent category not found", parent_id=str(parent_id))
                raise CategoryNotFoundError(
                    f"Parent category with ID {parent_id} not found"
                )
            if not parent.is_active:
                raise InvalidInputError("Cannot assign to an inactive parent category")

            # Prevent cycle
            if self._has_cycle(parent, parent_id):
                raise InvalidInputError("Category hierarchy cycle detected")

        # Create category
        category = Category(name=name, description=description, parent_id=parent_id)
        try:
            self.session.add(category)
            self.session.commit()
            self.session.refresh(category)
            log.info(
                "Category created successfully",
                category_id=str(category.id),
                name=category.name,
            )
            return category
        except Exception as e:
            log.exception(
                "Unexpected error during category creation",
                name=name,
                parent_id=str(parent_id),
                error=str(e),
                exc_info=True,
            )
            raise DatabaseError(
                "Failed to create category due to internal error"
            ) from e

    def get_category_by_id(self, category_id: UUID) -> Category:
        """
        Retrieve a category by ID.
        Args:
            category_id: UUID of the category to retrieve.
        Returns:
            Category object.
        Raises:
            CategoryNotFoundError: If category does not exist or is inactive.
        """
        log.debug("Fetching category by ID", category_id=str(category_id))
        category = self.session.get(Category, category_id)
        if not category:
            log.warning("Category not found", category_id=str(category_id))
            raise CategoryNotFoundError(f"Category with ID {category_id} not found")
        if not category.is_active:
            log.warning("Category is inactive", category_id=str(category_id))
            raise CategoryNotFoundError(f"Category with ID {category_id} is inactive")
        return category

    def list_categories(
        self, limit: int = 10, offset: int = 0, sort: str = "created_at:desc"
    ) -> tuple[List[Category], int]:
        """
        List categories with pagination and sorting.
        Args:
            limit: Number of categories to return.
            offset: Number of categories to skip.
            sort: Sort by field:direction (e.g., name:asc, created_at:desc).
        Returns:
            Tuple of (list of categories, total count).
        """
        log.debug("Listing categories", limit=limit, offset=offset, sort=sort)

        query = select(Category).where(Category.is_active)

        # Parse sort
        sort_field, direction = (
            sort.split(":") if ":" in sort else ("created_at", "desc")
        )
        allowed_sort_fields = ["name", "created_at", "updated_at"]
        if sort_field not in allowed_sort_fields:
            raise InvalidInputError(f"Invalid sort field: {sort_field}")
        if direction not in ["asc", "desc"]:
            raise InvalidInputError(f"Invalid sort direction: {direction}")

        column = getattr(Category, sort_field)
        if direction == "desc":
            column = column.desc()
        query = query.order_by(column)

        # Get total count
        count_query = query.with_only_columns(Category.id).order_by()
        total = len(self.session.exec(count_query).all())

        # Apply pagination
        query = query.offset(offset).limit(limit)
        categories = self.session.exec(query).all()

        log.info("Categories listed successfully", count=len(categories), total=total)
        return categories, total

    def update_category(
        self, category_id: UUID, category_update: CategoryUpdate
    ) -> Category:
        """
        Update an existing category.
        Args:
            category_id: UUID of the category to update.
            category_update: CategoryUpdate schema with new data.
        Returns:
            Updated Category object.
        Raises:
            CategoryNotFoundError: If category does not exist.
            CategoryAlreadyExistsError: If new name is taken.
            InvalidInputError: If input data is invalid (e.g., cycle in hierarchy).
        """
        log.debug(
            "Updating category",
            category_id=str(category_id),
            update_data=category_update.model_dump(exclude_unset=True),
        )

        # Retrieve the category to update
        category = self.get_category_by_id(category_id)

        # Get only the fields that were provided
        update_data = category_update.model_dump(exclude_unset=True)

        # If no fields were provided, return early
        if not update_data:
            log.debug("No fields to update", category_id=str(category_id))
            return category

        # Handle name update
        if "name" in update_data:
            new_name = update_data["name"].strip()
            if new_name == category.name:
                # No change, skip
                del update_data["name"]
            else:
                # Check for duplicate name
                existing = self.session.exec(
                    select(Category).where(Category.name == new_name)
                ).first()
                if existing:
                    log.warning(
                        "Cannot update category: name already exists", new_name=new_name
                    )
                    raise CategoryAlreadyExistsError(
                        f"Category with name '{new_name}' already exists"
                    )
                category.name = new_name

        # Handle description update
        if "description" in update_data:
            category.description = (
                update_data["description"].strip()
                if update_data["description"]
                else None
            )

        # Handle parent_id update
        if "parent_id" in update_data:
            parent_id = update_data["parent_id"]

            # Clear parent (allow setting to None)
            if parent_id is None:
                category.parent_id = None
            else:
                # Validate parent exists
                parent = self.session.get(Category, parent_id)
                if not parent:
                    log.warning("Parent category not found", parent_id=str(parent_id))
                    raise CategoryNotFoundError(
                        f"Parent category with ID {parent_id} not found"
                    )
                if not parent.is_active:
                    raise InvalidInputError(
                        "Cannot assign to an inactive parent category"
                    )

                # PREVENT CYCLE: Ensure the new parent does not create a cycle
                if self._has_cycle(parent, category_id):
                    log.warning(
                        "Cycle detected in category hierarchy",
                        category_id=str(category_id),
                        parent_id=str(parent_id),
                    )
                    raise InvalidInputError("Category hierarchy cycle detected")

                category.parent_id = parent_id

        # Update timestamp
        category.updated_at = datetime.utcnow()

        try:
            self.session.add(category)
            self.session.commit()
            self.session.refresh(category)
            log.info("Category updated successfully", category_id=str(category.id))
            return category

        except Exception as e:
            log.exception(
                "Unexpected error during category update",
                category_id=str(category.id),
                error=str(e),
                exc_info=True,
            )
            raise DatabaseError(
                "Failed to update category due to internal error"
            ) from e

    def delete_category(self, category_id: UUID) -> None:
        """
        Soft-delete a category by setting is_active=False.
        Args:
            category_id: UUID of the category to delete.
        Raises:
            CategoryNotFoundError: If category does not exist.
        """
        log.info("Soft-deleting category", category_id=str(category_id))
        category = self.get_category_by_id(category_id)
        category.is_active = False
        category.updated_at = datetime.utcnow()
        self.session.add(category)
        self.session.commit()
        log.info("Category soft-deleted", category_id=str(category.id))

    def _has_cycle(self, parent: Category, target_id: UUID) -> bool:
        """
        Check if adding a parent would create a cycle in the hierarchy.
        """
        current = parent
        while current:
            if current.id == target_id:
                return True
            current = current.parent
        return False
