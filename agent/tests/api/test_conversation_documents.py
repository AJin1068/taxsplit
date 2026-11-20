"""대화 만들기의 documents(간소화 PDF 추출 결과) 검사: 올바른 2개는 받고, 잘못된 것은 422."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from taxsplit.api.deps import get_conversation_repo
from taxsplit.main import create_app
from taxsplit.repositories.memory import InMemoryConversationRepository


class Server:
    def __init__(self) -> None:
        self.repo = InMemoryConversationRepository()
        app = create_app()
        app.dependency_overrides[get_conversation_repo] = lambda: self.repo
        self.client = TestClient(app)


def _doc(name: str, amount: Any = 1_200_000) -> dict[str, Any]:
    return {
        "tax_year": 2024,
        "worker_name": name,
        "items": [
            {"group": "medical", "kind": "일반", "person_name": "봄", "amount": amount},
            {"group": "card", "kind": "신용카드", "person_name": name, "amount": 9_000_000},
        ],
    }


def test_documents_accepted_and_marked_prior_year() -> None:
    server = Server()
    res = server.client.post(
        "/conversations", json={"title": "t", "documents": [_doc("남편"), _doc("아내")]}
    )
    assert res.status_code == 201
    saved = server.repo._items[res.json()["id"]]
    assert len(saved.documents) == 2
    assert saved.documents[0]["prior_year"] is True


@pytest.mark.parametrize(
    ("doc", "expected"),
    [
        (_doc("남편", amount="1200000"), "documents[1].items[0].amount: 정수여야 합니다"),
        ({**_doc("남편"), "memo": "x"}, "documents[1].memo: 모르는 칸입니다"),
    ],
)
def test_documents_rejected_with_korean_paths(doc: dict, expected: str) -> None:
    server = Server()
    res = server.client.post(
        "/conversations", json={"title": "t", "documents": [_doc("아내"), doc]}
    )
    assert res.status_code == 422
    assert expected in res.json()["detail"]


def test_more_than_two_documents_rejected() -> None:
    server = Server()
    docs = [_doc("남편"), _doc("아내"), _doc("남편")]
    res = server.client.post("/conversations", json={"title": "t", "documents": docs})
    assert res.status_code == 422
    assert res.json()["detail"] == ["documents: 최대 2개까지 받습니다"]
