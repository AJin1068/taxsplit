"""'공제 대상이 아닌 지출' 목록은 규칙표에서 읽는다(설계 원칙 5)."""

from pathlib import Path

import taxsplit.extract
from taxsplit.extract.prompt import build_system_prompt
from taxsplit.rules.loader import EXCLUDED_SUFFIX, load_rules

EXTRACT_DIR = Path(taxsplit.extract.__file__).parent


def _excluded_names() -> list[str]:
    rules = load_rules(2025)
    names = [i.name for r in rules.values() if r.id.endswith(EXCLUDED_SUFFIX) for i in r.items]
    assert names, "규칙표에 공제 대상이 아닌 지출 목록이 있어야 한다"
    return names


def test_list_strings_are_not_in_extract_code():
    source = "\n".join(p.read_text(encoding="utf-8") for p in EXTRACT_DIR.glob("*.py"))
    found = [name for name in _excluded_names() if name in source]
    assert found == []


def test_prompt_contains_every_list_item_from_rule_table():
    prompt = build_system_prompt()
    missing = [name for name in _excluded_names() if name not in prompt]
    assert missing == []


def test_prompt_follows_rule_table_changes():
    # 규칙표 내용을 바꾸면 지시문도 바뀐다 = 지시문이 규칙표에서 읽는다
    rules = load_rules(2025)
    rule_id = next(r for r in rules if r.endswith(EXCLUDED_SUFFIX))
    rule = rules[rule_id]
    new_item = rule.items[0].model_copy(update={"name": "규칙표에서 온 새 항목"})
    changed = {**rules, rule_id: rule.model_copy(update={"items": (new_item,)})}
    assert "규칙표에서 온 새 항목" in build_system_prompt(changed)
    assert "규칙표에서 온 새 항목" not in build_system_prompt(rules)
