"""성질 테스트: 가상 가구 1,000개 × 성질 5개. 어기면 시드와 단계를 보여 주고 실패한다.

어긴 가구가 나와도 엔진을 고쳐 맞추거나 가구를 빼지 않는다(Issue #16 하지 않을 것).
"""

import pytest

from property.checks import PROPERTIES


@pytest.mark.parametrize("prop", sorted(PROPERTIES))
def test_property_holds(prop, violations):
    bad = [v for v in violations if v.prop == prop]
    shown = "\n".join(f"seed={v.seed} {v.who} {v.stage}: {v.detail}" for v in bad[:20])
    assert not bad, f"성질 {prop}({PROPERTIES[prop]}) 위반 {len(bad)}건\n{shown}"
