from datetime import datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints


class Equipment(StrEnum):
    dry_van = "dry_van"
    refrigerated = "refrigerated"
    flatbed = "flatbed"


class Status(StrEnum):
    available = "available"
    booked = "booked"
    delivered = "delivered"


TEXT_PATTERN = r"^[^\x00]*$"
Location = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120, pattern=TEXT_PATTERN)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000, pattern=TEXT_PATTERN)]


class ListingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    origin: Location
    destination: Location
    cargo_description: Description
    equipment_type: Equipment
    status: Status


class Listing(ListingInput):
    id: UUID
    created_at: datetime
    updated_at: datetime


class SearchResults(BaseModel):
    items: list[Listing]
