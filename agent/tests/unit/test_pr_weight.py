"""PR 무게 판정(.github/scripts/pr_weight.py) 테스트. Issue의 시험 경우를 여기서 흉내 낸다.

(라)는 실제 규칙표와 실제 규칙 커버리지로 시험한다. 0건인 규칙은 그때그때 고른다(고정값 아님).
"""

import importlib.util
from pathlib import Path

import pytest
from cases.rule_coverage import coverage

from taxsplit.rules.loader import rules_path

PATH = Path(__file__).resolve().parents[3] / ".github" / "scripts" / "pr_weight.py"
RULES = "agent/src/taxsplit/rules/rules_2025.toml"


@pytest.fixture(scope="module")
def pw():
    spec = importlib.util.spec_from_file_location("pr_weight", PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def cov():
    return coverage()


def _bump_rule(text: str, rule_id: str) -> str:
    """규칙 하나의 summary만 바꾼 규칙표 글자(시험 PR이 그 규칙을 고친 것처럼)."""
    marker = f'id = "{rule_id}"\n'
    assert marker in text
    head, tail = text.split(marker, 1)
    return head + marker + tail.replace('summary = "', 'summary = "(바꿈) ', 1)


def test_changing_uncovered_rule_is_heavy(pw, cov):
    zero = next(i for i, n in cov.items() if n == 0)
    base = rules_path(2025).read_text(encoding="utf-8")
    changed = pw.changed_rule_ids(base, _bump_rule(base, zero))
    assert changed == {zero}
    result = pw.judge([RULES], set(), "", changed, cov)
    assert result["weight"] == "무거움" and result["criteria"] == ["라"]
    assert result["changed_rules"] == {zero: 0}


def test_changing_covered_rule_only_is_light(pw, cov):
    covered = next(i for i, n in cov.items() if n > 0)
    base = rules_path(2025).read_text(encoding="utf-8")
    changed = pw.changed_rule_ids(base, _bump_rule(base, covered))
    result = pw.judge([RULES], set(), "", changed, cov)
    assert result["weight"] == "가벼움"
    assert result["changed_rules"][covered] > 0


def test_comment_only_change_changes_no_rule(pw):
    base = rules_path(2025).read_text(encoding="utf-8")
    assert pw.changed_rule_ids(base, "# 주석 한 줄\n" + base) == set()


def test_added_or_removed_rule_counts_as_changed(pw):
    base = rules_path(2025).read_text(encoding="utf-8")
    assert pw.changed_rule_ids("", base) == set(pw.rule_rows(base))


@pytest.mark.parametrize(
    "files",
    [
        ["frontend/src/App.tsx", "frontend/src/screen.css"],
        ["docs/design.md", "README.md"],
        ["agent/src/taxsplit/api/routes/conversations.py"],
        [".github/workflows/ci.yml"],
    ],
)
def test_screen_or_docs_only_is_light(pw, cov, files):
    assert pw.judge(files, set(), "## 확인해 주세요\n\n없음\n", set(), cov)["weight"] == "가벼움"


def test_eval_change_is_heavy(pw):
    assert pw.judge(["eval/cases/a.json"], set(), "", set(), {})["criteria"] == ["가"]


def test_needs_verify_is_heavy(pw):
    assert pw.judge(["docs/a.md"], {"needs-verify"}, "", set(), {})["criteria"] == ["나"]


def test_case_code_change_is_heavy(pw):
    result = pw.judge(["agent/tests/cases/case_convert.py"], set(), "", set(), {})
    assert result["criteria"] == ["라"]


BODY = """# 사람이 볼 것

## 확인해 주세요

<!-- ### 예시
- **누가 답하나**: 기획 / 사람 -->

### ✅ 1. 끝난 것
- **누가 답하나**: 사람

### ➡️ 2. 넘긴 것
- **누가 답하나**: 사람

### 3. 기획이 볼 것
- **누가 답하나**: 기획

{extra}
## merge 전에 볼 코드

### 9. 여기는 다른 칸
- **누가 답하나**: 사람
"""


def test_open_human_item_is_heavy(pw):
    body = BODY.format(extra="### 4. 사람이 정할 것\n- **누가 답하나**: 사람.\n")
    assert pw.open_human_items(body) == ["4. 사람이 정할 것"]
    assert pw.judge([], set(), body, set(), {})["criteria"] == ["다"]


def test_closed_or_planner_items_are_light(pw):
    assert pw.open_human_items(BODY.format(extra="")) == []


def test_first_line_gets_machine_weight(pw):
    heavy = pw.judge(["eval/a.json"], {"needs-verify"}, "", set(), {})
    body = "[검증] PR 5 / 판정: 통과 / 기준 커밋 abc1234 / 무게: 가벼움\n\n### 완료 기준"
    out = pw.with_weight(body, heavy)
    first = out.splitlines()[0]
    # 모델이 적은 무게는 지우고 기계 판정만 남긴다. 기계 검문 ⑤가 읽는 칸은 그대로
    assert first == "[검증] PR 5 / 판정: 통과 / 기준 커밋 abc1234 / 무게: 무거움 (가·나)"
    assert "### PR 무게 (기계 판정)" in out and "### 완료 기준" in out


@pytest.mark.parametrize(
    ("heavy", "labels", "action"),
    [
        (True, set(), "add"),
        (True, {"human-review"}, None),
        (False, {"human-review", "chore"}, "remove"),
        (False, set(), None),
    ],
)
def test_label_follows_weight(pw, heavy, labels, action):
    assert pw.label_action(heavy, labels) == action
