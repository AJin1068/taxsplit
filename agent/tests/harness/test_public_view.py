"""public_view: 실행기·가상 사용자에게 정답 칸(gold·review·gaps_expected)을 주지 않는다."""

from taxsplit.harness.scenarios import load_scenarios, public_view
from taxsplit.harness.scoring import REPO_ROOT

V1 = REPO_ROOT / "eval" / "scenarios" / "v1"


def test_public_view_drops_answers() -> None:
    for s in load_scenarios(V1):
        assert "gaps_expected" in s  # v1은 빈 곳 정답이 있다
        view = public_view(s)
        assert not {"gold", "review", "gaps_expected"} & set(view)
        assert view["facts"] == s["facts"] and view["documents"] == s["documents"]
