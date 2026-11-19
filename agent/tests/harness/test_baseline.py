"""--baseline 비교: 떨어짐 / 같음 또는 좋아짐 / 비용 늘어남(경고). 떨어지면 끝 값 1."""

import json

from harness.fakes import DEFAULT_SCENARIOS, deps_for, factory, main_steps, sim_steps
from taxsplit.harness.__main__ import main
from taxsplit.harness.results import compare, comparison_lines
from taxsplit.harness.scenarios import load_scenarios


def overall(match=0.8, missed=0.1, invalid=0.05, cost=0.10) -> dict:
    return {
        "conversations": 30,
        "match_rate": match,
        "missed_question_rate": missed,
        "invalid_args_rate": invalid,
        "order_violations": 0,
        "cost_per_conversation_usd": cost,
        "explanation_consistent_rate": None,
    }


def write(tmp_path, name: str, **kw):
    path = tmp_path / f"{name}.json"
    path.write_text(json.dumps({"summary": {"overall": overall(**kw)}}))
    return path


def verdict(tmp_path, **cur) -> tuple[dict, list[str]]:
    result = {"summary": {"overall": overall(**cur)}}
    cmp = compare(result, write(tmp_path, "base"))
    return cmp, comparison_lines(cmp)


def test_drop_when_match_falls_10pp(tmp_path) -> None:
    cmp, lines = verdict(tmp_path, match=0.7)
    assert cmp["verdict"] == "떨어짐"
    assert "배분안 일치율" in lines[1]


def test_drop_when_missed_or_invalid_rises(tmp_path) -> None:
    assert verdict(tmp_path, missed=0.2)[0]["verdict"] == "떨어짐"
    assert verdict(tmp_path, invalid=0.15)[0]["verdict"] == "떨어짐"


def test_same_or_better(tmp_path) -> None:
    cmp, lines = verdict(tmp_path, match=0.75, missed=0.0)
    assert cmp["verdict"] == "같음 또는 좋아짐"
    assert lines == ["기준 수치 비교: 같음 또는 좋아짐"]


def test_cost_rise_is_warning_not_drop(tmp_path) -> None:
    cmp, lines = verdict(tmp_path, cost=0.16)
    assert cmp["verdict"] == "같음 또는 좋아짐"
    assert cmp["cost_warning"] is True
    assert any("비용 늘어남" in line for line in lines)


def _run_with_baseline(tmp_path, reveal: bool) -> tuple[int, dict]:
    s = load_scenarios(DEFAULT_SCENARIOS, ["v0-02"])[0]
    deps = deps_for(main_steps(s["household"]), sim_steps(s, reveal=reveal))
    base = write(tmp_path, "base", match=1.0, missed=0.0, invalid=0.0, cost=1.0)
    out = tmp_path / "r.json"
    args = ["run", "--only", "v0-02", "--repeat", "1", "--baseline", str(base), "--out", str(out)]
    code = main(args, factory(deps))
    return code, json.loads(out.read_text(encoding="utf-8"))


def test_command_exits_nonzero_on_drop(tmp_path, capsys) -> None:
    # 꼭 물어야 할 사실(시어머니 소득)을 듣지 못함 → 누락 질문 비율 0% → 100%
    code, result = _run_with_baseline(tmp_path, reveal=False)
    assert code == 1
    assert result["baseline_comparison"]["verdict"] == "떨어짐"
    assert "기준 수치 비교: 떨어짐" in capsys.readouterr().out


def test_command_exits_zero_when_same(tmp_path) -> None:
    code, result = _run_with_baseline(tmp_path, reveal=True)
    assert code == 0
    assert result["baseline_comparison"]["verdict"] == "같음 또는 좋아짐"
