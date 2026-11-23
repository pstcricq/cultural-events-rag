"""The filters of a search: the constraints of a question (period, district,
venue, free entry), applied to the metadata of the index before any ranking."""

from datetime import date

from pydantic import BaseModel, Field


class SearchFilters(BaseModel):
    """The constraints of a question, as the analysis read them."""

    date_from: date | None = Field(default=None, description="First day.")
    date_to: date | None = Field(default=None, description="Last day.")
    district: str | None = Field(default=None, description="A known district.")
    venue: str | None = Field(default=None, description="A venue, or part of it.")
    free: bool | None = Field(default=None, description="Only free events.")

    def from_today(self, today: date) -> "SearchFilters":
        """Return the filters starting from ``today`` when they have no period,
        or one that ends after today."""
        if self.date_from is None and (self.date_to is None or self.date_to >= today):
            return self.model_copy(update={"date_from": today})
        return self

    def describe(self) -> str:
        """Return a line describing the filters for the logs and reports, such
        as "dates: 2026-10-17 to 2026-10-18, venue: ABC"."""
        parts = []
        if self.date_from or self.date_to:
            parts.append(f"dates: {self.date_from or '...'} to {self.date_to or '...'}")
        if self.district:
            parts.append(f"district: {self.district}")
        if self.venue:
            parts.append(f"venue: {self.venue}")
        if self.free:
            parts.append("free")
        return ", ".join(parts) or "none"
