from __future__ import annotations

import logging
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

import fitz

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pdf2wordx.files.functions import Funcs, Pdf2DocxProgressHandler


class ConversionTests(unittest.TestCase):
    def test_pdf2docx_dependency_converts_a_simple_pdf(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            source = base / "示例.pdf"
            destination = base / "转换结果.docx"

            with fitz.open() as document:
                page = document.new_page(width=595, height=842)
                page.insert_text((72, 100), "OrangeGadgets pdf2wordx", fontsize=18)
                document.save(source)

            funcs = Funcs()
            funcs.file = str(source)
            funcs.file_name_original = source.name
            funcs.directory_out = str(destination)
            events: list[tuple[int, str]] = []

            result = funcs.convert_file(lambda percent, status: events.append((percent, status)))

            self.assertTrue(result.success)
            self.assertEqual(result.output_path, str(destination))
            self.assertEqual(result.skipped_pages, ())
            self.assertTrue(any("正在解析 PDF" in status for _percent, status in events))
            self.assertTrue(any("正在生成 Word" in status for _percent, status in events))
            self.assertEqual(events[-1], (100, "转换完成"))
            self.assertTrue(destination.is_file())
            self.assertGreater(destination.stat().st_size, 0)
            with zipfile.ZipFile(destination) as archive:
                self.assertIn("word/document.xml", archive.namelist())

    def test_progress_handler_reports_skipped_pages(self) -> None:
        events: list[tuple[int, str]] = []
        handler = Pdf2DocxProgressHandler(
            lambda percent, status: events.append((percent, status))
        )

        handler.emit(
            logging.LogRecord(
                name="root",
                level=logging.ERROR,
                pathname=__file__,
                lineno=1,
                msg="Ignore page 7 due to parsing page error: list index out of range",
                args=(),
                exc_info=None,
            )
        )

        self.assertEqual(handler.skipped_pages, [7])
        self.assertEqual(events[-1], (0, "第 7 页解析失败，已跳过"))
