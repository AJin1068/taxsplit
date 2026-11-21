"""실행기가 빈 곳 알림 카드(gaps 이벤트)를 실행 기록에 남기고 채점이 빈 곳 숫자를 낸다(#136)."""

import json

from harness.fakes import DEFAULT_SCENARIOS, deps_for, factory, main_steps, sim_steps
from taxsplit.harness.__main__ import main
from taxsplit.harness.scenarios import load_scenarios
from taxsplit.harness.scoring import REPO_ROOT
from taxsplit.llm.base import ToolUseBlock
from taxsplit.tools.definitions import FIND_MISSING_DEDUCTIONS

V1 = REPO_ROOT / "eval" / "scenarios" / "v1"
# 시나리오 가구(계산 엔진 말) → 빈 곳 찾기 가족 목록(가족 질문 말). 테스트 쪽 가짜 AI가 옮겨 적는 것
TO_FAMILY = {"lineal_ascendant": "parent", "child": "child", "sibling": "sibling"}


def family_of(household: dict) -> dict:
    """가짜 AI가 빈 곳 찾기 도구에 넘길 가족(첫 질문 묶음은 아직 답을 받지 않음)."""
    members = [
        {
            "name": m["dependent"]["name"],
            "relation": TO_FAMILY[m["dependent"]["relation"]],
            "birth_year": m["dependent"]["birth_year"],
        }
        for m in household.get("members", [])
    ]
    return {"family": {"members": members, "answered": []}}


def gap_steps(household: dict) -> list:
    """대화 하나: 빈 곳 찾기 + 질문 → (다음 턴) 요건 확인 → 배분 비교 → 답."""
    find = ToolUseBlock(id="g", name=FIND_MISSING_DEDUCTIONS, input=family_of(household))
    return [find, *main_steps(household)]


def _run(argv: list[str], deps, tmp_path) -> dict:
    out = tmp_path / "r.json"
    assert main(["run", "--repeat", "1", "--out", str(out), *argv], factory(deps)) == 0
    return json.loads(out.read_text(encoding="utf-8"))


def test_record_keeps_card_id_and_member(tmp_path) -> None:
    s = load_scenarios(V1, ["v1-02"])[0]
    deps = deps_for(gap_steps(s["household"]), sim_steps(s))
    record = _run(["--scenarios", str(V1), "--only", "v1-02"], deps, tmp_path)["records"][0]
    gaps = record["gaps"]
    # 가구 전체 질문 카드는 member가 null
    assert {"id": "gap.parent_living_apart", "member": None} in gaps
    # 성년이 된 자녀(2006년생) 카드에는 관계·출생연도가 들어간다
    adult = {"relation": "child", "birth_year": 2006}
    assert {"id": "gap.child_turned_adult", "member": adult} in gaps
    assert all(set(g) == {"id", "member"} for g in gaps)
    assert len(gaps) == len({json.dumps(g, sort_keys=True) for g in gaps})  # 같은 카드는 한 번


def test_no_gaps_event_means_empty_list(tmp_path) -> None:
    s = load_scenarios(DEFAULT_SCENARIOS, ["v0-02"])[0]
    deps = deps_for(main_steps(s["household"]), sim_steps(s))
    assert _run(["--only", "v0-02"], deps, tmp_path)["records"][0]["gaps"] == []


def test_v1_folder_gives_gap_hit_rate_number(tmp_path, capsys) -> None:
    scenarios = load_scenarios(V1)
    main_s, sim_s = [], []
    for s in scenarios:
        main_s += gap_steps(s["household"])
        sim_s += sim_steps(s)
    result = _run(["--scenarios", str(V1)], deps_for(main_s, sim_s), tmp_path)
    overall = result["summary"]["overall"]
    assert isinstance(overall["gap_hit_rate"], float) and 0 < overall["gap_hit_rate"] <= 1
    assert isinstance(overall["gap_false_alarms"], int)
    assert result["summary"]["by_gap"]
    assert "빈 곳 알림 적중률" in capsys.readouterr().out


def test_two_scenario_folders_go_into_one_result(tmp_path) -> None:
    v0 = load_scenarios(DEFAULT_SCENARIOS, ["v0-02"])
    v1 = load_scenarios(V1, ["v1-02"])
    main_s = main_steps(v0[0]["household"]) + gap_steps(v1[0]["household"])
    sim_s = sim_steps(v0[0]) + sim_steps(v1[0])
    argv = ["--scenarios", str(DEFAULT_SCENARIOS), "--scenarios", str(V1)]
    argv += ["--only", "v0-02", "--only", "v1-02"]
    result = _run(argv, deps_for(main_s, sim_s), tmp_path)
    assert result["scenarios"]["ids"] == ["v0-02", "v1-02"]
    assert result["scenarios"]["versions"] == ["v0", "v1"]
    assert result["scenarios"]["folder"] == [str(DEFAULT_SCENARIOS), str(V1)]
    assert [r["scenario_id"] for r in result["records"]] == ["v0-02", "v1-02"]
    assert result["summary"]["overall"]["conversations"] == 2


def _never_called(args):
    raise AssertionError("id가 겹치면 클라이언트를 만들기 전에 멈춰야 한다")


def test_duplicate_ids_across_folders_stop_before_start(tmp_path, capsys) -> None:
    other = tmp_path / "other"
    other.mkdir()
    data = json.loads((DEFAULT_SCENARIOS / "v0-02.json").read_text(encoding="utf-8"))
    (other / "copy.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    argv = ["run", "--scenarios", str(DEFAULT_SCENARIOS), "--scenarios", str(other)]
    assert main(argv, _never_called) == 2
    err = capsys.readouterr().err
    assert "겹칩니다" in err and "v0-02" in err


def test_sim_user_does_not_see_gaps_expected(tmp_path) -> None:
    s = load_scenarios(V1, ["v1-01"])[0]
    deps = deps_for(gap_steps(s["household"]), sim_steps(s))
    _run(["--scenarios", str(V1), "--only", "v1-01"], deps, tmp_path)
    sim_texts = " ".join((r.system or "") + str(r.messages) for r in deps.sim_llm.requests)
    assert "gaps_expected" not in sim_texts and "not_show" not in sim_texts
