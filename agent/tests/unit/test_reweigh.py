"""설명만 바뀐 PR의 무게 다시 맞추기(.github/scripts/reweigh.py) 테스트.

PR 설명에서 "사람" 항목에 ✅를 달면(새 커밋 없이) 무거움 → 가벼움으로 [검증] 첫 줄이 바뀌는지,
여러 번 고쳐도 무게 칸이 겹치지 않는지, 모델이 쓴 나머지 글은 그대로인지 본다.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[3] / ".github" / "scripts"

# 사람 항목이 열린 PR 설명과, 그 항목에 ✅를 단 PR 설명
OPEN_BODY = "## 확인해 주세요\n\n### 1. 범위\n\n- 누가 답하나: 사람\n"
DONE_BODY = "## 확인해 주세요\n\n### ✅ 1. 범위\n\n- 누가 답하나: 사람\n"
MODEL_TEXT = "[검증] 통과\n\n## 사람 확인 필요\n\n- 1번\n\n## 테스트\n\n- 통과"


@pytest.fixture(scope="module")
def rw():
    sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location("reweigh", SCRIPTS / "reweigh.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _judge(rw, body: str) -> dict:
    return rw.pr_weight.judge(["docs/x.md"], set(), body, set(), {})


def _posted(rw, body: str) -> str:
    """전체 검증이 처음 올린 코멘트처럼 만든다(post_verify가 하는 순서 그대로)."""
    return rw.post_verify.with_marker(rw.pr_weight.with_weight(MODEL_TEXT, _judge(rw, body)))


def test_description_fix_turns_heavy_into_light(rw):
    old = _posted(rw, OPEN_BODY)
    assert "무게: 무거움 (다)" in old.splitlines()[0]
    new = rw.reweigh_body(old, _judge(rw, DONE_BODY))
    assert new.splitlines()[0] == "[검증] 통과 / 무게: 가벼움"
    assert "기준 (가)~(라)에 걸린 것 없음" in new


def test_reweigh_twice_does_not_stack_sections(rw):
    once = rw.reweigh_body(_posted(rw, OPEN_BODY), _judge(rw, DONE_BODY))
    twice = rw.reweigh_body(once, _judge(rw, DONE_BODY))
    assert twice == once
    assert twice.count("### PR 무게 (기계 판정)") == 1
    assert twice.count(rw.post_verify.MARKER) == 1


def test_model_text_is_kept(rw):
    new = rw.reweigh_body(_posted(rw, OPEN_BODY), _judge(rw, DONE_BODY))
    for line in MODEL_TEXT.splitlines()[1:]:
        assert line in new.splitlines()


def test_light_to_heavy_also_updates(rw):
    new = rw.reweigh_body(_posted(rw, DONE_BODY), _judge(rw, OPEN_BODY))
    assert new.splitlines()[0].endswith("/ 무게: 무거움 (다)")
