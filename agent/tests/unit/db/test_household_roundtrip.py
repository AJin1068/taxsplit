"""가상 가구 5개를 DB에 넣었다 꺼내 Household로 되돌리면 원래와 같아야 한다."""

import asyncio
from datetime import UTC, datetime

import pytest
from allocation.households import HOUSEHOLDS

from taxsplit.allocation import Household
from taxsplit.db.repositories import SqlHouseholdRepository
from taxsplit.domain.models import StoredHousehold

NOW = datetime(2026, 11, 19, tzinfo=UTC)


@pytest.mark.parametrize("name", HOUSEHOLDS)
def test_household_json_roundtrip(engine, name: str) -> None:
    original: Household = HOUSEHOLDS[name]
    repo = SqlHouseholdRepository(engine)

    async def go() -> StoredHousehold | None:
        saved = await repo.save(
            StoredHousehold(
                tax_year=2025, data=original, source="json", created_at=NOW, updated_at=NOW
            )
        )
        assert saved.id is not None
        return await repo.get(saved.id)

    loaded = asyncio.run(go())
    assert loaded is not None
    assert loaded.data == original
