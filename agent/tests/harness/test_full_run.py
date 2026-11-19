"""명령 하나(`python -m taxsplit.harness run`)로 v0 시나리오 전체를 가짜 LLM으로 돌린다."""

import json

from harness.fakes import DEFAULT_SCENARIOS, deps_for, factory, main_steps, sim_steps
from taxsplit.harness.__main__ import main
from taxsplit.harness.scenarios import load_scenarios

JUDGE_OK = json.dumps({"consistent": True, "reason": "배분 결과와 같다"})


def test_one_command_runs_all_scenarios_and_writes_result(tmp_path, capsys) -> None:
    scenarios = load_scenarios(DEFAULT_SCENARIOS)
    main_s, sim_s = [], []
    for s in scenarios:
        main_s += main_steps(s["household"])
        sim_s += sim_steps(s)
    deps = deps_for(main_s, sim_s, judge=[JUDGE_OK] * len(scenarios))
    out = tmp_path / "result.json"

    code = main(["run", "--repeat", "1", "--judge", "--out", str(out)], factory(deps))

    assert code == 0
    result = json.loads(out.read_text(encoding="utf-8"))
    # 결과 JSON 칸(Issue #20 범위 6번)
    for key in ("records", "summary", "cost", "models", "commit", "scenarios", "elapsed_seconds"):
        assert key in result
    assert result["scenarios"]["versions"] == ["v0"]
    assert result["scenarios"]["ids"] == [s["id"] for s in scenarios]
    assert result["stopped_by_cost_cap"] is False
    assert set(result["cost"]) == {"main_agent_usd", "sim_user_usd", "judge_usd", "total_usd"}
    assert all(v is not None and v > 0 for v in result["cost"].values())

    records = result["records"]
    assert len(records) == len(scenarios)
    assert {r["ended"] for r in records} == {"answered"}
    assert all(r["turns"] == 2 and r["judge"]["consistent"] for r in records)
    first = records[0]
    assert [t["role"] for t in first["transcript"]] == ["user", "assistant", "user", "assistant"]
    assert first["tool_calls"][0] == {"tool": "check_eligibility", "status": "ok", "errors": []}

    # 진짜 가구로 계산한 배분안이라 기준 정답과 모두 맞아야 한다(실행기·채점 연결 확인)
    overall = result["summary"]["overall"]
    assert overall["conversations"] == len(scenarios)
    assert overall["match_rate"] == 1.0
    assert overall["missed_question_rate"] == 0.0
    assert overall["explanation_consistent_rate"] == 1.0
    assert "결과 JSON" in capsys.readouterr().out


def test_gold_is_not_sent_to_agent_or_sim_user(tmp_path) -> None:
    scenario = load_scenarios(DEFAULT_SCENARIOS, ["v0-02"])[0]
    deps = deps_for(main_steps(scenario["household"]), sim_steps(scenario))
    code = main(
        ["run", "--repeat", "1", "--only", "v0-02", "--out", str(tmp_path / "r.json")],
        factory(deps),
    )
    assert code == 0
    sim_texts = [r.system or "" for r in deps.sim_llm.requests]
    assert sim_texts and not any("best_total" in t or "must_ask" in t for t in sim_texts)
    assert str(scenario["gold"]["best_total"]) not in " ".join(sim_texts)
