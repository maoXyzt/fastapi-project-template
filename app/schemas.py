from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, computed_field
from pydantic.types import NonNegativeInt, PositiveInt


class BaseSchema(BaseModel):
    model_config: ConfigDict = ConfigDict(  # pyright: ignore[reportIncompatibleVariableOverride]
        validate_assignment=True,
        extra="ignore",
    )


class RequestBase(BaseSchema):
    """Base model for request params."""

    pass


TData = TypeVar(
    "TData",
    bound=dict[int | float | str, Any] | BaseSchema | tuple[Any, ...] | list[Any] | str | None,
)


class ResponseBase(BaseSchema, Generic[TData]):
    """Base model for response data."""

    code: int = 0
    msg: str = "OK"
    data: TData


TItems = TypeVar("TItems")


class PageData(BaseSchema, Generic[TItems]):
    items: list[TItems]
    page: PositiveInt
    page_size: PositiveInt
    item_count: NonNegativeInt

    @computed_field
    @property
    def page_count(self) -> NonNegativeInt:
        return (self.item_count - 1) // self.page_size + 1


class PaginationMixin:
    page: PositiveInt = 1
    page_size: PositiveInt = 20

    def get_offset(self) -> NonNegativeInt:
        """Get the offset based on the page and page_size.

        Returns
        -------
        NonNegativeInt
            The offset value.
        """
        return (self.page - 1) * self.page_size
