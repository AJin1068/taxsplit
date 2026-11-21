"""--scenarios로 레포 밖 폴더(홀드아웃 모드)를 읽고, 틀린 파일은 파일 이름·칸과 함께 멈춘다."""

import json

from harness.fakes import DEFAULT_SCENARIOS, deps_for, factory, main_steps, sim_steps
from taxsplit.harness.__main__ import main
from taxsplit.harness.scoring import REPO_ROOT


def _copy(src: str, dst, **change) -> dict:
    data = json.loads((DEFAULT_SCENARIOS / f"{src}.json").read_text(encoding="utf-8"))
    data.update(change)
    (dst / f"{data['id']}.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data


def test_reads_folder_outside_repo(tmp_path) -> None:
    assert not tmp_path.is_relative_to(REPO_ROOT)
    data = _copy("v0-02", tmp_path, id="h-01", version="h1")
    out = tmp_path / "out" / "r.json"
    deps = deps_for(main_steps(data["household"]), sim_steps(data))
    code = main(
        ["run", "--scenarios", str(tmp_path), "--repeat", "1", "--out", str(out)], factory(deps)
    )
    assert code == 0
    result = json.loads(out.read_text(encoding="utf-8"))
    assert result["scenarios"] == {"folder": str(tmp_path), "versions": ["h1"], "ids": ["h-01"]}
    assert result["records"][0]["scenario_id"] == "h-01"


def _never_called(args):
    raise AssertionError("형식이 틀리면 클라이언트를 만들기 전에 멈춰야 한다")


def test_missing_field_stops_with_file_and_field(tmp_path, capsys) -> None:
    data = _copy("v0-02", tmp_path, id="h-01")
    del data["persona"]
    (tmp_path / "h-02.json").write_text(
        json.dumps({**data, "id": "h-02"}, ensure_ascii=False), encoding="utf-8"
    )
    code = main(["run", "--scenarios", str(tmp_path)], _never_called)
    assert code == 2
    err = capsys.readouterr().err
    assert "h-02.json" in err and "persona" in err


def test_broken_json_stops_with_file_name(tmp_path, capsys) -> None:
    (tmp_path / "bad.json").write_text("{ 깨진", encoding="utf-8")
    assert main(["run", "--scenarios", str(tmp_path)], _never_called) == 2
    assert "bad.json" in capsys.readouterr().err


def test_unknown_only_id_stops(tmp_path, capsys) -> None:
    _copy("v0-02", tmp_path, id="h-01")
    assert main(["run", "--scenarios", str(tmp_path), "--only", "h-09"], _never_called) == 2
    assert "h-09" in capsys.readouterr().err
