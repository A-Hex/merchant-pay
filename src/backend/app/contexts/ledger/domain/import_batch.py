from dataclasses import dataclass, field
from datetime import datetime

from app.shared.domain.enums import DataOrigin


@dataclass(frozen=True, slots=True)
class RowError:
    row_number: int
    field: str
    message: str


@dataclass(frozen=True, slots=True)
class ImportBatch:
    batch_id: str
    source_name: str
    data_origin: DataOrigin
    imported_at: datetime
    row_count: int


@dataclass(frozen=True, slots=True)
class ImportReport:
    source_name: str
    batch_id: str | None
    imported_rows: int
    errors: list[RowError] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors
