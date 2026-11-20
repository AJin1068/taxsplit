"""감시 검사(.github/scripts/guard.py)의 규칙 판정 테스트.

GitHub에서는 merge 뒤에만 돌기 때문에, Issue의 시험 PR ①~④를 여기서 먼저 흉내 낸다.
"""

import importlib.util
from pathlib import Path

import pytest

GUARD_PATH = Path(__file__).resolve().parents[3] / ".github" / "scripts" / "guard.py"


@pytest.fixture(scope="module")
def guard():
    spec = importlib.util.spec_from_file_location("guard", GUARD_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def rules(violations):
    return {(path, rule[0]) for path, rule in violations}


# 시험 PR ①: ci.yml만 고친 PR → 실패, infra-ok 붙이면 통과
def test_infra_file_fails_without_label(guard):
    result = guard.check([".github/workflows/ci.yml"], "chore/x", set())
    assert rules(result) == {(".github/workflows/ci.yml", "①")}


def test_infra_file_passes_with_label(guard):
    assert guard.check([".github/workflows/ci.yml"], "chore/x", {"infra-ok"}) == []


# 시험 PR ②: ci.yml + eval/ (eval/ 아닌 브랜치) → infra-ok가 있어도 실패
def test_eval_change_not_unlocked_by_infra_ok(guard):
    files = [".github/workflows/ci.yml", "eval/cases/a.json"]
    result = guard.check(files, "feat/x", {"infra-ok"})
    assert rules(result) == {("eval/cases/a.json", "②")}


# 시험 PR ③: docs/만 → 통과 (agent/, README.md도 잡으면 안 됨)
@pytest.mark.parametrize(
    "files",
    [
        ["docs/prd.md"],
        ["agent/src/taxsplit/main.py", "agent/tests/unit/test_config.py"],
        ["README.md"],
        ["eval/README.md"],
        [".claude/commands/next-issue.md"],
    ],
)
def test_ordinary_changes_pass(guard, files):
    assert guard.check(files, "feat/x", set()) == []


# 시험 PR ④: eval/ 브랜치에서 eval/만 → 통과
def test_eval_branch_may_change_eval(guard):
    assert guard.check(["eval/cases/a.json"], "eval/hometax", set()) == []


def test_eval_branch_still_needs_infra_ok(guard):
    result = guard.check(["eval/cases/a.json", ".github/ci.yml"], "eval/x", set())
    assert rules(result) == {(".github/ci.yml", "①")}


@pytest.mark.parametrize(
    "path",
    [
        ".claude/settings.json",
        ".claude/commands/verify-pr.md",
        ".github/scripts/guard.py",
        # goal 연속 실행의 조건문 틀과 기계 검문 자체 (PR 1ab)
        ".claude/goal-condition.md",
        "scripts/goal/lib-checks.sh",
        "scripts/goal/fakes/gh",
    ],
)
def test_all_guarded_files(guard, path):
    assert rules(guard.check([path], "chore/x", set())) == {(path, "①")}


def test_branch_name_must_start_with_eval(guard):
    # "evaluation/..."이나 "feat/eval/..." 같은 이름으로 벽을 피하지 못한다
    for ref in ["evaluation/x", "feat/eval/x", "eval"]:
        assert guard.check(["eval/a.json"], ref, set()) != []


def test_rename_out_of_eval_is_caught(guard, monkeypatch):
    # eval/ 파일을 밖으로 옮기면 원래 이름(previous_filename)으로 걸린다
    pages = [[{"filename": "docs/a.json", "previous_filename": "eval/cases/a.json"}]]
    monkeypatch.setattr(guard, "gh_json", lambda *args: pages)
    files = guard.fetch_changed_files("o/r", 1)
    assert rules(guard.check(files, "feat/x", set())) == {("eval/cases/a.json", "②")}


# PR 1ab: 감시 목록을 넓혀도 문서·코드·CLAUDE.md만 바꾼 PR은 infra-ok 없이 통과해야 한다
@pytest.mark.parametrize(
    "files",
    [
        ["CLAUDE.md"],
        ["CLAUDE.md", "docs/assumptions.md", "agent/src/taxsplit/main.py"],
        ["scripts/README.md"],
        ["scripts/goalkeeper/x.sh", ".claude/goal-condition.md.bak"],
    ],
)
def test_docs_agent_claude_md_pass(guard, files):
    assert guard.check(files, "docs/x", set()) == []
