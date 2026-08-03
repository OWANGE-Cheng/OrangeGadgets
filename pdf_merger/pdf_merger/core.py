from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import fitz
from PIL import Image, ImageOps, ImageSequence, UnidentifiedImageError


PDF_EXTENSIONS = {".pdf"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp", ".gif"}
DOCUMENT_EXTENSIONS = {".doc", ".docx"}
SUPPORTED_EXTENSIONS = PDF_EXTENSIONS | IMAGE_EXTENSIONS | DOCUMENT_EXTENSIONS

ProgressCallback = Callable[[int, int, str], None]


class MergeError(RuntimeError):
    """Raised when a source cannot be processed or the output cannot be written."""


class ConversionError(MergeError):
    """Raised when a non-PDF source cannot be converted."""


@dataclass(frozen=True, slots=True)
class SourceInfo:
    path: Path
    kind: str
    page_count: int | None
    size_bytes: int


@dataclass(frozen=True, slots=True)
class PageSelection:
    source: Path
    page_index: int
    prepared_pdf: Path | None = None


def _normalise_path(path: str | os.PathLike[str]) -> Path:
    return Path(path).expanduser().resolve()


def inspect_source(path: str | os.PathLike[str]) -> SourceInfo:
    source = _normalise_path(path)
    if not source.is_file():
        raise MergeError(f"文件不存在：{source}")

    suffix = source.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise MergeError(f"不支持的文件类型：{source.name}")

    if suffix in PDF_EXTENSIONS:
        try:
            with fitz.open(source) as document:
                if document.needs_pass:
                    raise MergeError(f"PDF 已加密，暂时无法读取：{source.name}")
                pages = document.page_count
        except MergeError:
            raise
        except Exception as exc:
            raise MergeError(f"PDF 文件损坏或无法读取：{source.name}") from exc
        if pages < 1:
            raise MergeError(f"PDF 没有可用页面：{source.name}")
        return SourceInfo(source, "PDF", pages, source.stat().st_size)

    if suffix in IMAGE_EXTENSIONS:
        try:
            with Image.open(source) as image:
                pages = getattr(image, "n_frames", 1)
                image.verify()
        except (UnidentifiedImageError, OSError) as exc:
            raise MergeError(f"图片损坏或无法读取：{source.name}") from exc
        return SourceInfo(source, "图片", pages, source.stat().st_size)

    return SourceInfo(source, "Word 文档", None, source.stat().st_size)


def image_to_pdf(source: Path, destination: Path) -> None:
    output = fitz.open()
    try:
        with Image.open(source) as image:
            frame_count = 0
            for raw_frame in ImageSequence.Iterator(image):
                frame_count += 1
                frame = ImageOps.exif_transpose(raw_frame.copy())
                dpi_value = frame.info.get("dpi", image.info.get("dpi", (96, 96)))
                try:
                    dpi_x, dpi_y = float(dpi_value[0]), float(dpi_value[1])
                except (TypeError, ValueError, IndexError):
                    dpi_x = dpi_y = 96.0
                if not 36 <= dpi_x <= 1200:
                    dpi_x = 96.0
                if not 36 <= dpi_y <= 1200:
                    dpi_y = 96.0

                width = max(1.0, min(14400.0, frame.width * 72.0 / dpi_x))
                height = max(1.0, min(14400.0, frame.height * 72.0 / dpi_y))
                if frame.mode not in {"RGB", "RGBA", "L", "LA"}:
                    frame = frame.convert("RGBA")
                stream = BytesIO()
                frame.save(stream, format="PNG")
                page = output.new_page(width=width, height=height)
                page.insert_image(page.rect, stream=stream.getvalue(), keep_proportion=False)
            if frame_count == 0:
                raise ConversionError(f"图片没有可用画面：{source.name}")
        output.save(destination, garbage=4, deflate=True)
    except ConversionError:
        raise
    except Exception as exc:
        raise ConversionError(f"图片转换失败：{source.name}（{exc}）") from exc
    finally:
        output.close()


def _find_libreoffice() -> str | None:
    candidates = [shutil.which("soffice"), shutil.which("libreoffice")]
    if sys.platform == "win32":
        candidates.extend(
            [
                r"C:\Program Files\LibreOffice\program\soffice.exe",
                r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
            ]
        )
    return next((str(path) for path in candidates if path and Path(path).is_file()), None)


def _convert_with_word(source: Path, destination: Path) -> None:
    try:
        import pythoncom
        import win32com.client
    except ImportError as exc:
        raise ConversionError("未安装 Microsoft Word 转换组件 pywin32。") from exc

    pythoncom.CoInitialize()
    word = None
    document = None
    try:
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        word.DisplayAlerts = 0
        try:
            word.AutomationSecurity = 3  # msoAutomationSecurityForceDisable
        except Exception:
            pass
        document = word.Documents.Open(
            str(source),
            ConfirmConversions=False,
            ReadOnly=True,
            AddToRecentFiles=False,
        )
        document.ExportAsFixedFormat(str(destination), 17)
    except Exception as exc:
        raise ConversionError(f"Word 文档转换失败：{source.name}（{exc}）") from exc
    finally:
        if document is not None:
            try:
                document.Close(False)
            except Exception:
                pass
        if word is not None:
            try:
                word.Quit()
            except Exception:
                pass
        pythoncom.CoUninitialize()


def _convert_with_libreoffice(source: Path, destination: Path, executable: str) -> None:
    with tempfile.TemporaryDirectory(prefix="pdf-merger-lo-") as profile_dir:
        profile_uri = Path(profile_dir).as_uri()
        command = [
            executable,
            "--headless",
            f"-env:UserInstallation={profile_uri}",
            "--convert-to",
            "pdf",
            "--outdir",
            str(destination.parent),
            str(source),
        ]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=180, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ConversionError(f"LibreOffice 转换失败：{source.name}") from exc
        generated = destination.parent / f"{source.stem}.pdf"
        if result.returncode != 0 or not generated.is_file():
            detail = (result.stderr or result.stdout or "未知错误").strip()
            raise ConversionError(f"LibreOffice 转换失败：{source.name}（{detail}）")
        if generated != destination:
            generated.replace(destination)


def document_to_pdf(source: Path, destination: Path) -> None:
    errors: list[str] = []
    if sys.platform == "win32":
        try:
            _convert_with_word(source, destination)
            return
        except ConversionError as exc:
            errors.append(str(exc))

    libreoffice = _find_libreoffice()
    if libreoffice:
        try:
            _convert_with_libreoffice(source, destination, libreoffice)
            return
        except ConversionError as exc:
            errors.append(str(exc))

    detail = "；".join(errors)
    hint = "请安装 Microsoft Word（Windows）或 LibreOffice 后重试。"
    raise ConversionError(f"无法转换 {source.name}。{detail + '。' if detail else ''}{hint}")


def merge_sources(
    sources: Iterable[str | os.PathLike[str]],
    destination: str | os.PathLike[str],
    *,
    progress: ProgressCallback | None = None,
    document_converter: Callable[[Path, Path], None] = document_to_pdf,
) -> int:
    source_paths = [_normalise_path(path) for path in sources]
    if not source_paths:
        raise MergeError("请至少添加一个文件。")

    output_path = _normalise_path(destination)
    if output_path.suffix.lower() != ".pdf":
        output_path = output_path.with_suffix(".pdf")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    for source in source_paths:
        inspect_source(source)
        if source == output_path:
            raise MergeError("输出文件不能与源文件相同。")

    merged = fitz.open()
    total = len(source_paths)
    temp_output: Path | None = None
    try:
        with tempfile.TemporaryDirectory(prefix="pdf-merger-") as work_dir_name:
            work_dir = Path(work_dir_name)
            for index, source in enumerate(source_paths, start=1):
                if progress:
                    progress(index - 1, total, f"正在处理 {source.name}")
                suffix = source.suffix.lower()
                prepared = source
                if suffix in IMAGE_EXTENSIONS:
                    prepared = work_dir / f"{index:04d}-image.pdf"
                    image_to_pdf(source, prepared)
                elif suffix in DOCUMENT_EXTENSIONS:
                    prepared = work_dir / f"{index:04d}-document.pdf"
                    document_converter(source, prepared)

                try:
                    with fitz.open(prepared) as part:
                        if part.needs_pass:
                            raise MergeError(f"PDF 已加密，暂时无法读取：{source.name}")
                        if part.page_count < 1:
                            raise MergeError(f"文件没有可用页面：{source.name}")
                        merged.insert_pdf(part)
                except MergeError:
                    raise
                except Exception as exc:
                    raise MergeError(f"合并失败：{source.name}（{exc}）") from exc

            if merged.page_count < 1:
                raise MergeError("没有可导出的 PDF 页面。")
            fd, temp_name = tempfile.mkstemp(
                prefix=f".{output_path.stem}-", suffix=".pdf", dir=output_path.parent
            )
            os.close(fd)
            temp_output = Path(temp_name)
            merged.set_metadata({"title": output_path.stem, "producer": "OrangeGadgets PDF Merger"})
            merged.save(temp_output, garbage=4, deflate=True)
            merged.close()

            with fitz.open(temp_output) as verification:
                if verification.page_count < 1:
                    raise MergeError("导出的 PDF 校验失败。")
            os.replace(temp_output, output_path)
            temp_output = None
            if progress:
                progress(total, total, "导出完成")
            return merged.page_count if not merged.is_closed else _count_pdf_pages(output_path)
    except MergeError:
        raise
    except Exception as exc:
        raise MergeError(f"无法生成 PDF：{exc}") from exc
    finally:
        if not merged.is_closed:
            merged.close()
        if temp_output and temp_output.exists():
            temp_output.unlink(missing_ok=True)


def _count_pdf_pages(path: Path) -> int:
    with fitz.open(path) as document:
        return document.page_count


def merge_selected_pages(
    selections: Iterable[PageSelection],
    destination: str | os.PathLike[str],
    *,
    progress: ProgressCallback | None = None,
    document_converter: Callable[[Path, Path], None] = document_to_pdf,
) -> int:
    page_plan = [
        PageSelection(
            _normalise_path(selection.source),
            selection.page_index,
            _normalise_path(selection.prepared_pdf) if selection.prepared_pdf else None,
        )
        for selection in selections
    ]
    if not page_plan:
        raise MergeError("请至少保留一个页面。")
    for selection in page_plan:
        if not isinstance(selection.page_index, int) or isinstance(selection.page_index, bool) or selection.page_index < 0:
            raise MergeError("页面编号无效。")
        inspect_source(selection.source)

    output_path = _normalise_path(destination)
    if output_path.suffix.lower() != ".pdf":
        output_path = output_path.with_suffix(".pdf")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if any(selection.source == output_path for selection in page_plan):
        raise MergeError("输出文件不能与源文件相同。")

    merged = fitz.open()
    temp_output: Path | None = None
    total = len(page_plan)
    prepared: dict[Path, Path] = {}
    try:
        with tempfile.TemporaryDirectory(prefix="pdf-merger-pages-") as work_dir_name:
            work_dir = Path(work_dir_name)
            for selection in page_plan:
                source = selection.source
                if source in prepared:
                    continue
                suffix = source.suffix.lower()
                if suffix in PDF_EXTENSIONS:
                    prepared[source] = source
                elif suffix in IMAGE_EXTENSIONS:
                    converted = work_dir / f"source-{len(prepared):04d}-image.pdf"
                    image_to_pdf(source, converted)
                    prepared[source] = converted
                else:
                    if selection.prepared_pdf and selection.prepared_pdf.is_file():
                        prepared[source] = selection.prepared_pdf
                    else:
                        converted = work_dir / f"source-{len(prepared):04d}-document.pdf"
                        document_converter(source, converted)
                        prepared[source] = converted

            open_documents: dict[Path, fitz.Document] = {}
            try:
                for position, selection in enumerate(page_plan, start=1):
                    source_pdf = prepared[selection.source]
                    document = open_documents.get(source_pdf)
                    if document is None:
                        try:
                            document = fitz.open(source_pdf)
                        except Exception as exc:
                            raise MergeError(f"无法读取转换结果：{selection.source.name}") from exc
                        if document.needs_pass:
                            document.close()
                            raise MergeError(f"PDF 已加密，暂时无法读取：{selection.source.name}")
                        open_documents[source_pdf] = document
                    if selection.page_index >= document.page_count:
                        raise MergeError(
                            f"页面不存在：{selection.source.name} 第 {selection.page_index + 1} 页"
                        )
                    if progress:
                        progress(position - 1, total, f"正在合并第 {position} / {total} 页")
                    merged.insert_pdf(
                        document,
                        from_page=selection.page_index,
                        to_page=selection.page_index,
                        links=True,
                        annots=True,
                    )
            finally:
                for document in open_documents.values():
                    document.close()

            fd, temp_name = tempfile.mkstemp(
                prefix=f".{output_path.stem}-", suffix=".pdf", dir=output_path.parent
            )
            os.close(fd)
            temp_output = Path(temp_name)
            merged.set_metadata({"title": output_path.stem, "producer": "OrangeGadgets PDF Merger"})
            merged.save(temp_output, garbage=4, deflate=True)
            merged.close()

            with fitz.open(temp_output) as verification:
                if verification.page_count != total:
                    raise MergeError("导出的 PDF 页数校验失败。")
            os.replace(temp_output, output_path)
            temp_output = None
            if progress:
                progress(total, total, "导出完成")
            return total
    except MergeError:
        raise
    except Exception as exc:
        raise MergeError(f"无法生成 PDF：{exc}") from exc
    finally:
        if not merged.is_closed:
            merged.close()
        if temp_output and temp_output.exists():
            temp_output.unlink(missing_ok=True)
