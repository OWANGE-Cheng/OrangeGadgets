from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pdf_merger.app import LayoutUnit, PageRef, PdfMergerApp, SourceModel


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


def make_page(uid: str, source_id: str = "source", page_index: int = 0) -> PageRef:
    return PageRef(uid, source_id, page_index, 595, 842)


class UiModelTests(unittest.TestCase):
    def test_disabled_context_command_uses_flat_grey_noop_style(self) -> None:
        class FakeMenu:
            def __init__(self) -> None:
                self.options = None

            def add_command(self, **options) -> None:
                self.options = options

        app = object.__new__(PdfMergerApp)
        app.theme_name = "dark"
        menu = FakeMenu()
        called = []

        app._add_context_command(menu, "复制", lambda: called.append(True), False)

        self.assertEqual(menu.options["foreground"], app.colors["disabled"])
        self.assertEqual(menu.options["activeforeground"], app.colors["disabled"])
        self.assertEqual(menu.options["activebackground"], app.colors["surface"])
        menu.options["command"]()
        self.assertEqual(called, [])

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

    def test_ctrl_and_shift_selection_match_desktop_conventions(self) -> None:
        app = object.__new__(PdfMergerApp)
        app.units = [make_unit(595, 842) for _ in range(3)]
        for index, unit in enumerate(app.units):
            unit.uid = f"unit-{index}"
            unit.page_ids = [f"page-{index}"]
        app.selected_page_ids = []
        app.selection_anchor_id = None

        app._select_unit_with_modifiers(app.units[0], 0)
        app._select_unit_with_modifiers(app.units[2], 0x0004)
        self.assertEqual(app.selected_page_ids, ["page-0", "page-2"])

        app._select_unit_with_modifiers(app.units[1], 0x0001)
        self.assertEqual(app.selected_page_ids, ["page-1", "page-2"])

    def test_selection_rectangle_uses_intersection(self) -> None:
        self.assertTrue(PdfMergerApp._rects_intersect((0, 0, 20, 20), (15, 15, 30, 30)))
        self.assertFalse(PdfMergerApp._rects_intersect((0, 0, 10, 10), (11, 11, 20, 20)))

    def test_undo_and_redo_restore_page_order(self) -> None:
        app = object.__new__(PdfMergerApp)
        first, second = make_page("first"), make_page("second", page_index=1)
        app.pages = [first, second]
        app.expanded_sources = set()
        app.selected_page_ids = []
        app.selection_anchor_id = None
        app.drag = None
        app.selection_box = None
        app.undo_stack = []
        app.redo_stack = []
        app.pending_conversions = 0
        app.busy = False
        app._update_summary = lambda: None
        app._schedule_draw = lambda: None
        app._set_status = lambda _message: None

        app._record_undo()
        app.pages = [second, first]
        app._undo()
        self.assertEqual(app.pages, [first, second])
        app._redo()
        self.assertEqual(app.pages, [second, first])

    def test_paste_creates_independent_file_and_is_undoable(self) -> None:
        app = object.__new__(PdfMergerApp)
        original = make_page("original")
        app.sources = {
            "source": SourceModel("source", Path("sample.pdf"), "pdf", 1),
        }
        app.pages = [original]
        app.clipboard_pages = [original]
        app.expanded_sources = set()
        app.selected_page_ids = [original.uid]
        app.selection_anchor_id = original.uid
        app.drag = None
        app.selection_box = None
        app.undo_stack = []
        app.redo_stack = []
        app.pending_conversions = 0
        app.busy = False
        app._update_summary = lambda: None
        app._schedule_draw = lambda: None
        app._set_status = lambda _message: None

        app._paste_pages()

        self.assertEqual(len(app.pages), 2)
        self.assertNotEqual(app.pages[0].source_id, app.pages[1].source_id)
        self.assertEqual(len(app._build_units()), 2)
        self.assertEqual([len(unit.page_ids) for unit in app._build_units()], [1, 1])

        app._undo()
        self.assertEqual(app.pages, [original])
        app._redo()
        self.assertEqual(len(app.pages), 2)
        self.assertIn(app.pages[1].source_id, app.sources)


if __name__ == "__main__":
    unittest.main()
