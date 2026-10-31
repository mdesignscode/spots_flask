from pathlib import Path
from unittest.mock import patch

from spots_cli.utils.detect_js_runtimes import detect_js_runtimes

MODULE = "spots_cli.utils.detect_js_runtimes"


def which_from(found: dict[str, str]):
    return lambda name: found.get(name)


def test_lists_every_runtime_on_path_in_preference_order(tmp_path):
    found = {"node": "/usr/bin/node", "deno": "/usr/bin/deno"}
    with (
        patch(f"{MODULE}.shutil.which", side_effect=which_from(found)),
        patch(f"{MODULE}.Path.home", return_value=tmp_path),
    ):
        runtimes = detect_js_runtimes()

    assert list(runtimes) == ["deno", "node"]
    assert runtimes["deno"] == {"path": "/usr/bin/deno"}


def test_finds_bun_in_home_when_not_on_path(tmp_path):
    bun = tmp_path / ".bun" / "bin" / "bun"
    bun.parent.mkdir(parents=True)
    bun.touch()

    with (
        patch(f"{MODULE}.shutil.which", return_value=None),
        patch(f"{MODULE}.Path.home", return_value=tmp_path),
    ):
        runtimes = detect_js_runtimes()

    assert runtimes == {"bun": {"path": str(bun)}}


def test_nothing_found(tmp_path):
    with (
        patch(f"{MODULE}.shutil.which", return_value=None),
        patch(f"{MODULE}.Path.home", return_value=Path(tmp_path)),
    ):
        assert detect_js_runtimes() == {}
