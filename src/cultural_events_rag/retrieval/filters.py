"""The filters of a search: the constraints a question gives (period, district,
venue, free entry), applied to the metadata of the index before any ranking.

A vector captures a meaning ("en famille", "techno"), not a date ("ce
week-end"), and holds a place or a price only loosely: a filter on the
metadata does it exactly.
"""

from datetime import date

from pydantic import BaseModel, Field


class SearchFilters(BaseModel):
    """The constraints of a question, as the analysis understood them."""

    date_from: date | None = Field(default=None, description="First day.")
    date_to: date | None = Field(default=None, description="Last day.")
    district: str | None = Field(default=None, description="A known district.")
    venue: str | None = Field(default=None, description="A venue, or part of it.")
    free: bool | None = Field(default=None, description="Only free events.")

    def from_today(self, today: date) -> "SearchFilters":
        """Without a period, or with one that ends after today, the events start
        from today: finished events only for a question about the past."""
        if self.date_from is None and (self.date_to is None or self.date_to >= today):
            return self.model_copy(update={"date_from": today})
        return self

    def describe(self) -> str:
        """A line for the logs and reports, as "dates: 2026-10-17 to 2026-10-18,
        venue: ABC"."""
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
