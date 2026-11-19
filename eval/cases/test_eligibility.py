"""`eligibility.py` 검사 자체가 빠진 줄·잘못된 줄을 잡는지 보는 테스트.

    python3 eval/cases/test_eligibility.py

표준 라이브러리만 쓴다. 실제 사례 파일 하나를 읽어 일부러 망가뜨린 사본으로 검사한다.
"""

import copy
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from eligibility import check_eligibility, expense_paths  # noqa: E402

NTS = HERE / "nts-2025" / "item-p185-education.json"
HOMETAX = HERE / "hometax-2025" / "household2-plan-b.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class EligibilityCheck(unittest.TestCase):
    def setUp(self):
        self.case = load(NTS)

    def test_real_files_pass(self):
        for path in sorted(HERE.glob("*/*.json")):
            with self.subTest(path.name):
                self.assertEqual(check_eligibility(load(path)), [])

    def test_missing_row_fails(self):
        case = copy.deepcopy(self.case)
        removed = case["eligibility"]["rows"].pop(2)
        errs = check_eligibility(case)
        self.assertTrue(any(removed["path"] in e and "없음" in e for e in errs), errs)

    def test_missing_block_fails_when_rows_exist(self):
        case = copy.deepcopy(self.case)
        del case["eligibility"]
        self.assertTrue(check_eligibility(case))

    def test_not_deductible_needs_filter(self):
        case = copy.deepcopy(self.case)
        row = next(r for r in case["eligibility"]["rows"] if r["deductible"] is False)
        del row["filtered_by"]
        self.assertTrue(any("filtered_by" in e for e in check_eligibility(case)))

    def test_path_must_exist_and_be_expense(self):
        case = copy.deepcopy(self.case)
        case["eligibility"]["rows"].append(
            {"path": "/gross_salary", "deductible": True, "page": 185, "text": "x"}
        )
        self.assertTrue(any("지출 줄이 아님" in e for e in check_eligibility(case)))

    def test_page_must_be_in_source(self):
        case = copy.deepcopy(self.case)
        case["eligibility"]["rows"][0]["page"] = 999
        self.assertTrue(any(".page" in e for e in check_eligibility(case)))

    def test_hometax_has_no_page(self):
        case = load(HOMETAX)
        case["eligibility"]["rows"][0]["page"] = 389
        self.assertTrue(any("page" in e for e in check_eligibility(case)))

    def test_card_only_case_needs_nothing(self):
        case = load(HERE / "nts-2025" / "item-p137-card.json")
        self.assertEqual(expense_paths(case), [])
        self.assertEqual(check_eligibility(case), [])

    def test_confirmed_needs_reviewer(self):
        case = copy.deepcopy(self.case)
        case["eligibility"]["status"] = "confirmed"
        self.assertTrue(any("reviewer" in e for e in check_eligibility(case)))


if __name__ == "__main__":
    unittest.main()
