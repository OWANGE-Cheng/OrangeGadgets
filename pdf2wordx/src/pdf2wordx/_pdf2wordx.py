from __future__ import annotations

import ctypes
from pathlib import Path
from queue import Empty, Queue
from threading import Thread
from tkinter import Button, Entry, Label, TclError, Tk, messagebox, ttk
from typing import Any

from .files import functions as funcs
from .files import interfaz as win
from .files.logging_utils import get_logger


PACKAGE_DIR = Path(__file__).resolve().parent
INFO_DIR = PACKAGE_DIR / "files" / "info"


logger = get_logger(__name__)


class App(win.Window):
    def __init__(
        self,
        root: Tk,
        width: int = 580,
        height: int = 410,
        bg_color: str = "#001223",
        title: str = "PDF2WORDX（简体中文版）",
        resizable: tuple[bool, bool] = (False, False),
    ) -> None:
        self.ui_scale = max(1.0, min(4.0, float(root.winfo_fpixels("1i")) / 96.0))
        scaled_width = round(width * self.ui_scale)
        scaled_height = round(height * self.ui_scale)
        super().__init__(root, scaled_width, scaled_height, bg_color, title, resizable)
        self.width = scaled_width
        self.root = root
        self._conversion_queue: Queue[tuple[str, Any]] = Queue()
        self._conversion_running = False
        try:
            root.iconbitmap(str(PACKAGE_DIR / "favicon.ico"))
        except (OSError, TclError):
            pass

        self.funcs = funcs.Funcs()
        self.elements = [
            Label,
            Button,
            Button,
            Label,
            Entry,
            Button,
            Button,
            Label,
            Label,
            Label,
            Button,
            Label,
            Label,
            ttk.Progressbar,
        ]
        self.op_elements = [
            {
                "text": "PDF2WORDX - SRM",
                "font": ("Microsoft YaHei UI", 20, "bold"),
                "bg": "#001223",
                "fg": "white",
            },
            {
                "text": "帮助",
                "bg": "#001223",
                "width": 7,
                "height": 1,
                "fg": "#66ff02",
                "relief": "sunken",
                "command": self.help,
            },
            {
                "text": "开源许可",
                "bg": "#001223",
                "width": 9,
                "height": 1,
                "fg": "#66ff02",
                "relief": "sunken",
                "command": self.osl,
            },
            {"text": "输出文件名：", "bg": "#001223", "fg": "white"},
            {
                "bg": "#13004d",
                "fg": "#ffdd02",
                "font": ("Microsoft YaHei UI", 11, "bold"),
                "justify": "center",
            },
            {
                "text": "选择 PDF 文件",
                "bg": "#d1ff00",
                "width": 15,
                "pady": 5,
                "padx": 3,
                "font": ("Microsoft YaHei UI", 10, "bold"),
                "command": self.file_set,
            },
            {
                "text": "选择输出目录",
                "bg": "#d1ff00",
                "width": 15,
                "pady": 5,
                "padx": 3,
                "font": ("Microsoft YaHei UI", 10, "bold"),
                "command": self.file_out_set,
                "state": "disabled",
            },
            {
                "text": "PDF 文件：",
                "bg": "#001223",
                "fg": "white",
                "anchor": "w",
                "width": 64,
            },
            {
                "text": "输出文件：",
                "bg": "#001223",
                "fg": "white",
                "anchor": "w",
                "width": 64,
            },
            {
                "text": "保存位置：",
                "bg": "#001223",
                "fg": "white",
                "anchor": "w",
                "width": 64,
            },
            {
                "text": "开始转换",
                "bg": "#d1ff00",
                "width": 15,
                "pady": 5,
                "padx": 3,
                "font": ("Microsoft YaHei UI", 10, "bold"),
                "command": self.convert_file,
                "state": "disabled",
            },
            {
                "text": "© Tutos Rive / SRM-TRG 2024 · 简体中文翻译：OrangeGadgets",
                "bg": "#001223",
                "font": ("Microsoft YaHei UI", 7),
                "fg": "white",
            },
            {
                "text": "准备就绪",
                "bg": "#001223",
                "fg": "#d1ff00",
                "anchor": "w",
            },
            {
                "mode": "determinate",
                "maximum": 100,
                "value": 0,
            },
        ]
        self.type_package = ["place" for _ in self.op_elements]
        self.pack_op = [
            {"relx": 0.29, "rely": 0.05},
            {"relx": 0.02, "rely": 0.05},
            {"relx": 0.14, "rely": 0.05},
            {"relx": 0.25, "rely": 0.23},
            {"relx": 0.45, "rely": 0.23},
            {"relx": 0.09, "rely": 0.35},
            {"relx": 0.37, "rely": 0.35},
            {"relx": 0.08, "rely": 0.49},
            {"relx": 0.08, "rely": 0.58},
            {"relx": 0.08, "rely": 0.67},
            {"relx": 0.67, "rely": 0.35},
            {"relx": 0.25, "rely": 0.96},
            {"relx": 0.08, "rely": 0.76},
            {"relx": 0.08, "rely": 0.83, "relwidth": 0.84},
        ]

        self.widget = win.Widgets(self.root, self.elements)
        self.widget.widgets_create(self.op_elements, self.type_package, self.pack_op)

    def osl(self) -> None:
        self.funcs.msgbox(INFO_DIR / "NOTICE.zh-CN", "开源许可与致谢")

    def file_set(self) -> None:
        button = self.widget.widgets_list[6]
        if not self.funcs.ask_file(button):
            return
        entry = self.widget.widgets_list[4]
        entry.delete(0, "end")
        entry.insert(0, Path(self.funcs.file).stem)
        self.widget.widgets_list[10].configure(state="normal")
        self.funcs.set_text_label(
            self.widget.widgets_list[7], "PDF 文件：", self.funcs.file_name_original
        )
        self.funcs.set_text_label(
            self.widget.widgets_list[8], "输出文件：", self.funcs.file_name_out
        )
        self.funcs.set_text_label(
            self.widget.widgets_list[9], "保存位置：", self.funcs.output_directory
        )
        self._set_progress(0, "已选择文件，等待转换")

    def file_out_set(self) -> None:
        entry = self.widget.get_text(4)
        self.funcs.set_output_filename(entry)
        button = self.widget.widgets_list[10]
        if not self.funcs.ask_output_directory(button):
            return
        self.funcs.set_text_label(
            self.widget.widgets_list[8], "输出文件：", self.funcs.file_name_out
        )
        self.funcs.set_text_label(
            self.widget.widgets_list[9], "保存位置：", self.funcs.output_directory
        )

    def convert_file(self) -> None:
        if self._conversion_running:
            return
        self.funcs.set_output_filename(self.widget.get_text(4))
        self.funcs.refresh_output_path()
        if not self.funcs.file or not Path(self.funcs.file).is_file():
            messagebox.showerror("无法转换", "请先选择一个有效的 PDF 文件。")
            return
        if not self.funcs.directory_out:
            messagebox.showerror("无法转换", "请确认输出文件名和保存位置。")
            return
        self.funcs.set_text_label(
            self.widget.widgets_list[8], "输出文件：", self.funcs.file_name_out
        )
        self._conversion_running = True
        self._set_conversion_controls("disabled")
        self._set_progress(0, "正在准备转换…")

        def worker() -> None:
            try:
                result = self.funcs.convert_file(
                    lambda percent, status: self._conversion_queue.put(
                        ("progress", (percent, status))
                    )
                )
            except Exception as exc:
                logger.exception("转换任务意外终止")
                result = funcs.ConversionResult(
                    success=False,
                    output_path=self.funcs.directory_out,
                    error_message=str(exc),
                )
            self._conversion_queue.put(("done", result))

        try:
            Thread(target=worker, daemon=True).start()
            self.root.after(100, self._poll_conversion_queue)
        except Exception:
            logger.exception("启动转换线程失败")
            self._conversion_running = False
            self._set_conversion_controls("normal")
            self._set_progress(0, "无法启动转换")
            messagebox.showerror("转换失败", "无法启动转换任务，请查看日志。")

    def _poll_conversion_queue(self) -> None:
        result: funcs.ConversionResult | None = None
        while True:
            try:
                event, payload = self._conversion_queue.get_nowait()
            except Empty:
                break
            if event == "progress":
                percent, status = payload
                self._set_progress(percent, status)
            elif event == "done":
                result = payload

        if result is not None:
            self._finish_conversion(result)
        elif self._conversion_running:
            self.root.after(100, self._poll_conversion_queue)

    def _finish_conversion(self, result: funcs.ConversionResult) -> None:
        self._conversion_running = False
        self._set_conversion_controls("normal")
        if not result.success:
            self._set_progress(0, "转换失败")
            detail = result.error_message or "未知错误"
            messagebox.showerror(
                "转换失败", f"转换 PDF 时发生错误：\n{detail}\n\n详细信息已写入日志。"
            )
            return

        self._set_progress(100, "转换完成")
        if result.skipped_pages:
            pages = "、".join(str(page) for page in result.skipped_pages)
            messagebox.showwarning(
                "转换完成（部分页面已跳过）",
                f"DOCX 已生成：\n{result.output_path}\n\n"
                f"第 {pages} 页无法由转换引擎解析，未写入输出文件。",
            )
        else:
            messagebox.showinfo(
                "转换完成", f"{self.funcs.file_name_original} 已成功转换为：\n{result.output_path}"
            )

    def _set_conversion_controls(self, state: str) -> None:
        for index in (4, 5, 6, 10):
            self.widget.widgets_list[index].configure(state=state)

    def _set_progress(self, percent: int, status: str) -> None:
        safe_percent = max(0, min(100, int(percent)))
        self.widget.widgets_list[12].configure(
            text=f"{safe_percent}% · {status}" if safe_percent else status
        )
        self.widget.widgets_list[13].configure(value=safe_percent)

    def help(self) -> None:
        self.funcs.msgbox(INFO_DIR / "help.zh-CN", "如何使用 PDF2WORDX？")


def _enable_windows_dpi_awareness() -> None:
    import os

    if os.name != "nt":
        return
    try:
        user32 = ctypes.windll.user32
        if hasattr(user32, "SetProcessDpiAwarenessContext"):
            user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
            return
    except (AttributeError, OSError):
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


def run() -> None:
    _enable_windows_dpi_awareness()
    app = App(Tk())
    app.loop_window()


if __name__ == "__main__":
    run()
