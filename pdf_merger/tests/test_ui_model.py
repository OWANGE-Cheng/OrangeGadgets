from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pdf_merger.app import LayoutUnit, PdfMergerApp


def make_unit(width: float, height: float) -> LayoutUnit:
    return LayoutUnit(
        uid="unit",
        source_id="source",
        page_ids=["page"],
        page_indices=[0],
        expanded=False,
        page_width=width,
        page_height=height,
    )


class UiModelTests(unittest.TestCase):
    def test_theme_choice_is_saved_and_loaded(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {"ORANGE_GADGETS_CONFIG_DIR": temp_dir}):
                app = object.__new__(PdfMergerApp)
                app.startup_theme = "dark"
                app._save_startup_theme()

                self.assertEqual(app._load_startup_theme(), "dark")
                config = json.loads((Path(temp_dir) / "pdf_merger.json").read_text(encoding="utf-8"))
                self.assertEqual(config, {"startup_theme": "dark"})

    def test_card_dimensions_follow_page_orientation(self) -> None:
        app = object.__new__(PdfMergerApp)
        portrait = app._measure_unit(make_unit(595, 842))
        landscape = app._measure_unit(make_unit(842, 595))
        square = app._measure_unit(make_unit(700, 700))

        self.assertLess(portrait[0], portrait[1])
        self.assertGreater(landscape[0], landscape[1])
        self.assertEqual(square[0], square[1])
        self.assertLess(portrait[2], landscape[2])
        self.assertGreater(portrait[3], landscape[3])

    def test_layout_pixels_scale_for_high_dpi_displays(self) -> None:
        app = object.__new__(PdfMergerApp)
        app.ui_scale = 2.0
        self.assertEqual(app._px(12), 24)
        high_dpi = app._measure_unit(make_unit(595, 842))

        app.ui_scale = 1.0
        standard_dpi = app._measure_unit(make_unit(595, 842))
        self.assertEqual(high_dpi, tuple(value * 2 for value in standard_dpi))


if __name__ == "__main__":
    unittest.main()
