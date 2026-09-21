from __future__ import annotations

import tempfile
import unittest
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pdf2wordx.files.functions import Funcs


class FakeButton:
    def __init__(self) -> None:
        self.state = "disabled"

    def configure(self, **options) -> None:
        self.state = options.get("state", self.state)


class FunctionsTests(unittest.TestCase):
    def test_chinese_pdf_path_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "科研资料_示例.pdf"
            source.write_bytes(b"%PDF-1.4\n")
            funcs = Funcs()
            funcs.file_dialog.askopenfilename = lambda **_kwargs: str(source)
            button = FakeButton()

            with patch("pdf2wordx.files.functions.messagebox.showerror") as show_error:
                result = funcs.ask_file(button)

            self.assertTrue(result)
            self.assertEqual(funcs.file, str(source))
            self.assertEqual(funcs.file_name_original, source.name)
            self.assertEqual(funcs.file_name_out, "科研资料_示例.docx")
            self.assertEqual(funcs.output_directory, str(source.parent))
            self.assertEqual(funcs.directory_out, str(source.with_suffix(".docx")))
            self.assertEqual(button.state, "normal")
            show_error.assert_not_called()

    def test_missing_pdf_path_has_specific_error(self) -> None:
        funcs = Funcs()
        funcs.file_dialog.askopenfilename = lambda **_kwargs: "Z:/不存在/示例.pdf"
        button = FakeButton()

        with patch("pdf2wordx.files.functions.messagebox.showerror") as show_error:
            result = funcs.ask_file(button)

        self.assertFalse(result)
        self.assertEqual(button.state, "disabled")
        show_error.assert_called_once_with("文件选择失败", "请选择一个实际存在的 PDF 文件。")

    def test_edited_filename_keeps_current_output_directory(self) -> None:
        funcs = Funcs()
        funcs.output_directory = r"D:\科研\输出"

        funcs.set_output_filename("自定义文件名.docx")
        funcs.refresh_output_path()

        self.assertEqual(funcs.file_name_out, "自定义文件名.docx")
        self.assertEqual(funcs.directory_out, r"D:\科研\输出\自定义文件名.docx")
