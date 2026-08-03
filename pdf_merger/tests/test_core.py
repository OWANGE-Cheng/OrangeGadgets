from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import fitz
from PIL import Image

from pdf_merger.core import MergeError, PageSelection, inspect_source, merge_selected_pages, merge_sources


def make_pdf(path: Path, labels: list[str]) -> None:
    document = fitz.open()
    for label in labels:
        page = document.new_page(width=300, height=400)
        page.insert_text((40, 80), label, fontsize=24)
    document.save(path)
    document.close()


class CoreTests(unittest.TestCase):
    def test_inspect_and_merge_pdf_and_image_in_order(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = root / "first.pdf"
            image = root / "middle.png"
            last = root / "last.pdf"
            output = root / "merged.pdf"
            make_pdf(first, ["FIRST-1", "FIRST-2"])
            Image.new("RGB", (160, 90), "#f07a2b").save(image)
            make_pdf(last, ["LAST"])

            self.assertEqual(inspect_source(first).page_count, 2)
            self.assertEqual(inspect_source(image).page_count, 1)
            page_count = merge_sources([first, image, last], output)

            self.assertEqual(page_count, 4)
            with fitz.open(output) as merged:
                self.assertIn("FIRST-1", merged[0].get_text())
                self.assertEqual(len(merged[2].get_images()), 1)
                self.assertIn("LAST", merged[3].get_text())

    def test_document_converter_is_used(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "sample.docx"
            output = root / "result.pdf"
            source.write_bytes(b"test placeholder")

            def fake_converter(_source: Path, destination: Path) -> None:
                make_pdf(destination, ["CONVERTED"])

            page_count = merge_sources([source], output, document_converter=fake_converter)
            self.assertEqual(page_count, 1)
            with fitz.open(output) as merged:
                self.assertIn("CONVERTED", merged[0].get_text())

    def test_multiframe_image_becomes_multiple_pages(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "animation.gif"
            output = root / "result.pdf"
            first = Image.new("RGB", (80, 60), "red")
            second = Image.new("RGB", (80, 60), "blue")
            first.save(source, save_all=True, append_images=[second], duration=100, loop=0)

            page_count = merge_sources([source], output)
            self.assertEqual(page_count, 2)
            with fitz.open(output) as merged:
                self.assertEqual(merged.page_count, 2)

    def test_rejects_unsupported_and_same_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            unsupported = root / "notes.txt"
            unsupported.write_text("hello", encoding="utf-8")
            with self.assertRaises(MergeError):
                inspect_source(unsupported)

            source = root / "source.pdf"
            make_pdf(source, ["SOURCE"])
            with self.assertRaises(MergeError):
                merge_sources([source], source)

    def test_selected_pages_can_be_reordered_across_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = root / "first.pdf"
            second = root / "second.pdf"
            output = root / "selected.pdf"
            make_pdf(first, ["A-1", "A-2", "A-3"])
            make_pdf(second, ["B-1", "B-2"])

            page_count = merge_selected_pages(
                [
                    PageSelection(first, 2),
                    PageSelection(second, 0),
                    PageSelection(first, 0),
                ],
                output,
            )

            self.assertEqual(page_count, 3)
            with fitz.open(output) as merged:
                self.assertIn("A-3", merged[0].get_text())
                self.assertIn("B-1", merged[1].get_text())
                self.assertIn("A-1", merged[2].get_text())

    def test_selected_document_page_uses_converter(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "sample.docx"
            output = root / "selected.pdf"
            source.write_bytes(b"placeholder")

            def fake_converter(_source: Path, destination: Path) -> None:
                make_pdf(destination, ["DOC-1", "DOC-2"])

            merge_selected_pages(
                [PageSelection(source, 1)],
                output,
                document_converter=fake_converter,
            )
            with fitz.open(output) as merged:
                self.assertEqual(merged.page_count, 1)
                self.assertIn("DOC-2", merged[0].get_text())


if __name__ == "__main__":
    unittest.main()
