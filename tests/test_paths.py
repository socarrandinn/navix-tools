from pathlib import Path

from ipswitch.config import default_config_path
from ipswitch.helper import results_dir, runtime_dir
from ipswitch.install import install_dir
from ipswitch.paths import FOLDERID_PROGRAM_DATA, known_folder


def test_known_folder_program_data():
    assert known_folder(FOLDERID_PROGRAM_DATA).name.lower() == "programdata"


def test_paths_ignore_user_environment(monkeypatch, tmp_path):
    for name in ("ProgramData", "LOCALAPPDATA", "ProgramFiles", "ProgramW6432", "APPDATA"):
        monkeypatch.setenv(name, str(tmp_path))
    for path in (default_config_path(), runtime_dir(), results_dir(), install_dir()):
        assert tmp_path not in path.parents, path


def test_results_live_next_to_admin_config():
    assert results_dir() == default_config_path().parent / "results"


def test_install_dir_is_under_program_files():
    assert install_dir().parent.name.lower() == "program files"
    assert install_dir().name == "ipswitch"
    assert isinstance(install_dir(), Path)
