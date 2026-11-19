"""기준 정답 스크립트 테스트. 계산 엔진이 필요해 agent/에서 돌린다:
cd agent && uv run python ../eval/scenarios/test_make_gold.py
"""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import make_gold  # noqa: E402


class MakeGoldTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        for p in (HERE / "v0").glob("*.json"):
            shutil.copy(p, self.tmp / p.name)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def snapshot(self):
        return {p.name: p.read_text(encoding="utf-8") for p in sorted(self.tmp.glob("*.json"))}

    def test_same_input_same_output(self):
        args = ["--scenarios", str(self.tmp), "--engine-commit", "abc123"]
        self.assertEqual(make_gold.main(args), 0)
        first = self.snapshot()
        self.assertEqual(make_gold.main(args), 0)
        self.assertEqual(first, self.snapshot())
        self.assertEqual(make_gold.main([*args, "--check"]), 0)

    def test_confirmed_gold_not_overwritten(self):
        path = self.tmp / "v0-01.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["status"] = "confirmed"
        data["gold"]["best_total"] += 1  # 엔진 결과와 일부러 다르게
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        before = path.read_text(encoding="utf-8")
        code = make_gold.main(["--scenarios", str(self.tmp), "--engine-commit", "abc123"])
        self.assertEqual(code, 1)
        self.assertEqual(before, path.read_text(encoding="utf-8"))

    def test_confirmed_same_gold_passes_with_new_commit(self):
        path = self.tmp / "v0-02.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["status"] = "confirmed"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        code = make_gold.main(["--scenarios", str(self.tmp), "--engine-commit", "other"])
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main(verbosity=1)
