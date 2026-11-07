import json

import pytest

from taskgen_proto.cli import main


def test_demo_runs_offline(tmp_path, capsys):
    out = tmp_path / "demo"
    assert main(["demo", "--out", str(out)]) == 0
    report = json.loads((out / "report.json").read_text())
    assert report["slots_filled"] == 9 and report["rejected"] == 7
    assert "fixture agrees with pipeline" in capsys.readouterr().out
    # rerunning into a directory this tool created is allowed
    assert main(["generate", "--out", str(out)]) == 0


def test_refuses_to_clobber_foreign_directory(tmp_path):
    (tmp_path / "keep.txt").write_text("mine")
    with pytest.raises(FileExistsError):
        main(["generate", "--out", str(tmp_path)])
    assert (tmp_path / "keep.txt").read_text() == "mine"
