"""평가 하네스 채점 코드 (규칙: eval/scoring/rules.md, 실행 기록 형식: eval/scoring/README.md).

표준 라이브러리만 쓰고 계산 엔진을 import하지 않는다. 기준 정답(`gold`)에 모든 배분안의
합계가 들어 있어서, 에이전트가 고른 안의 금액도 검수한 파일에서 찾는다.

평가 하네스 실행기(agent/src/taxsplit/harness/, PR 11)가 이 파일을 경로로 불러 쓴다.
이 파일은 eval/ 벽 안에 있어 개발 PR이 고칠 수 없다.
"""

import json
from pathlib import Path

GROUPS = ("dependent", "child", "medical", "education", "card")
FACT_KINDS = ("must_ask", "may_assume", "background")
ENDED = ("answered", "stopped", "error", "max_turns")
WHO = ("husband", "wife")

# 기준 수치 비교 (rules.md "기준 수치와 비교")
DROP_MATCH = 0.10  # 배분안 일치율이 이만큼(10%p) 이상 떨어지면 떨어짐
RISE_MISSED = 0.10  # 누락 질문 비율이 이만큼 이상 오르면 떨어짐
RISE_INVALID = 0.10  # 잘못된 인자 비율이 이만큼 이상 오르면 떨어짐
COST_WARN_RATIO = 1.5  # 대화당 비용이 기준의 1.5배를 넘으면 경고


# ---------- 시나리오 형식 검사 ----------


def _key(member: dict) -> tuple[str, int]:
    return (member["relation"], member["birth_year"])


def check_scenario(data: dict) -> list[str]:
    """시나리오 하나의 형식 오류 목록. 비어 있으면 통과."""
    errs: list[str] = []
    for name in ("id", "version", "status", "title", "groups", "household", "documents"):
        if name not in data:
            errs.append(f"{name}: 칸이 없습니다")
    for name in ("opening", "persona", "facts"):
        if name not in data:
            errs.append(f"{name}: 칸이 없습니다")
    if errs:
        return errs
    if data["status"] not in ("draft", "confirmed"):
        errs.append(f"status: draft 또는 confirmed여야 합니다 (받은 값 {data['status']!r})")
    if not data["groups"] or any(g not in GROUPS for g in data["groups"]):
        errs.append(f"groups: {GROUPS} 중에서 하나 이상이어야 합니다")
    ids = [f.get("id") for f in data["facts"]]
    if len(set(ids)) != len(ids):
        errs.append("facts: id가 겹칩니다")
    for i, f in enumerate(data["facts"]):
        if f.get("kind") not in FACT_KINDS:
            errs.append(f"facts[{i}].kind: {FACT_KINDS} 중 하나여야 합니다")
        if not f.get("text"):
            errs.append(f"facts[{i}].text: 비어 있으면 안 됩니다")
    members = [m["dependent"] for m in data["household"].get("members", [])]
    keys = [_key(m) for m in members]
    if len(set(keys)) != len(keys):
        errs.append(
            "household.members: (관계, 출생연도)가 겹치는 부양가족이 있어 짝짓기를 할 수 없습니다"
        )
    if len(data["documents"]) != 2:
        errs.append("documents: 부부 각자 1개, 모두 2개여야 합니다")
    if data["status"] == "confirmed" and not data.get("gold"):
        errs.append("gold: confirmed 시나리오에는 기준 정답이 있어야 합니다")
    gold = data.get("gold")
    if gold:
        for name in ("plan_count", "best_assignments", "best_total", "plans", "members"):
            if name not in gold:
                errs.append(f"gold.{name}: 칸이 없습니다")
    return errs


def load_scenarios(folder: str | Path) -> list[dict]:
    """폴더의 *.json 시나리오를 id 순으로 읽는다. 형식이 틀리면 파일 이름과 함께 ValueError."""
    out = []
    for path in sorted(Path(folder).glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        errs = check_scenario(data)
        if errs:
            raise ValueError(f"{path.name}: " + "; ".join(errs))
        out.append(data)
    return sorted(out, key=lambda s: s["id"])


# ---------- 대화 하나 채점 ----------


def _map_assignment(final: dict, gold: dict) -> dict | None:
    """에이전트의 배분안(에이전트가 붙인 이름 → 쪽)을 진짜 가족 이름 → 쪽으로 옮긴다.

    짝짓기는 (관계, 출생연도)로 한다. 짝이 없거나 겹치면 None.
    """
    truth = {_key(m): m["name"] for m in gold["members"]}
    by_agent_name = {}
    for m in final.get("members", []):
        k = _key(m)
        if k not in truth or m["name"] in by_agent_name:
            return None
        by_agent_name[m["name"]] = truth[k]
    if len(set(by_agent_name.values())) != len(by_agent_name):
        return None
    mapped = {}
    for name, who in final.get("assignment", {}).items():
        if name not in by_agent_name or who not in WHO:
            return None
        mapped[by_agent_name[name]] = who
    return mapped


def score_run(scenario: dict, record: dict) -> dict:
    """대화 하나(시나리오 × 반복 1번)의 점수."""
    gold = scenario["gold"]
    final = record.get("final")
    mapped = _map_assignment(final, gold) if final else None
    match = mapped is not None and mapped in gold["best_assignments"]
    missed_won = None
    if mapped is not None:
        for p in gold["plans"]:
            if p["assignment"] == mapped:
                missed_won = p["total"] - gold["best_total"]
                break
    must = [f["id"] for f in scenario["facts"] if f["kind"] == "must_ask"]
    revealed = set(record.get("revealed", []))
    missed_facts = [fid for fid in must if fid not in revealed]
    calls = record.get("tool_calls", [])
    invalid = sum(1 for c in calls if c.get("status") == "invalid_args")
    order = sum(1 for c in calls if c.get("status") == "order_violation")
    cost = record.get("cost") or {}
    return {
        "scenario_id": scenario["id"],
        "repeat": record.get("repeat"),
        "ended": record.get("ended"),
        "match": match,
        "missed_won": missed_won,
        "must_ask": len(must),
        "missed_facts": missed_facts,
        "tool_calls": len(calls),
        "invalid_args": invalid,
        "order_violations": order,
        "main_agent_usd": cost.get("main_agent_usd"),
        "sim_user_usd": cost.get("sim_user_usd"),
        "judge_usd": cost.get("judge_usd"),
        "judge_consistent": (record.get("judge") or {}).get("consistent"),
    }


# ---------- 모아서 숫자 내기 ----------


def _ratio(num: float, den: float) -> float | None:
    return None if den == 0 else num / den


def _sum_or_none(values: list) -> float | None:
    return None if any(v is None for v in values) else sum(values)


def _numbers(runs: list[dict]) -> dict:
    n = len(runs)
    cost = _sum_or_none([r["main_agent_usd"] for r in runs])
    judged = [r["judge_consistent"] for r in runs if r["judge_consistent"] is not None]
    return {
        "conversations": n,
        "match_rate": _ratio(sum(r["match"] for r in runs), n),
        "missed_question_rate": _ratio(
            sum(len(r["missed_facts"]) for r in runs), sum(r["must_ask"] for r in runs)
        ),
        "invalid_args_rate": _ratio(
            sum(r["invalid_args"] for r in runs), sum(r["tool_calls"] for r in runs)
        ),
        "order_violations": sum(r["order_violations"] for r in runs),
        "cost_per_conversation_usd": None if cost is None or n == 0 else cost / n,
        "explanation_consistent_rate": _ratio(sum(judged), len(judged)),
    }


def summarize(scenarios: list[dict], records: list[dict]) -> dict:
    """실행 기록 전부를 채점한다. confirmed 시나리오만 점수에 넣고, draft는 따로 센다."""
    by_id = {s["id"]: s for s in scenarios}
    runs, skipped = [], []
    for rec in records:
        s = by_id.get(rec["scenario_id"])
        if s is None:
            raise ValueError(f"실행 기록의 시나리오가 없습니다: {rec['scenario_id']}")
        if s["status"] != "confirmed":
            skipped.append(rec["scenario_id"])
            continue
        runs.append(score_run(s, rec))
    groups = {}
    for g in GROUPS:
        ids = {s["id"] for s in scenarios if g in s["groups"] and s["status"] == "confirmed"}
        sub = [r for r in runs if r["scenario_id"] in ids]
        if sub:
            groups[g] = _numbers(sub)
    per_scenario = {}
    for sid in sorted({r["scenario_id"] for r in runs}):
        per_scenario[sid] = _numbers([r for r in runs if r["scenario_id"] == sid])
    cost_other = {
        "sim_user_usd": _sum_or_none([r["sim_user_usd"] for r in runs]),
        "judge_usd": _sum_or_none([r["judge_usd"] or 0 for r in runs]),
    }
    return {
        "overall": _numbers(runs),
        "by_group": groups,
        "by_scenario": per_scenario,
        "runs": runs,
        "skipped_draft": sorted(set(skipped)),
        "other_cost": cost_other,
    }


# ---------- 기준 수치와 비교 ----------


def compare_to_baseline(current: dict, baseline: dict) -> dict:
    """summarize 결과의 overall 두 개를 비교한다(rules.md "기준 수치와 비교")."""
    cur, base = current["overall"], baseline["overall"]
    reasons = []

    def diff(name: str) -> float | None:
        if cur.get(name) is None or base.get(name) is None:
            return None
        return cur[name] - base[name]

    d_match = diff("match_rate")
    d_missed = diff("missed_question_rate")
    d_invalid = diff("invalid_args_rate")
    # 부동소수 오차로 0.1을 아슬아슬하게 못 넘는 것을 막는다
    eps = 1e-9
    if d_match is not None and -d_match >= DROP_MATCH - eps:
        reasons.append(f"배분안 일치율 {d_match * 100:+.1f}%p")
    if d_missed is not None and d_missed >= RISE_MISSED - eps:
        reasons.append(f"누락 질문 비율 {d_missed * 100:+.1f}%p")
    if d_invalid is not None and d_invalid >= RISE_INVALID - eps:
        reasons.append(f"잘못된 인자 비율 {d_invalid * 100:+.1f}%p")
    cost_warning = False
    c, b = cur.get("cost_per_conversation_usd"), base.get("cost_per_conversation_usd")
    if c is not None and b:
        cost_warning = c > b * COST_WARN_RATIO
    return {
        "verdict": "떨어짐" if reasons else "같음 또는 좋아짐",
        "reasons": reasons,
        "cost_warning": cost_warning,
        "diff": {
            "match_rate": d_match,
            "missed_question_rate": d_missed,
            "invalid_args_rate": d_invalid,
            "order_violations": cur["order_violations"] - base["order_violations"],
        },
    }
