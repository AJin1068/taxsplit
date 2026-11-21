"""답 외우기 검사: 처리 코드(agent/src/)와 프롬프트에 시나리오 id·부양가족 이름이 없어야 한다."""

from harness.memorize import leaks, secrets_of
from taxsplit.harness.scoring import REPO_ROOT

SCENARIOS_ROOT = REPO_ROOT / "eval" / "scenarios"
SRC = REPO_ROOT / "agent" / "src"


def test_source_and_prompts_do_not_contain_scenario_answers() -> None:
    secrets = secrets_of(SCENARIOS_ROOT)
    assert "v0-01" in secrets and len(secrets) > 10
    found = leaks(SRC, secrets)
    assert found == [], f"처리 코드·프롬프트에 시나리오 id·부양가족 이름이 있습니다: {found}"


def test_catches_planted_id_and_name(tmp_path) -> None:
    secrets = secrets_of(SCENARIOS_ROOT)
    name = sorted(s for s in secrets if not s.startswith("v0-"))[0]
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "cheat.py").write_text('IF_ID = "v0-03"\n')
    (tmp_path / "pkg" / "prompt.md").write_text(
        f"{name} 님은 남편 쪽에 넣으세요.\n", encoding="utf-8"
    )
    assert leaks(tmp_path, secrets) == ["pkg/cheat.py: v0-03", f"pkg/prompt.md: {name}"]


def test_does_not_catch_allowed_things(tmp_path) -> None:
    secrets = secrets_of(SCENARIOS_ROOT)
    # 일반 낱말, 기본 경로의 폴더 이름(v0)은 잡지 않는다
    (tmp_path / "ok.py").write_text(
        'WORDS = ["어머니", "자녀", "남편"]\nDEFAULT = "eval/scenarios/v0"\n'
    )
    assert leaks(tmp_path, secrets) == []
    # 테스트 코드 안의 시나리오 id는 검사 대상(agent/src/)이 아니다
    assert not (REPO_ROOT / "agent" / "tests").is_relative_to(SRC)
    assert leaks(SRC, {"v0-02"}) == []
