"""[검증] 올리기 스크립트(.github/scripts/post_verify.py)의 할 일 넘기기 테스트.

검증이 넘긴 할 일은 열린 `PR N:` Issue가 있으면 거기 코멘트로 달고,
없으면 새 Issue를 만들되 제목이 `PR `으로 시작하면 안 된다(PR 1ab).
`PR N:` 제목의 열린 Issue가 생기면 goal은 선행 PR N이 안 끝났다고 보고,
`/next-issue`는 그 Issue를 작업으로 고른다.
gh 호출은 가짜로 바꿔 끼우고 `--dry-run` 출력으로 확인한다.
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[3] / ".github" / "scripts"
OPEN_ISSUES = [
    {"number": 140, "title": "PR 5: 계산 엔진 ⑤"},
    {"number": 141, "title": "묶음 9: 무언가"},
]


@pytest.fixture(scope="module")
def pv():
    sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location("post_verify", SCRIPTS / "post_verify.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def fake_gh(pv, monkeypatch):
    """gh를 가짜로 바꾼다. 부른 명령을 모아 두고, 정해진 응답만 돌려준다."""
    calls: list[tuple[str, ...]] = []

    def gh(*args: str, stdin: str | None = None) -> str:
        calls.append(args)
        if args[:2] == ("issue", "list"):
            return json.dumps(OPEN_ISSUES)
        if args[:2] == ("pr", "diff"):
            return "agent/x.py\n"
        if args[:1] == ("api",) and "comments" in args[-1]:
            return "[]"
        return ""

    monkeypatch.setattr(pv, "gh", gh)
    return calls


def _writes(calls):
    """실제로 GitHub에 쓰는 명령(코멘트·Issue 만들기)."""
    return [c for c in calls if c[:2] in {("issue", "comment"), ("issue", "create")}]


def test_open_issue_gets_comment(pv, fake_gh):
    log = pv.post_followups("o/r", 61, [{"pr": "5", "body": "고칠 것"}], dry_run=True)
    assert log == ["Issue #140(PR 5)에 코멘트"]
    assert _writes(fake_gh) == []  # dry-run은 쓰지 않는다


def test_missing_issue_title_does_not_start_with_pr(pv, fake_gh):
    items = [{"pr": "7", "title": "턴 세기 고치기", "body": "b"}]
    log = pv.post_followups("o/r", 61, items, dry_run=True)
    assert log == ["새 Issue '[할 일] PR 7 뒤: 턴 세기 고치기' (ready 없음)"]


def test_model_title_with_pr_prefix_is_stripped(pv, fake_gh):
    # 모델이 title에 "PR 7: …"을 붙여도 새 Issue 제목은 PR로 시작하지 않는다
    items = [{"pr": "7", "title": "PR 7: 턴 세기", "body": "b"}, {"pr": "", "body": "b"}]
    log = pv.post_followups("o/r", 61, items, dry_run=True)
    titles = [line.split("'")[1] for line in log]
    assert titles == ["[할 일] PR 7 뒤: 턴 세기", "[할 일] 검증에서 넘긴 할 일"]
    assert not any(t.upper().startswith("PR") for t in titles)


def test_not_matched_by_task_pattern(pv):
    # 새 제목을 다시 넣어도 find_issue_for(작업 Issue 찾기)에 걸리지 않는다
    title = pv.followup_title("1k", "x")
    assert pv.find_issue_for("1k", [{"number": 1, "title": title}]) is None


def test_create_when_not_dry_run(pv, fake_gh):
    pv.post_followups("o/r", 61, [{"pr": "9", "title": "t", "body": "b"}], dry_run=False)
    created = [c for c in _writes(fake_gh) if c[1] == "create"]
    assert len(created) == 1
    title = created[0][created[0].index("--title") + 1]
    assert title == "[할 일] PR 9 뒤: t"
    assert "--label" not in created[0]  # ready를 붙이지 않는다


def test_main_dry_run_output(pv, fake_gh, tmp_path, monkeypatch, capsys):
    (tmp_path / "comment.md").write_text("[검증] PR 7 / 판정: 통과\n", encoding="utf-8")
    followups = [{"pr": "5", "body": "a"}, {"pr": "7", "title": "턴", "body": "b"}]
    (tmp_path / "followups.json").write_text(json.dumps(followups), encoding="utf-8")
    argv = ["post_verify.py", "--pr", "61", "--repo", "o/r", "--dir", str(tmp_path), "--dry-run"]
    monkeypatch.setattr(sys, "argv", argv)
    pv.main()
    out = capsys.readouterr().out
    assert "Issue #140(PR 5)에 코멘트" in out
    assert "새 Issue '[할 일] PR 7 뒤: 턴' (ready 없음)" in out
    assert "새 Issue 'PR " not in out
    assert _writes(fake_gh) == []
