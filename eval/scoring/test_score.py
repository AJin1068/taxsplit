"""채점 코드·시나리오 형식 테스트. 실행: python3 eval/scoring/test_score.py (표준 라이브러리만)."""

import copy
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import score  # noqa: E402

V0 = HERE.parent / "scenarios" / "v0"
V1 = HERE.parent / "scenarios" / "v1"


def scenario() -> dict:
    """테스트용 작은 시나리오(v0 파일과 이름·값이 다름)."""
    return {
        "id": "t-01",
        "version": "test",
        "status": "confirmed",
        "title": "테스트",
        "groups": ["dependent", "child"],
        "household": {
            "members": [
                {"dependent": {"name": "가나", "relation": "lineal_ascendant", "birth_year": 1950}},
                {"dependent": {"name": "다라", "relation": "child", "birth_year": 2015}},
            ]
        },
        "documents": [{}, {}],
        "opening": "시작",
        "persona": "보통",
        "facts": [
            {"id": "f1", "kind": "must_ask", "text": "가나 소득 없음"},
            {"id": "f2", "kind": "may_assume", "text": "다라 소득 없음"},
            {"id": "f3", "kind": "must_ask", "text": "다라 의료비는 아내가 냄"},
        ],
        "gold": {
            "plan_count": 4,
            "best_assignments": [
                {"가나": "husband", "다라": "wife"},
                {"가나": "husband", "다라": "husband"},
            ],
            "best_total": 1000,
            "plans": [
                {"assignment": {"가나": "husband", "다라": "wife"}, "total": 1000},
                {"assignment": {"가나": "husband", "다라": "husband"}, "total": 1000},
                {"assignment": {"가나": "wife", "다라": "wife"}, "total": 1300},
                {"assignment": {"가나": "wife", "다라": "husband"}, "total": 1500},
            ],
            "headline_saving": 300,
            "members": [
                {"name": "가나", "relation": "lineal_ascendant", "birth_year": 1950},
                {"name": "다라", "relation": "child", "birth_year": 2015},
            ],
        },
    }


def record(**kw) -> dict:
    base = {
        "scenario_id": "t-01",
        "repeat": 1,
        "ended": "answered",
        "turns": 3,
        "transcript": [],
        "revealed": ["f1", "f3"],
        "tool_calls": [
            {"tool": "check_eligibility", "status": "ok", "errors": []},
            {"tool": "compare_allocations", "status": "ok", "errors": []},
        ],
        "final": {
            "assignment": {"어머님": "husband", "첫째": "wife"},
            "members": [
                {"name": "어머님", "relation": "lineal_ascendant", "birth_year": 1950},
                {"name": "첫째", "relation": "child", "birth_year": 2015},
            ],
        },
        "cost": {"main_agent_usd": 0.10, "sim_user_usd": 0.01, "judge_usd": None},
        "judge": None,
    }
    base.update(kw)
    return base


class MatchTest(unittest.TestCase):
    def test_other_names_still_match(self):
        # 잡으면 안 되는 것 1: 이름 표기가 달라도 (관계, 출생연도)로 짝짓는다
        r = score.score_run(scenario(), record())
        self.assertTrue(r["match"])
        self.assertEqual(r["missed_won"], 0)

    def test_any_tied_best_matches(self):
        # 잡으면 안 되는 것 2: 최적안이 여럿이면 그중 하나
        rec = record(
            final={**record()["final"], "assignment": {"어머님": "husband", "첫째": "husband"}}
        )
        self.assertTrue(score.score_run(scenario(), rec)["match"])

    def test_wrong_side_is_mismatch_with_missed_amount(self):
        rec = record(final={**record()["final"], "assignment": {"어머님": "wife", "첫째": "wife"}})
        r = score.score_run(scenario(), rec)
        self.assertFalse(r["match"])
        self.assertEqual(r["missed_won"], 300)

    def test_missing_dependent_is_mismatch_unknown_amount(self):
        # 요건이 되는 가족을 빼먹은 안: 기준 정답 plans에 없어 놓친 금액은 알 수 없음
        final = {
            "assignment": {"첫째": "wife"},
            "members": [{"name": "첫째", "relation": "child", "birth_year": 2015}],
        }
        r = score.score_run(scenario(), record(final=final))
        self.assertFalse(r["match"])
        self.assertIsNone(r["missed_won"])

    def test_unknown_member_key_is_mismatch(self):
        final = {
            "assignment": {"어머님": "husband", "첫째": "wife"},
            "members": [
                {"name": "어머님", "relation": "lineal_ascendant", "birth_year": 1951},
                {"name": "첫째", "relation": "child", "birth_year": 2015},
            ],
        }
        self.assertFalse(score.score_run(scenario(), record(final=final))["match"])

    def test_no_final_is_mismatch(self):
        r = score.score_run(scenario(), record(final=None, ended="stopped"))
        self.assertFalse(r["match"])
        self.assertIsNone(r["missed_won"])


class QuestionTest(unittest.TestCase):
    def test_missed_must_ask_counted(self):
        r = score.score_run(scenario(), record(revealed=["f1"]))
        self.assertEqual(r["missed_facts"], ["f3"])
        self.assertEqual(r["must_ask"], 2)

    def test_may_assume_not_asked_is_fine(self):
        # 잡으면 안 되는 것 3: 짐작해도 되는 사실(f2)을 묻지 않아도 감점 없음
        r = score.score_run(scenario(), record(revealed=["f1", "f3"]))
        self.assertEqual(r["missed_facts"], [])

    def test_volunteered_counts_as_revealed(self):
        # 잡으면 안 되는 것 4: 사용자가 먼저 말해 준 것도 "알려 줌"(실행기가 revealed에 넣음)
        r = score.score_run(scenario(), record(revealed=["f3", "f1"]))
        self.assertEqual(r["missed_facts"], [])


class SummaryTest(unittest.TestCase):
    def test_rates_and_groups(self):
        s = scenario()
        bad = record(
            repeat=2,
            revealed=["f1"],
            final={**record()["final"], "assignment": {"어머님": "wife", "첫째": "wife"}},
            tool_calls=[
                {"tool": "compare_allocations", "status": "order_violation", "errors": []},
                {"tool": "check_eligibility", "status": "invalid_args", "errors": ["x"]},
                {"tool": "check_eligibility", "status": "ok", "errors": []},
                {"tool": "compare_allocations", "status": "ok", "errors": []},
            ],
        )
        out = score.summarize([s], [record(), bad])
        o = out["overall"]
        self.assertEqual(o["conversations"], 2)
        self.assertAlmostEqual(o["match_rate"], 0.5)
        self.assertAlmostEqual(o["missed_question_rate"], 1 / 4)
        self.assertAlmostEqual(o["invalid_args_rate"], 1 / 6)
        self.assertEqual(o["order_violations"], 1)
        self.assertAlmostEqual(o["cost_per_conversation_usd"], 0.10)
        self.assertEqual(set(out["by_group"]), {"dependent", "child"})

    def test_draft_scenarios_not_scored(self):
        s = scenario()
        s["status"] = "draft"
        out = score.summarize([s], [record()])
        self.assertEqual(out["overall"]["conversations"], 0)
        self.assertEqual(out["skipped_draft"], ["t-01"])

    def test_unknown_cost_stays_unknown(self):
        rec = record(cost={"main_agent_usd": None, "sim_user_usd": None, "judge_usd": None})
        out = score.summarize([scenario()], [rec])
        self.assertIsNone(out["overall"]["cost_per_conversation_usd"])


def gap_scenario() -> dict:
    """빈 곳 알림 정답이 있는 테스트 시나리오(v1 파일과 이름·값이 다름)."""
    s = scenario()
    s["gaps_expected"] = {
        "show": [
            {
                "id": "gap.adult_no_consent",
                "member": {"relation": "lineal_ascendant", "birth_year": 1950},
            },
            {"id": "gap.field_trip", "member": None},
        ],
        "not_show": [
            {"id": "gap.child_turned_adult", "member": {"relation": "child", "birth_year": 2015}},
            {"id": "gap.preschool_academy", "member": None},
        ],
    }
    return s


class GapTest(unittest.TestCase):
    def test_no_expected_or_no_record_field_is_none(self):
        # 정답이 없는 시나리오(v0), gaps를 남기지 않는 실행기 기록은 빈 곳 숫자를 내지 않는다
        self.assertIsNone(score.score_run(scenario(), record(gaps=[]))["gaps"])
        self.assertIsNone(score.score_run(gap_scenario(), record())["gaps"])

    def test_hit_with_parent_relation_mapped(self):
        # 빈 곳 찾기는 부모를 parent라 부른다. 시나리오 말(lineal_ascendant)로 맞춘다
        shown = [
            {"id": "gap.adult_no_consent", "member": {"relation": "parent", "birth_year": 1950}},
            {"id": "gap.field_trip", "member": {"relation": "child", "birth_year": 2015}},
        ]
        g = score.score_run(gap_scenario(), record(gaps=shown))["gaps"]
        self.assertEqual(g["hit"], ["gap.adult_no_consent", "gap.field_trip"])
        self.assertEqual(g["false_alarm"], [])

    def test_wrong_member_is_not_hit(self):
        shown = [
            {"id": "gap.adult_no_consent", "member": {"relation": "parent", "birth_year": 1951}}
        ]
        g = score.score_run(gap_scenario(), record(gaps=shown))["gaps"]
        self.assertEqual(g["hit"], [])

    def test_card_without_member_does_not_hit_member_answer(self):
        # 누구 일인지 모르는 카드는 "그 가족" 정답에 맞히지 않는다(아무나 맞힌 것으로 보지 않음)
        shown = [{"id": "gap.adult_no_consent", "member": None}]
        g = score.score_run(gap_scenario(), record(gaps=shown))["gaps"]
        self.assertEqual(g["hit"], [])

    def test_false_alarms(self):
        shown = [
            {"id": "gap.child_turned_adult", "member": {"relation": "child", "birth_year": 2015}},
            {"id": "gap.preschool_academy", "member": {"relation": "child", "birth_year": 2021}},
        ]
        g = score.score_run(gap_scenario(), record(gaps=shown))["gaps"]
        self.assertEqual(g["false_alarm"], ["gap.child_turned_adult", "gap.preschool_academy"])

    def test_other_child_is_not_false_alarm(self):
        # 잡으면 안 되는 것: 다른 가족의 같은 카드는 오알림이 아니다
        shown = [
            {"id": "gap.child_turned_adult", "member": {"relation": "child", "birth_year": 2006}}
        ]
        g = score.score_run(gap_scenario(), record(gaps=shown))["gaps"]
        self.assertEqual(g["false_alarm"], [])

    def test_summary_numbers_and_by_gap(self):
        s = gap_scenario()
        good = [
            {"id": "gap.adult_no_consent", "member": {"relation": "parent", "birth_year": 1950}},
            {"id": "gap.field_trip", "member": None},
        ]
        bad = [{"id": "gap.preschool_academy", "member": None}]
        out = score.summarize(
            [s], [record(gaps=good), record(repeat=2, gaps=bad), record(repeat=3)]
        )
        self.assertAlmostEqual(out["overall"]["gap_hit_rate"], 2 / 4)
        self.assertEqual(out["overall"]["gap_false_alarms"], 1)
        self.assertEqual(
            out["by_gap"]["gap.adult_no_consent"], {"expected": 2, "hit": 1, "false_alarm": 0}
        )
        self.assertEqual(
            out["by_gap"]["gap.preschool_academy"], {"expected": 0, "hit": 0, "false_alarm": 1}
        )

    def test_v0_summary_has_no_gap_numbers(self):
        out = score.summarize([scenario()], [record()])
        self.assertIsNone(out["overall"]["gap_hit_rate"])
        self.assertEqual(out["by_gap"], {})

    def test_bad_gaps_expected_rejected(self):
        s = gap_scenario()
        s["gaps_expected"]["show"].append({"id": "adult_no_consent", "member": {"relation": "x"}})
        errs = score.check_scenario(s)
        self.assertTrue(any("id" in e for e in errs))
        self.assertTrue(any("member" in e for e in errs))


class BaselineTest(unittest.TestCase):
    def overall(self, **kw):
        base = {
            "match_rate": 0.8,
            "missed_question_rate": 0.2,
            "invalid_args_rate": 0.1,
            "order_violations": 1,
            "cost_per_conversation_usd": 0.10,
        }
        base.update(kw)
        return {"overall": base}

    def test_same(self):
        r = score.compare_to_baseline(self.overall(), self.overall())
        self.assertEqual(r["verdict"], "같음 또는 좋아짐")
        self.assertFalse(r["cost_warning"])

    def test_match_drop_10pp(self):
        r = score.compare_to_baseline(self.overall(match_rate=0.7), self.overall())
        self.assertEqual(r["verdict"], "떨어짐")

    def test_match_drop_less_than_10pp(self):
        r = score.compare_to_baseline(self.overall(match_rate=0.71), self.overall())
        self.assertEqual(r["verdict"], "같음 또는 좋아짐")

    def test_missed_and_invalid_rise(self):
        r = score.compare_to_baseline(self.overall(missed_question_rate=0.3), self.overall())
        self.assertEqual(r["verdict"], "떨어짐")
        r = score.compare_to_baseline(self.overall(invalid_args_rate=0.2), self.overall())
        self.assertEqual(r["verdict"], "떨어짐")

    def test_cost_warning_only(self):
        r = score.compare_to_baseline(self.overall(cost_per_conversation_usd=0.16), self.overall())
        self.assertEqual(r["verdict"], "같음 또는 좋아짐")
        self.assertTrue(r["cost_warning"])


class ScenarioFilesTest(unittest.TestCase):
    """eval/scenarios/v0/ 실제 파일 검사."""

    def setUp(self):
        self.files = sorted(V0.glob("*.json"))
        self.data = [json.loads(p.read_text(encoding="utf-8")) for p in self.files]

    def test_ten_files_pass_format(self):
        self.assertEqual(len(self.files), 10)
        for p, d in zip(self.files, self.data, strict=True):
            self.assertEqual(score.check_scenario(d), [], p.name)
            self.assertEqual(p.stem, d["id"])

    def test_each_group_has_three(self):
        for g in score.GROUPS:
            n = sum(1 for d in self.data if g in d["groups"])
            self.assertGreaterEqual(n, 3, g)

    def test_dependent_names_unique_across_scenarios(self):
        names = [
            m["dependent"]["name"] for d in self.data for m in d["household"].get("members", [])
        ]
        self.assertEqual(len(names), len(set(names)))

    def test_gold_matches_household_members(self):
        for d in self.data:
            names = [m["dependent"]["name"] for m in d["household"].get("members", [])]
            self.assertEqual([m["name"] for m in d["gold"]["members"]], names, d["id"])
            self.assertEqual(len(d["gold"]["plans"]), d["gold"]["plan_count"], d["id"])

    def test_documents_do_not_reveal_payer_income_disability(self):
        # 간소화 자료에는 누가 냈나·부양가족 소득·장애 여부가 없다(Issue #109)
        for d in self.data:
            text = json.dumps(d["documents"], ensure_ascii=False)
            for word in ("payer", "income", "disabled", "wage_only_gross"):
                self.assertNotIn(word, text, d["id"])

    def test_gold_is_fixed_point_of_copy(self):
        # load_scenarios가 읽어도 파일 내용이 바뀌지 않는다(읽기 전용)
        before = copy.deepcopy(self.data)
        score.load_scenarios(V0)
        self.assertEqual(before, [json.loads(p.read_text(encoding="utf-8")) for p in self.files])

    def test_load_scenarios_reports_file_name(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "bad.json").write_text('{"id": "x"}', encoding="utf-8")
            with self.assertRaises(ValueError) as ctx:
                score.load_scenarios(tmp)
            self.assertIn("bad.json", str(ctx.exception))


class V1FilesTest(unittest.TestCase):
    """eval/scenarios/v1/ 실제 파일 검사(간소화에 안 나오는 가족 경우, Issue #127)."""

    def setUp(self):
        self.files = sorted(V1.glob("*.json"))
        self.data = [json.loads(p.read_text(encoding="utf-8")) for p in self.files]

    def test_files_pass_format_and_have_gap_answers(self):
        self.assertGreaterEqual(len(self.files), 4)
        for p, d in zip(self.files, self.data, strict=True):
            self.assertEqual(score.check_scenario(d), [], p.name)
            self.assertEqual(p.stem, d["id"])
            self.assertEqual(d["version"], "v1")
            self.assertIn("gaps_expected", d, p.name)

    def test_has_a_household_with_nothing_to_alert(self):
        # 놓칠 게 없는 가구: 알려야 할 것은 없고 알리면 안 되는 것만 있다
        quiet = [d for d in self.data if not d["gaps_expected"]["show"]]
        self.assertTrue(quiet)
        self.assertTrue(all(d["gaps_expected"]["not_show"] for d in quiet))

    def test_names_unique_across_v0_and_v1(self):
        names = []
        for folder in (V0, V1):
            for p in sorted(folder.glob("*.json")):
                d = json.loads(p.read_text(encoding="utf-8"))
                names += list(d["spouse_names"].values())
                names += [m["dependent"]["name"] for m in d["household"].get("members", [])]
        self.assertEqual(len(names), len(set(names)))

    def test_gold_matches_household_members(self):
        for d in self.data:
            names = [m["dependent"]["name"] for m in d["household"].get("members", [])]
            self.assertEqual([m["name"] for m in d["gold"]["members"]], names, d["id"])
            self.assertEqual(len(d["gold"]["plans"]), d["gold"]["plan_count"], d["id"])

    def test_documents_do_not_reveal_payer_income_disability(self):
        for d in self.data:
            text = json.dumps(d["documents"], ensure_ascii=False)
            for word in ("payer", "income", "disabled", "wage_only_gross", "infertility"):
                self.assertNotIn(word, text, d["id"])

    def test_gap_answers_name_real_gap_ids(self):
        # 정답의 항목 ID는 빈 곳 찾기 질문 표에 있는 것만
        table = (HERE.parent.parent / "agent/src/taxsplit/gaps/questions_2025.toml").read_text(
            encoding="utf-8"
        )
        for d in self.data:
            for side in ("show", "not_show"):
                for e in d["gaps_expected"][side]:
                    self.assertIn(f'id = "{e["id"]}"', table, d["id"])


if __name__ == "__main__":
    unittest.main(verbosity=1)
