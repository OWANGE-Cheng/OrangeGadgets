from __future__ import annotations

import importlib.util
import os
import queue
import subprocess
import sys
import tempfile
import threading
import traceback
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SOURCE_DIR = ROOT / "src"
VENV_DIR = ROOT / ".venv"
REQUIREMENTS = ROOT / "requirements.txt"
CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def _venv_executable(*, windowed: bool) -> Path:
    if os.name == "nt":
        name = "pythonw.exe" if windowed else "python.exe"
        return VENV_DIR / "Scripts" / name
    return VENV_DIR / "bin" / "python"


def _console_python() -> Path:
    executable = Path(sys.executable)
    if os.name == "nt" and executable.name.lower() == "pythonw.exe":
        return executable.with_name("python.exe")
    return executable


def _log_path() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    preferred = base / "OrangeGadgets" / "pdf2wordx" / "setup.log"
    try:
        preferred.parent.mkdir(parents=True, exist_ok=True)
        return preferred
    except OSError:
        fallback = Path(tempfile.gettempdir()) / "OrangeGadgets" / "pdf2wordx-setup.log"
        fallback.parent.mkdir(parents=True, exist_ok=True)
        return fallback


def _write_log(content: str) -> Path:
    path = _log_path()
    path.write_text(content, encoding="utf-8", errors="replace")
    return path


def _dependencies_available() -> bool:
    return importlib.util.find_spec("pdf2docx") is not None


def _running_in_local_venv() -> bool:
    try:
        return Path(sys.prefix).resolve() == VENV_DIR.resolve()
    except OSError:
        return False


def _restart_with_local_venv() -> None:
    pythonw = _venv_executable(windowed=True)
    python = _venv_executable(windowed=False)
    executable = pythonw if pythonw.is_file() else python
    subprocess.Popen(
        [str(executable), str(Path(__file__).resolve())],
        cwd=str(ROOT),
        creationflags=CREATE_NO_WINDOW,
    )


def _show_setup_window() -> None:
    import tkinter as tk
    from tkinter import messagebox, ttk

    root = tk.Tk()
    root.title("PDF2WORDX 首次启动")
    root.geometry("520x210")
    root.resizable(False, False)

    frame = ttk.Frame(root, padding=24)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="正在准备 PDF2WORDX", font=("Microsoft YaHei UI", 15, "bold")).pack(
        anchor="w"
    )
    status = ttk.Label(
        frame,
        text="首次启动需要创建本地运行环境并安装转换组件。\n这通常需要一到数分钟，请保持网络连接。",
        font=("Microsoft YaHei UI", 10),
        justify="left",
    )
    status.pack(anchor="w", pady=(12, 18))
    progress = ttk.Progressbar(frame, mode="indeterminate")
    progress.pack(fill="x")
    progress.start(12)

    result_queue: queue.Queue[tuple[bool, str, Path | None]] = queue.Queue()

    def install() -> None:
        output: list[str] = []
        try:
            venv_python = _venv_executable(windowed=False)
            if not venv_python.is_file():
                command = [str(_console_python()), "-m", "venv", str(VENV_DIR)]
                completed = subprocess.run(
                    command,
                    cwd=str(ROOT),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    creationflags=CREATE_NO_WINDOW,
                    check=False,
                )
                output.extend(["$ " + " ".join(command), completed.stdout, completed.stderr])
                if completed.returncode:
                    raise RuntimeError("创建本地 Python 环境失败。")

            command = [
                str(venv_python),
                "-m",
                "pip",
                "install",
                "-r",
                str(REQUIREMENTS),
            ]
            completed = subprocess.run(
                command,
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=CREATE_NO_WINDOW,
                check=False,
            )
            output.extend(["$ " + " ".join(command), completed.stdout, completed.stderr])
            log_path = _write_log("\n".join(output))
            if completed.returncode:
                raise RuntimeError("安装转换组件失败。")
            result_queue.put((True, "运行环境准备完成。", log_path))
        except Exception as exc:
            output.append(traceback.format_exc())
            try:
                log_path = _write_log("\n".join(output))
            except OSError:
                log_path = None
            result_queue.put((False, str(exc), log_path))

    def poll_result() -> None:
        try:
            success, message, log_path = result_queue.get_nowait()
        except queue.Empty:
            root.after(120, poll_result)
            return

        progress.stop()
        if success:
            status.configure(text="准备完成，正在启动 PDF2WORDX……")
            root.after(350, finish_and_restart)
            return

        status.configure(text="运行环境准备失败。")
        detail = message
        if log_path is not None:
            detail += f"\n\n详细日志：\n{log_path}"
        messagebox.showerror("PDF2WORDX 启动失败", detail, parent=root)
        ttk.Button(frame, text="关闭", command=root.destroy).pack(anchor="e", pady=(14, 0))

    def finish_and_restart() -> None:
        try:
            _restart_with_local_venv()
        except Exception:
            log_path = _write_log(traceback.format_exc())
            messagebox.showerror(
                "PDF2WORDX 启动失败",
                f"无法启动本地运行环境。\n\n详细日志：\n{log_path}",
                parent=root,
            )
            return
        root.destroy()

    threading.Thread(target=install, daemon=True).start()
    root.after(120, poll_result)
    root.mainloop()


def _show_startup_error() -> None:
    import tkinter as tk
    from tkinter import messagebox

    try:
        log_path = _write_log(traceback.format_exc())
    except OSError:
        log_path = None
    root = tk.Tk()
    root.withdraw()
    detail = "PDF2WORDX 无法启动。"
    if log_path is not None:
        detail += f"\n\n详细日志：\n{log_path}"
    messagebox.showerror("PDF2WORDX 启动失败", detail, parent=root)
    root.destroy()


def _launch_app() -> None:
    sys.path.insert(0, str(SOURCE_DIR))
    from pdf2wordx import run

    run()


def main() -> None:
    try:
        if _dependencies_available():
            _launch_app()
            return

        local_python = _venv_executable(windowed=False)
        if not _running_in_local_venv() and local_python.is_file():
            _restart_with_local_venv()
            return

        _show_setup_window()
    except Exception:
        _show_startup_error()


if __name__ == "__main__":
    main()
