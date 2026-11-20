"""첫 화면 설정(UI-00, FR-09·FR-10): 대화 만들기에 본인 입장·자녀 수를 받아 저장하고 돌려준다."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from taxsplit.api.deps import get_conversation_repo
from taxsplit.main import create_app
from taxsplit.repositories.memory import InMemoryConversationRepository


@pytest.fixture
def client() -> Iterator[TestClient]:
    repo = InMemoryConversationRepository()
    app = create_app()
    app.dependency_overrides[get_conversation_repo] = lambda: repo
    yield TestClient(app)


@pytest.mark.parametrize(("role", "count"), [("wife", 2), ("husband", 0), ("husband", 5)])
def test_setup_values_saved_and_returned(client: TestClient, role: str, count: int) -> None:
    created = client.post(
        "/conversations", json={"title": "t", "self_role": role, "child_count": count}
    )
    assert created.status_code == 201
    assert created.json()["self_role"] == role and created.json()["child_count"] == count
    fetched = client.get(f"/conversations/{created.json()['id']}").json()
    assert fetched["self_role"] == role and fetched["child_count"] == count


def test_start_without_choosing(client: TestClient) -> None:
    created = client.post("/conversations", json={"title": "t"})
    assert created.status_code == 201
    fetched = client.get(f"/conversations/{created.json()['id']}").json()
    assert fetched["self_role"] is None and fetched["child_count"] is None


@pytest.mark.parametrize(
    "extra",
    [{"self_role": "me"}, {"child_count": 6}, {"child_count": -1}, {"child_count": "two"}],
)
def test_bad_setup_values_rejected(client: TestClient, extra: dict) -> None:
    res = client.post("/conversations", json={"title": "t", **extra})
    assert res.status_code == 422
