from __future__ import annotations

import importlib.machinery
import types
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def load_launcher():
    module = types.ModuleType("pdf2wordx_launcher")
    module.__file__ = str(ROOT / "run.pyw")
    loader = importlib.machinery.SourceFileLoader(module.__name__, module.__file__)
    loader.exec_module(module)
    return module


class LauncherTests(unittest.TestCase):
    def test_launcher_uses_only_standard_library_before_bootstrap(self) -> None:
        launcher = load_launcher()
        self.assertTrue(callable(launcher.main))
        self.assertEqual(launcher.REQUIREMENTS, ROOT / "requirements.txt")

    def test_ready_dependencies_launch_application_directly(self) -> None:
        launcher = load_launcher()
        with (
            patch.object(launcher, "_dependencies_available", return_value=True),
            patch.object(launcher, "_launch_app") as launch,
            patch.object(launcher, "_show_setup_window") as setup,
        ):
            launcher.main()
        launch.assert_called_once_with()
        setup.assert_not_called()

    def test_existing_local_environment_is_reused(self) -> None:
        launcher = load_launcher()
        with TemporaryDirectory() as temp_dir:
            fake_python = Path(temp_dir) / "python.exe"
            fake_python.touch()
            with (
                patch.object(launcher, "_dependencies_available", return_value=False),
                patch.object(launcher, "_running_in_local_venv", return_value=False),
                patch.object(launcher, "_venv_executable", return_value=fake_python),
                patch.object(launcher, "_restart_with_local_venv") as restart,
                patch.object(launcher, "_show_setup_window") as setup,
            ):
                launcher.main()
        restart.assert_called_once_with()
        setup.assert_not_called()

    def test_missing_environment_opens_first_run_setup(self) -> None:
        launcher = load_launcher()
        with TemporaryDirectory() as temp_dir:
            missing_python = Path(temp_dir) / "python.exe"
            with (
                patch.object(launcher, "_dependencies_available", return_value=False),
                patch.object(launcher, "_running_in_local_venv", return_value=False),
                patch.object(launcher, "_venv_executable", return_value=missing_python),
                patch.object(launcher, "_restart_with_local_venv") as restart,
                patch.object(launcher, "_show_setup_window") as setup,
            ):
                launcher.main()
        setup.assert_called_once_with()
        restart.assert_not_called()


if __name__ == "__main__":
    unittest.main()
