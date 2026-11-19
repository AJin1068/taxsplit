"""가상 가구 생성기: 시드로 맞벌이 가구를 만든다(성질 테스트, 평가 하네스 PR 11에서 씀)."""

from taxsplit.synth.household import SPOUSES, SynthHousehold, make_household, make_households

__all__ = ["SPOUSES", "SynthHousehold", "make_household", "make_households"]
