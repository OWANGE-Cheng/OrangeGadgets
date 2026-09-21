from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from threading import get_ident
from tkinter import Button, Label, filedialog, messagebox
from typing import Callable

from pdf2docx import Converter

from .logging_utils import get_logger


logger = get_logger(__name__)


ProgressCallback = Callable[[int, str], None]


@dataclass(frozen=True)
class ConversionResult:
    success: bool
    output_path: str
    skipped_pages: tuple[int, ...] = ()
    error_message: str = ""


class Pdf2DocxProgressHandler(logging.Handler):
    """把 pdf2docx 的阶段日志转换为适合界面显示的进度。"""

    _ansi_pattern = re.compile(r"\x1b\[[0-9;]*m")
    _page_pattern = re.compile(r"\((\d+)/(\d+)\) Page (\d+)")
    _skipped_pattern = re.compile(
        r"Ignore page (\d+) due to parsing page error:\s*(.*)"
    )

    def __init__(self, callback: ProgressCallback) -> None:
        super().__init__(level=logging.INFO)
        self.callback = callback
        self.worker_thread_id = get_ident()
        self.phase = ""
        self.percent = 0
        self.skipped_pages: list[int] = []

    def _report(self, percent: int, status: str) -> None:
        self.percent = max(self.percent, percent)
        self.callback(self.percent, status)

    def emit(self, record: logging.LogRecord) -> None:
        if record.thread != self.worker_thread_id:
            return

        message = self._ansi_pattern.sub("", record.getMessage())
        skipped_match = self._skipped_pattern.search(message)
        if skipped_match:
            page_number = int(skipped_match.group(1))
            if page_number not in self.skipped_pages:
                self.skipped_pages.append(page_number)
            self._report(self.percent, f"第 {page_number} 页解析失败，已跳过")
            return

        if "[1/4] Opening document" in message:
            self.phase = "opening"
            self._report(3, "正在打开 PDF…")
        elif "[2/4] Analyzing document" in message:
            self.phase = "analyzing"
            self._report(10, "正在分析文档结构…")
        elif "[3/4] Parsing pages" in message:
            self.phase = "parsing"
            self._report(15, "正在解析页面…")
        elif "[4/4] Creating pages" in message:
            self.phase = "creating"
            self._report(78, "正在生成 Word 文档…")
        elif "Terminated in" in message:
            self._report(100, "转换完成")
        else:
            page_match = self._page_pattern.search(message)
            if not page_match:
                return
            current, total, page_number = map(int, page_match.groups())
            if total <= 0:
                return
            if self.phase == "parsing":
                percent = 15 + round(60 * current / total)
                status = f"正在解析 PDF：第 {current}/{total} 页（原第 {page_number} 页）"
            elif self.phase == "creating":
                percent = 78 + round(20 * current / total)
                status = f"正在生成 Word：第 {current}/{total} 页"
            else:
                return
            self._report(min(percent, 98), status)


class Funcs:
    def __init__(self) -> None:
        self.file_dialog = filedialog
        self.file = ""
        self.file_name_original = ""
        self.file_name_out = ""
        self.output_directory = ""
        self.directory_out = ""

    def ask_file(self, button: Button) -> bool:
        try:
            selected = self.file_dialog.askopenfilename(
                title="选择要转换的 PDF 文件",
                filetypes=[("PDF 文件", "*.pdf")],
            )
        except Exception:
            logger.exception("打开 PDF 文件选择窗口失败")
            messagebox.showerror("文件选择失败", "无法打开文件选择窗口，请重试。")
            return False

        if not selected:
            return False
        selected_path = Path(selected)
        if not selected_path.is_file() or selected_path.suffix.lower() != ".pdf":
            messagebox.showerror("文件选择失败", "请选择一个实际存在的 PDF 文件。")
            return False

        try:
            self.file = str(selected_path)
            self.file_name_original = selected_path.name
            self.output_directory = str(selected_path.parent)
            self.set_output_filename(selected_path.stem)
            self.refresh_output_path()
            self._active_button(button)
            return True
        except Exception:
            logger.exception("记录所选 PDF 文件失败")
            messagebox.showerror("文件选择失败", "读取所选 PDF 时发生内部错误，请查看日志。")
            return False

    def ask_output_directory(self, button: Button) -> bool:
        try:
            selected = self.file_dialog.askdirectory(title="选择 DOCX 文件的保存目录")
            if not selected:
                return False
            self.output_directory = selected
            self.refresh_output_path()
            self._active_button(button)
            return True
        except Exception:
            logger.exception("选择输出目录失败")
            messagebox.showerror("目录选择失败", "请选择一个有效的输出目录。")
            return False

    def set_output_filename(self, text: str) -> None:
        name = text.strip() or "转换后的文档"
        if name.lower().endswith(".docx"):
            name = name[:-5]
        self.file_name_out = f"{name}.docx"

    def refresh_output_path(self) -> None:
        if not self.output_directory or not self.file_name_out:
            self.directory_out = ""
            return
        self.directory_out = str(Path(self.output_directory) / self.file_name_out)

    def convert_file(
        self, progress_callback: ProgressCallback | None = None
    ) -> ConversionResult:
        converter: Converter | None = None
        callback = progress_callback or (lambda _percent, _status: None)
        progress_handler = Pdf2DocxProgressHandler(callback)
        root_logger = logging.getLogger()
        root_logger.addHandler(progress_handler)
        try:
            callback(0, "正在准备转换…")
            logger.info("开始转换：%s -> %s", self.file, self.directory_out)
            converter = Converter(self.file)
            converter.convert(self.directory_out)
            output_path = Path(self.directory_out)
            if not output_path.is_file() or output_path.stat().st_size == 0:
                raise RuntimeError("转换器未生成有效的 DOCX 文件")
            skipped_pages = tuple(sorted(progress_handler.skipped_pages))
            if skipped_pages:
                logger.warning("转换完成，但跳过页面：%s", skipped_pages)
            else:
                logger.info("转换完成：%s", self.directory_out)
            return ConversionResult(
                success=True,
                output_path=self.directory_out,
                skipped_pages=skipped_pages,
            )
        except Exception as exc:
            logger.exception("PDF 转 DOCX 失败")
            callback(0, "转换失败")
            return ConversionResult(
                success=False,
                output_path=self.directory_out,
                error_message=str(exc),
            )
        finally:
            if converter is not None:
                try:
                    converter.close()
                except Exception:
                    logger.exception("关闭 PDF 转换器时发生错误")
            try:
                root_logger.removeHandler(progress_handler)
            except ValueError:
                pass

    def set_text_label(self, label: Label, prefix: str, text: str) -> None:
        try:
            label.configure(text=prefix + text)
        except Exception:
            logger.exception("更新界面文字失败")
            messagebox.showerror("界面更新失败", "更新界面文字时发生内部错误。")

    @staticmethod
    def _active_button(button: Button) -> None:
        button.configure(state="normal")

    @staticmethod
    def _disable_button(button: Button | list[Button]) -> None:
        if isinstance(button, list):
            for item in button:
                item.configure(state="disabled")
        else:
            button.configure(state="disabled")

    @staticmethod
    def msgbox(path: str | Path, window_title: str) -> None:
        try:
            message = Path(path).read_text(encoding="utf-8")
            messagebox.showinfo(window_title, message)
        except Exception:
            logger.exception("读取说明文件失败")
            messagebox.showerror("无法打开说明", "读取说明文件时发生错误。")
