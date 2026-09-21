from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src" / "pdf2wordx"


class LocalizationTests(unittest.TestCase):
    def test_python_sources_are_valid(self) -> None:
        for path in PACKAGE.rglob("*.py"):
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    def test_chinese_interface_and_attribution_are_present(self) -> None:
        source = (PACKAGE / "_pdf2wordx.py").read_text(encoding="utf-8")
        for text in ("帮助", "开源许可", "选择 PDF 文件", "开始转换", "简体中文翻译：OrangeGadgets"):
            self.assertIn(text, source)
        self.assertIn("Tutos Rive", source)

        launcher = (ROOT / "run.pyw").read_text(encoding="utf-8")
        self.assertIn("PDF2WORDX 首次启动", launcher)
        self.assertIn("正在准备 PDF2WORDX", launcher)
        self.assertIn("PDF2WORDX 启动失败", launcher)

    def test_user_facing_spanish_was_removed_from_runtime_sources(self) -> None:
        runtime = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (PACKAGE / "_pdf2wordx.py", PACKAGE / "files" / "functions.py")
        )
        for spanish in (
            "Abrir Archivo",
            "Elegir Directorio",
            "Conversión Exitosa",
            "¿Cómo usar este programa?",
            "Seleccionar PDF",
        ):
            self.assertNotIn(spanish, runtime)
        self.assertNotIn("chromologger", runtime)

    def test_upstream_license_and_original_readme_are_preserved(self) -> None:
        self.assertIn("Copyright (c) 2025 Tutos Rive", (ROOT / "LICENSE").read_text(encoding="utf-8"))
        self.assertTrue((ROOT / "UPSTREAM_README_ES.md").is_file())
        notice = (ROOT / "TRANSLATION_NOTICE.md").read_text(encoding="utf-8")
        self.assertIn("仅承担上述翻译与集成工作", notice)


if __name__ == "__main__":
    unittest.main()
