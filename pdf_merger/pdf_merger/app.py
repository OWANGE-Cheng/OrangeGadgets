from __future__ import annotations

import json
import os
import queue
import ctypes
import tempfile
import threading
import tkinter as tk
import uuid
from collections import Counter
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import fitz
from PIL import Image, ImageOps, ImageTk

from .core import (
    DOCUMENT_EXTENSIONS,
    IMAGE_EXTENSIONS,
    SUPPORTED_EXTENSIONS,
    MergeError,
    PageSelection,
    document_to_pdf,
    inspect_source,
    merge_selected_pages,
)

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD

    DND_AVAILABLE = True
except ImportError:
    DND_FILES = None
    TkinterDnD = None
    DND_AVAILABLE = False


THEMES = {
    "light": {
        "bg": "#F4F5F7",
        "surface": "#FFFFFF",
        "canvas": "#EEF1F4",
        "card": "#FFFFFF",
        "card_hover": "#FFF8F2",
        "thumb": "#E3E7EC",
        "text": "#17202B",
        "muted": "#697586",
        "border": "#D7DCE3",
        "accent": "#EC6A22",
        "accent_hover": "#D95612",
        "accent_soft": "#FFF0E6",
        "danger": "#D92D20",
        "shadow": "#C8CED6",
        "insert": "#1976D2",
    },
    "dark": {
        "bg": "#0F1217",
        "surface": "#171B22",
        "canvas": "#11151B",
        "card": "#202630",
        "card_hover": "#292F39",
        "thumb": "#303743",
        "text": "#F2F4F7",
        "muted": "#A8B0BD",
        "border": "#343B47",
        "accent": "#FF7A2E",
        "accent_hover": "#FF9257",
        "accent_soft": "#3B281E",
        "danger": "#FF6B62",
        "shadow": "#090B0E",
        "insert": "#58A6FF",
    },
}


_DPI_AWARENESS_INITIALIZED = False


def _enable_windows_dpi_awareness() -> None:
    """Enable native-resolution rendering before Tk creates any windows."""
    global _DPI_AWARENESS_INITIALIZED
    if _DPI_AWARENESS_INITIALIZED or os.name != "nt":
        return
    _DPI_AWARENESS_INITIALIZED = True
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


@dataclass(slots=True)
class SourceModel:
    uid: str
    path: Path
    kind: str
    page_count: int
    prepared_pdf: Path | None = None
    converting: bool = False
    error: str | None = None


@dataclass(frozen=True, slots=True)
class PageRef:
    uid: str
    source_id: str
    page_index: int
    width: float
    height: float


@dataclass(slots=True)
class LayoutUnit:
    uid: str
    source_id: str
    page_ids: list[str]
    page_indices: list[int]
    expanded: bool
    page_width: float
    page_height: float
    x1: float = 0
    y1: float = 0
    x2: float = 0
    y2: float = 0

    @property
    def center_x(self) -> float:
        return (self.x1 + self.x2) / 2

    @property
    def center_y(self) -> float:
        return (self.y1 + self.y2) / 2


@dataclass(slots=True)
class DragState:
    unit: LayoutUnit
    start_x: float
    start_y: float
    current_x: float
    current_y: float
    active: bool = False
    insert_index: int = 0


class PdfMergerApp:
    CARD_GAP_X = 22
    CARD_GAP_Y = 24
    CANVAS_PAD = 30
    MAX_PREVIEW_WIDTH = 220
    MAX_PREVIEW_HEIGHT = 170
    MIN_CARD_WIDTH = 140
    THUMBNAIL_SIZE = (300, 380)

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.ui_scale = max(1.0, min(4.0, float(root.winfo_fpixels("1i")) / 96.0))
        self.startup_theme = self._load_startup_theme()
        self.theme_name = self._resolve_theme(self.startup_theme)
        self.sources: dict[str, SourceModel] = {}
        self.pages: list[PageRef] = []
        self.expanded_sources: set[str] = set()
        self.units: list[LayoutUnit] = []
        self.unit_by_id: dict[str, LayoutUnit] = {}
        self.selected_page_ids: list[str] = []
        self.hover_unit_id: str | None = None
        self.drag: DragState | None = None
        self.busy = False
        self.pending_conversions = 0
        self.render_job: str | None = None
        self.queue_job: str | None = None
        self.thumbnail_images: dict[tuple[str, int], Image.Image] = {}
        self.thumbnail_photos: dict[tuple[str, int], ImageTk.PhotoImage] = {}
        self.thumbnail_pending: set[tuple[str, int]] = set()
        self.executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="pdf-merger")
        self.ui_queue: queue.Queue[tuple[object, tuple[object, ...]]] = queue.Queue()
        self.temp_dir = tempfile.TemporaryDirectory(prefix="orange-pdf-merger-")
        self.closing = False

        self.root.title("PDF 合并与转换")
        self.root.geometry(f"{self._px(1240)}x{self._px(820)}")
        self.root.minsize(self._px(900), self._px(620))
        self._configure_styles()
        self._build_ui()
        self._bind_events()
        self._apply_theme()
        self._draw_workspace()
        self.queue_job = self.root.after(40, self._drain_ui_queue)

        if DND_AVAILABLE:
            self.root.drop_target_register(DND_FILES)
            self.root.dnd_bind("<<Drop>>", self._on_drop)
        else:
            self._set_status("安装 tkinterdnd2 后可把文件直接拖到工作区。")

    @property
    def colors(self) -> dict[str, str]:
        return THEMES[self.theme_name]

    def _px(self, value: float) -> int:
        return max(1, round(value * getattr(self, "ui_scale", 1.0)))

    def _configure_styles(self) -> None:
        self.style = ttk.Style(self.root)
        self.style.theme_use("clam")

    def _apply_theme(self) -> None:
        c = self.colors
        self.root.configure(bg=c["bg"])
        self.style.configure("App.TFrame", background=c["bg"])
        self.style.configure("Surface.TFrame", background=c["surface"])
        self.style.configure(
            "Title.TLabel",
            background=c["bg"],
            foreground=c["text"],
            font=("Microsoft YaHei UI", 21, "bold"),
        )
        self.style.configure(
            "Subtitle.TLabel",
            background=c["bg"],
            foreground=c["muted"],
            font=("Microsoft YaHei UI", 9),
        )
        self.style.configure(
            "Section.TLabel",
            background=c["surface"],
            foreground=c["text"],
            font=("Microsoft YaHei UI", 11, "bold"),
        )
        self.style.configure(
            "Meta.TLabel",
            background=c["surface"],
            foreground=c["muted"],
            font=("Microsoft YaHei UI", 9),
        )
        self.style.configure(
            "Footer.TLabel",
            background=c["bg"],
            foreground=c["muted"],
            font=("Microsoft YaHei UI", 9),
        )
        self.style.configure(
            "Accent.TButton",
            background=c["accent"],
            foreground="white",
            borderwidth=0,
            padding=(self._px(16), self._px(9)),
            font=("Microsoft YaHei UI", 10, "bold"),
        )
        self.style.map(
            "Accent.TButton",
            background=[("active", c["accent_hover"]), ("disabled", c["border"])],
            foreground=[("disabled", c["muted"])],
        )
        self.style.configure(
            "Plain.TButton",
            background=c["surface"],
            foreground=c["text"],
            bordercolor=c["border"],
            lightcolor=c["border"],
            darkcolor=c["border"],
            padding=(self._px(11), self._px(8)),
            font=("Microsoft YaHei UI", 9),
        )
        self.style.map("Plain.TButton", background=[("active", c["card_hover"])])
        self.style.configure(
            "Theme.TButton",
            background=c["bg"],
            foreground=c["text"],
            bordercolor=c["border"],
            padding=(self._px(12), self._px(8)),
            font=("Microsoft YaHei UI", 9),
        )
        self.style.map("Theme.TButton", background=[("active", c["surface"])])
        self.style.configure(
            "Orange.Horizontal.TProgressbar",
            troughcolor=c["border"],
            background=c["accent"],
            borderwidth=0,
        )
        self.style.configure(
            "Vertical.TScrollbar",
            background=c["surface"],
            troughcolor=c["canvas"],
            bordercolor=c["border"],
            lightcolor=c["surface"],
            darkcolor=c["surface"],
            arrowcolor=c["muted"],
        )
        self.style.map("Vertical.TScrollbar", background=[("active", c["card_hover"])])
        self.workspace.configure(bg=c["canvas"], highlightbackground=c["border"])
        self.canvas_box.configure(bg=c["surface"], highlightbackground=c["border"])
        self.theme_button.configure(text="☀  浅色模式" if self.theme_name == "dark" else "☾  夜间模式")
        self._draw_workspace()

    def _build_ui(self) -> None:
        outer = ttk.Frame(
            self.root,
            style="App.TFrame",
            padding=(self._px(24), self._px(18), self._px(24), self._px(18)),
        )
        outer.pack(fill="both", expand=True)

        header = ttk.Frame(outer, style="App.TFrame")
        header.pack(fill="x", pady=(0, 14))
        title_box = ttk.Frame(header, style="App.TFrame")
        title_box.pack(side="left", fill="x", expand=True)
        ttk.Label(title_box, text="合并文件", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            title_box,
            text="拖动卡片调整顺序；展开后可单独移动页面",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(3, 0))
        self.theme_button = ttk.Button(header, style="Theme.TButton", command=self._toggle_theme)
        self.theme_button.pack(side="right", padx=(8, 0))
        self.settings_button = ttk.Button(header, text="⚙  设置", style="Theme.TButton", command=self._open_settings)
        self.settings_button.pack(side="right", padx=(8, 0))
        self.add_button = ttk.Button(header, text="＋  添加文件", style="Accent.TButton", command=self._choose_files)
        self.add_button.pack(side="right", padx=(8, 0))

        self.canvas_box = tk.Frame(outer, highlightthickness=1)
        self.canvas_box.pack(fill="both", expand=True)
        work_header = ttk.Frame(
            self.canvas_box,
            style="Surface.TFrame",
            padding=(self._px(16), self._px(11)),
        )
        work_header.pack(fill="x")
        ttk.Label(work_header, text="文件与页面", style="Section.TLabel").pack(side="left")
        self.summary_label = ttk.Label(work_header, text="0 个文件 · 0 页", style="Meta.TLabel")
        self.summary_label.pack(side="left", padx=(9, 0))
        self.hint_label = ttk.Label(
            work_header,
            text="悬停显示删除操作  ·  鼠标滚轮纵向浏览",
            style="Meta.TLabel",
        )
        self.hint_label.pack(side="right")

        self.workspace = tk.Canvas(
            self.canvas_box,
            highlightthickness=0,
            borderwidth=0,
            yscrollincrement=self._px(32),
        )
        self.workspace.pack(fill="both", expand=True)
        self.scrollbar = ttk.Scrollbar(
            self.canvas_box,
            orient="vertical",
            command=self._scroll_workspace,
        )
        self.scrollbar.pack(side="right", fill="y", before=self.workspace)
        self.workspace.configure(yscrollcommand=self.scrollbar.set)

        footer = ttk.Frame(outer, style="App.TFrame")
        footer.pack(fill="x", pady=(14, 0))
        status_box = ttk.Frame(footer, style="App.TFrame")
        status_box.pack(side="left", fill="x", expand=True, padx=(0, 14))
        self.status_label = ttk.Label(status_box, text="可拖入 PDF、图片、DOC 或 DOCX 文件", style="Footer.TLabel")
        self.status_label.pack(anchor="w")
        self.progress = ttk.Progressbar(status_box, style="Orange.Horizontal.TProgressbar", mode="determinate")
        self.progress.pack(fill="x", pady=(6, 0))
        self.remove_button = ttk.Button(footer, text="删除所选", style="Plain.TButton", command=self._delete_selected)
        self.remove_button.pack(side="right", padx=(0, 8))
        self.export_button = ttk.Button(footer, text="合并并导出 PDF", style="Accent.TButton", command=self._export)
        self.export_button.pack(side="right")

    def _bind_events(self) -> None:
        self.workspace.bind("<Configure>", lambda _event: self._schedule_draw())
        self.workspace.bind("<Motion>", self._on_motion)
        self.workspace.bind("<Leave>", self._on_leave)
        self.workspace.bind("<ButtonPress-1>", self._on_press)
        self.workspace.bind("<B1-Motion>", self._on_drag_motion)
        self.workspace.bind("<ButtonRelease-1>", self._on_release)
        self.workspace.bind("<MouseWheel>", self._on_mousewheel)
        self.root.bind("<Control-o>", lambda _event: self._choose_files())
        self.root.bind("<Delete>", lambda _event: self._delete_selected())
        self.root.bind("<Control-d>", lambda _event: self._toggle_theme())
        self.root.protocol("WM_DELETE_WINDOW", self._close)

    def _toggle_theme(self) -> None:
        self.theme_name = "dark" if self.theme_name == "light" else "light"
        self.startup_theme = self.theme_name
        self._save_startup_theme()
        self._apply_theme()

    @staticmethod
    def _config_path() -> Path:
        override = os.environ.get("ORANGE_GADGETS_CONFIG_DIR")
        if override:
            base = Path(override)
        elif os.name == "nt":
            base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "OrangeGadgets"
        else:
            base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "OrangeGadgets"
        return base / "pdf_merger.json"

    @staticmethod
    def _system_theme() -> str:
        if os.name == "nt":
            try:
                import winreg

                with winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
                ) as key:
                    value, _kind = winreg.QueryValueEx(key, "AppsUseLightTheme")
                    return "light" if int(value) else "dark"
            except (OSError, ValueError):
                pass
        return "light"

    @classmethod
    def _resolve_theme(cls, choice: str) -> str:
        return cls._system_theme() if choice == "system" else choice

    def _load_startup_theme(self) -> str:
        try:
            data = json.loads(self._config_path().read_text(encoding="utf-8"))
            choice = data.get("startup_theme", "system")
            return choice if choice in {"system", "light", "dark"} else "system"
        except (OSError, ValueError, TypeError, AttributeError):
            return "system"

    def _save_startup_theme(self) -> None:
        path = self._config_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(".tmp")
            temporary.write_text(
                json.dumps({"startup_theme": self.startup_theme}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            os.replace(temporary, path)
        except OSError as exc:
            messagebox.showwarning("设置未保存", f"无法保存主题设置：\n{exc}", parent=self.root)

    def _open_settings(self) -> None:
        c = self.colors
        dialog = tk.Toplevel(self.root)
        dialog.title("外观设置")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.configure(bg=c["bg"])
        box = tk.Frame(dialog, bg=c["bg"], padx=self._px(24), pady=self._px(20))
        box.pack(fill="both", expand=True)
        tk.Label(
            box,
            text="启动时使用的主题",
            bg=c["bg"],
            fg=c["text"],
            font=("Microsoft YaHei UI", 13, "bold"),
        ).pack(anchor="w")
        tk.Label(
            box,
            text="设置会自动保存，并在下次打开程序时应用。",
            bg=c["bg"],
            fg=c["muted"],
            font=("Microsoft YaHei UI", 9),
        ).pack(anchor="w", pady=(4, 14))
        choice = tk.StringVar(value=self.startup_theme)
        for value, label in (("system", "跟随系统"), ("light", "浅色模式"), ("dark", "夜间模式")):
            tk.Radiobutton(
                box,
                text=label,
                value=value,
                variable=choice,
                bg=c["bg"],
                fg=c["text"],
                selectcolor=c["surface"],
                activebackground=c["bg"],
                activeforeground=c["text"],
                highlightthickness=0,
                anchor="w",
                font=("Microsoft YaHei UI", 10),
            ).pack(fill="x", pady=3)

        buttons = tk.Frame(box, bg=c["bg"])
        buttons.pack(fill="x", pady=(16, 0))
        ttk.Button(buttons, text="取消", style="Plain.TButton", command=dialog.destroy).pack(side="right")

        def apply_setting() -> None:
            self.startup_theme = choice.get()
            self.theme_name = self._resolve_theme(self.startup_theme)
            self._save_startup_theme()
            self._apply_theme()
            dialog.destroy()

        ttk.Button(buttons, text="保存并应用", style="Accent.TButton", command=apply_setting).pack(
            side="right", padx=(0, 8)
        )
        dialog.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - dialog.winfo_reqwidth()) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - dialog.winfo_reqheight()) // 2
        dialog.geometry(f"+{max(0, x)}+{max(0, y)}")

    def _choose_files(self) -> None:
        if self.busy:
            return
        paths = filedialog.askopenfilenames(
            parent=self.root,
            title="选择要合并或转换的文件",
            filetypes=[
                ("支持的文件", "*.pdf *.jpg *.jpeg *.png *.bmp *.tif *.tiff *.webp *.gif *.doc *.docx"),
                ("PDF 文件", "*.pdf"),
                ("图片", "*.jpg *.jpeg *.png *.bmp *.tif *.tiff *.webp *.gif"),
                ("Word 文档", "*.doc *.docx"),
                ("所有文件", "*.*"),
            ],
        )
        if paths:
            self._add_paths(paths)

    def _on_drop(self, event: tk.Event) -> str:
        if not self.busy:
            self._add_paths(self.root.tk.splitlist(event.data))
        return "break"

    def _add_paths(self, paths: tuple[str, ...] | list[str]) -> None:
        existing = {source.path for source in self.sources.values()}
        errors: list[str] = []
        added = 0
        for raw_path in paths:
            path = Path(raw_path).expanduser().resolve()
            if path in existing:
                continue
            if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                errors.append(f"{path.name}：不支持的文件类型")
                continue
            try:
                info = inspect_source(path)
            except MergeError as exc:
                errors.append(str(exc))
                continue

            source_id = uuid.uuid4().hex
            is_document = path.suffix.lower() in DOCUMENT_EXTENSIONS
            try:
                page_sizes = [(595.0, 842.0)] if is_document else self._read_page_sizes(info.path)
            except Exception as exc:
                errors.append(f"{path.name}：无法读取页面尺寸（{exc}）")
                continue
            page_count = info.page_count or len(page_sizes) or 1
            if len(page_sizes) != page_count:
                page_sizes = [(595.0, 842.0)] * page_count
            source = SourceModel(
                uid=source_id,
                path=info.path,
                kind=info.kind,
                page_count=page_count,
                converting=is_document,
            )
            self.sources[source_id] = source
            self.pages.extend(self._make_pages(source_id, page_count, page_sizes))
            existing.add(path)
            added += 1
            if is_document:
                self._start_document_conversion(source)

        if added:
            self._set_status(f"已添加 {added} 个文件。拖动卡片即可调整合并顺序。")
            self._update_summary()
            self._schedule_draw()
        if errors:
            messagebox.showwarning("部分文件未添加", "\n".join(f"• {item}" for item in errors[:10]), parent=self.root)

    @staticmethod
    def _read_page_sizes(path: Path) -> list[tuple[float, float]]:
        if path.suffix.lower() == ".pdf":
            with fitz.open(path) as document:
                return [(float(page.rect.width), float(page.rect.height)) for page in document]
        sizes: list[tuple[float, float]] = []
        with Image.open(path) as image:
            for index in range(getattr(image, "n_frames", 1)):
                image.seek(index)
                width, height = ImageOps.exif_transpose(image.copy()).size
                sizes.append((float(width), float(height)))
        return sizes

    def _make_pages(
        self,
        source_id: str,
        page_count: int,
        page_sizes: list[tuple[float, float]],
    ) -> list[PageRef]:
        return [
            PageRef(uuid.uuid4().hex, source_id, index, page_sizes[index][0], page_sizes[index][1])
            for index in range(page_count)
        ]

    def _start_document_conversion(self, source: SourceModel) -> None:
        self.pending_conversions += 1
        self.progress.configure(mode="indeterminate")
        self.progress.start(12)
        self._set_status(f"正在转换并生成预览：{source.path.name}")
        destination = Path(self.temp_dir.name) / f"{source.uid}.pdf"
        future = self.executor.submit(self._convert_document, source.path, destination)
        future.add_done_callback(
            lambda completed, source_id=source.uid, output=destination: self._after(
                self._document_converted, source_id, output, completed
            )
        )

    @staticmethod
    def _convert_document(source: Path, destination: Path) -> list[tuple[float, float]]:
        document_to_pdf(source, destination)
        with fitz.open(destination) as converted:
            if converted.page_count < 1:
                raise MergeError(f"转换结果没有页面：{source.name}")
            return [(float(page.rect.width), float(page.rect.height)) for page in converted]

    def _document_converted(
        self,
        source_id: str,
        output: Path,
        future: Future[list[tuple[float, float]]],
    ) -> None:
        self.pending_conversions = max(0, self.pending_conversions - 1)
        source = self.sources.get(source_id)
        if source is None:
            self._finish_conversion_status()
            return
        try:
            page_sizes = future.result()
            page_count = len(page_sizes)
        except Exception as exc:
            source.converting = False
            source.error = str(exc)
            self._set_status(f"转换失败：{source.path.name}")
            messagebox.showerror("Word 文档转换失败", str(exc), parent=self.root)
        else:
            placeholder_positions = [index for index, page in enumerate(self.pages) if page.source_id == source_id]
            insert_at = placeholder_positions[0] if placeholder_positions else len(self.pages)
            self.pages = [page for page in self.pages if page.source_id != source_id]
            new_pages = self._make_pages(source_id, page_count, page_sizes)
            self.pages[insert_at:insert_at] = new_pages
            source.page_count = page_count
            source.prepared_pdf = output
            source.converting = False
            source.error = None
            self._set_status(f"已完成转换：{source.path.name}（{page_count} 页）")
        self._finish_conversion_status()
        self._update_summary()
        self._schedule_draw()

    def _finish_conversion_status(self) -> None:
        if self.pending_conversions == 0 and not self.busy:
            self.progress.stop()
            self.progress.configure(mode="determinate", value=0)
        self._sync_controls()

    def _build_units(self) -> list[LayoutUnit]:
        units: list[LayoutUnit] = []
        index = 0
        while index < len(self.pages):
            page = self.pages[index]
            source = self.sources.get(page.source_id)
            if source is None:
                index += 1
                continue
            if page.source_id in self.expanded_sources and not source.converting:
                units.append(
                    LayoutUnit(
                        uid=f"p_{page.uid}",
                        source_id=page.source_id,
                        page_ids=[page.uid],
                        page_indices=[page.page_index],
                        expanded=True,
                        page_width=page.width,
                        page_height=page.height,
                    )
                )
                index += 1
                continue

            segment = [page]
            cursor = index + 1
            while cursor < len(self.pages) and self.pages[cursor].source_id == page.source_id:
                segment.append(self.pages[cursor])
                cursor += 1
            units.append(
                LayoutUnit(
                    uid=f"g_{segment[0].uid}",
                    source_id=page.source_id,
                    page_ids=[item.uid for item in segment],
                    page_indices=[item.page_index for item in segment],
                    expanded=False,
                    page_width=segment[0].width,
                    page_height=segment[0].height,
                )
            )
            index = cursor
        return units

    def _draw_workspace(self) -> None:
        if not hasattr(self, "workspace"):
            return
        self.render_job = None
        c = self.colors
        self.workspace.delete("all")
        self.thumbnail_photos.clear()
        self.units = self._build_units()
        self.unit_by_id = {unit.uid: unit for unit in self.units}
        active_source_counts = Counter(page.source_id for page in self.pages)
        height = max(self._px(360), self.workspace.winfo_height())

        if not self.units:
            self.workspace.configure(scrollregion=(0, 0, self.workspace.winfo_width(), height))
            center_x = max(self._px(280), self.workspace.winfo_width() // 2)
            center_y = height // 2
            self.workspace.create_oval(
                center_x - self._px(34),
                center_y - self._px(70),
                center_x + self._px(34),
                center_y - self._px(2),
                fill=c["accent_soft"],
                outline="",
            )
            self.workspace.create_text(
                center_x,
                center_y - self._px(36),
                text="＋",
                fill=c["accent"],
                font=("Segoe UI", 28),
            )
            self.workspace.create_text(
                center_x,
                center_y + self._px(28),
                text="将文件拖到这里",
                fill=c["text"],
                font=("Microsoft YaHei UI", 14, "bold"),
            )
            self.workspace.create_text(
                center_x,
                center_y + self._px(58),
                text="支持 PDF、图片、DOC 和 DOCX",
                fill=c["muted"],
                font=("Microsoft YaHei UI", 9),
            )
            return

        available_width = max(self._px(300), self.workspace.winfo_width())
        canvas_pad = self._px(self.CANVAS_PAD)
        gap_x = self._px(self.CARD_GAP_X)
        gap_y = self._px(self.CARD_GAP_Y)
        x = canvas_pad
        y = canvas_pad
        row_height = 0.0
        visible_top = self.workspace.canvasy(0) - self._px(320)
        visible_bottom = visible_top + self.workspace.winfo_height() + self._px(640)

        for unit in self.units:
            preview_width, preview_height, card_width, card_height = self._measure_unit(unit)
            if x > canvas_pad and x + card_width > available_width - canvas_pad:
                x = canvas_pad
                y += row_height + gap_y
                row_height = 0
            unit.x1, unit.y1 = x, y
            unit.x2, unit.y2 = x + card_width, y + card_height
            should_load = unit.y2 >= visible_top and unit.y1 <= visible_bottom
            self._draw_unit(
                unit,
                preview_width,
                preview_height,
                should_load,
                active_source_counts[unit.source_id],
            )
            x += card_width + gap_x
            row_height = max(row_height, card_height)

        total_height = max(height, y + row_height + canvas_pad)
        self.workspace.configure(scrollregion=(0, 0, available_width, total_height))
        if self.drag and self.drag.active:
            remaining = [unit for unit in self.units if unit.uid != self.drag.unit.uid]
            marker_x, marker_y1, marker_y2 = self._insertion_marker(remaining, self.drag.insert_index)
            self.workspace.create_line(
                marker_x,
                marker_y1,
                marker_x,
                marker_y2,
                fill=c["insert"],
                width=self._px(4),
                capstyle="round",
                tags=("drag_overlay",),
            )
            self.workspace.create_rectangle(
                self.drag.current_x - self._px(68),
                self.drag.current_y - self._px(31),
                self.drag.current_x + self._px(68),
                self.drag.current_y + self._px(31),
                outline=c["accent"],
                width=self._px(2),
                dash=(self._px(5), self._px(3)),
                tags=("drag_overlay",),
            )
            self.workspace.create_text(
                self.drag.current_x,
                self.drag.current_y,
                text="移动到这里",
                fill=c["accent"],
                font=("Microsoft YaHei UI", 9, "bold"),
                tags=("drag_overlay",),
            )

    def _measure_unit(self, unit: LayoutUnit) -> tuple[int, int, int, int]:
        width = max(1.0, unit.page_width)
        height = max(1.0, unit.page_height)
        max_width = self._px(self.MAX_PREVIEW_WIDTH)
        max_height = self._px(self.MAX_PREVIEW_HEIGHT)
        scale = min(max_width / width, max_height / height)
        preview_width = max(self._px(56), round(width * scale))
        preview_height = max(self._px(56), round(height * scale))
        card_width = max(self._px(self.MIN_CARD_WIDTH), preview_width + self._px(24))
        card_height = preview_height + self._px(78)
        return preview_width, preview_height, card_width, card_height

    def _draw_unit(
        self,
        unit: LayoutUnit,
        preview_width: int,
        preview_height: int,
        should_load: bool,
        active_source_pages: int,
    ) -> None:
        c = self.colors
        px = self._px
        source = self.sources[unit.source_id]
        selected = set(unit.page_ids) == set(self.selected_page_ids) and bool(self.selected_page_ids)
        hovered = unit.uid == self.hover_unit_id
        card_fill = c["card_hover"] if hovered else c["card"]
        border = c["accent"] if selected else c["border"]
        border_width = px(3) if selected else px(1)

        if len(unit.page_ids) > 1:
            for offset in (px(10), px(6)):
                self.workspace.create_rectangle(
                    unit.x1 + offset,
                    unit.y1 - offset,
                    unit.x2 + offset,
                    unit.y2 - offset,
                    fill=c["shadow"],
                    outline=c["border"],
                )
        self.workspace.create_rectangle(
            unit.x1,
            unit.y1,
            unit.x2,
            unit.y2,
            fill=card_fill,
            outline=border,
            width=border_width,
            tags=("card", f"unit:{unit.uid}"),
        )
        card_center_x = (unit.x1 + unit.x2) / 2
        thumb_box = (
            card_center_x - preview_width / 2,
            unit.y1 + px(12),
            card_center_x + preview_width / 2,
            unit.y1 + px(12) + preview_height,
        )
        self.workspace.create_rectangle(*thumb_box, fill=c["thumb"], outline="")

        first_page_index = unit.page_indices[0]
        key = (unit.source_id, first_page_index)
        if source.error:
            self.workspace.create_text(
                (thumb_box[0] + thumb_box[2]) / 2,
                (thumb_box[1] + thumb_box[3]) / 2,
                text="转换失败\n点击删除后重试",
                fill=c["danger"],
                font=("Microsoft YaHei UI", 10, "bold"),
                justify="center",
            )
        elif source.converting:
            self.workspace.create_text(
                (thumb_box[0] + thumb_box[2]) / 2,
                (thumb_box[1] + thumb_box[3]) / 2,
                text="Word\n正在生成预览…",
                fill=c["muted"],
                font=("Microsoft YaHei UI", 11, "bold"),
                justify="center",
            )
        elif key in self.thumbnail_images:
            image = self.thumbnail_images[key].copy()
            image.thumbnail(
                (
                    int(thumb_box[2] - thumb_box[0] - px(8)),
                    int(thumb_box[3] - thumb_box[1] - px(8)),
                ),
                Image.Resampling.LANCZOS,
            )
            photo = ImageTk.PhotoImage(image)
            self.thumbnail_photos[key] = photo
            self.workspace.create_image(
                (thumb_box[0] + thumb_box[2]) / 2,
                (thumb_box[1] + thumb_box[3]) / 2,
                image=photo,
            )
        else:
            self.workspace.create_text(
                (thumb_box[0] + thumb_box[2]) / 2,
                (thumb_box[1] + thumb_box[3]) / 2,
                text="正在生成缩略图…",
                fill=c["muted"],
                font=("Microsoft YaHei UI", 9),
            )
            if should_load:
                self._request_thumbnail(source, first_page_index)

        if unit.expanded:
            badge_text = f"第 {first_page_index + 1} 页"
        else:
            badge_text = f"{len(unit.page_ids)} 页" if len(unit.page_ids) > 1 else "1 页"
        badge_width = max(px(48), len(badge_text) * px(12))
        self.workspace.create_rectangle(
            unit.x2 - badge_width - px(18),
            unit.y1 + px(20),
            unit.x2 - px(18),
            unit.y1 + px(46),
            fill=c["accent_soft"],
            outline="",
        )
        self.workspace.create_text(
            unit.x2 - badge_width / 2 - px(18),
            unit.y1 + px(33),
            text=badge_text,
            fill=c["accent"],
            font=("Microsoft YaHei UI", 8, "bold"),
        )

        display_name = self._ellipsize(source.path.name, 23)
        self.workspace.create_text(
            (unit.x1 + unit.x2) / 2,
            thumb_box[3] + px(22),
            text=display_name,
            fill=c["text"],
            font=("Microsoft YaHei UI", 9, "bold"),
            width=max(px(110), unit.x2 - unit.x1 - px(18)),
        )

        can_toggle = active_source_pages > 1 and not source.converting and not source.error
        if can_toggle:
            action_text = "收起文件  ▴" if unit.expanded else "展开页面  ▾"
            action_y = unit.y2 - px(24)
            self.workspace.create_text(
                (unit.x1 + unit.x2) / 2,
                action_y,
                text=action_text,
                fill=c["accent"],
                font=("Microsoft YaHei UI", 8, "bold"),
                tags=("action", f"toggle:{unit.uid}"),
            )

        if hovered:
            self.workspace.create_oval(
                unit.x1 + px(8),
                unit.y1 + px(8),
                unit.x1 + px(36),
                unit.y1 + px(36),
                fill=c["card"],
                outline=c["border"],
                tags=("action", f"delete:{unit.uid}"),
            )
            self.workspace.create_text(
                unit.x1 + px(22),
                unit.y1 + px(21),
                text="×",
                fill=c["danger"],
                font=("Segoe UI", 13, "bold"),
                tags=("action", f"delete:{unit.uid}"),
            )

    def _request_thumbnail(self, source: SourceModel, page_index: int) -> None:
        key = (source.uid, page_index)
        if key in self.thumbnail_pending or key in self.thumbnail_images or source.converting or source.error:
            return
        self.thumbnail_pending.add(key)
        render_path = source.prepared_pdf if source.prepared_pdf else source.path
        future = self.executor.submit(
            self._render_thumbnail,
            render_path,
            source.path.suffix.lower(),
            page_index,
            (self._px(self.THUMBNAIL_SIZE[0]), self._px(self.THUMBNAIL_SIZE[1])),
        )
        future.add_done_callback(lambda completed, thumb_key=key: self._after(self._thumbnail_ready, thumb_key, completed))

    @classmethod
    def _render_thumbnail(
        cls,
        path: Path,
        original_suffix: str,
        page_index: int,
        target_size: tuple[int, int],
    ) -> Image.Image:
        if original_suffix in IMAGE_EXTENSIONS and path.suffix.lower() != ".pdf":
            with Image.open(path) as image:
                image.seek(page_index)
                rendered = ImageOps.exif_transpose(image.copy()).convert("RGB")
        else:
            with fitz.open(path) as document:
                if page_index >= document.page_count:
                    raise MergeError(f"页面不存在：{path.name} 第 {page_index + 1} 页")
                page = document.load_page(page_index)
                scale = min(4.0, max(0.5, target_size[0] / page.rect.width * 1.25))
                pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
                rendered = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
        rendered.thumbnail(target_size, Image.Resampling.LANCZOS)
        return rendered

    def _thumbnail_ready(self, key: tuple[str, int], future: Future[Image.Image]) -> None:
        self.thumbnail_pending.discard(key)
        try:
            self.thumbnail_images[key] = future.result()
        except Exception:
            return
        self._schedule_draw()

    def _on_motion(self, event: tk.Event) -> None:
        if self.drag and self.drag.active:
            return
        unit = self._unit_at(self.workspace.canvasx(event.x), self.workspace.canvasy(event.y))
        unit_id = unit.uid if unit else None
        if unit_id != self.hover_unit_id:
            self.hover_unit_id = unit_id
            if unit:
                self._set_status(str(self.sources[unit.source_id].path))
            self._schedule_draw()

    def _on_leave(self, _event: tk.Event) -> None:
        if not self.drag and self.hover_unit_id is not None:
            self.hover_unit_id = None
            self._schedule_draw()

    def _on_press(self, event: tk.Event) -> str | None:
        if self.busy:
            return "break"
        tags = self.workspace.gettags("current")
        for tag in tags:
            if tag.startswith("toggle:"):
                self._toggle_unit(tag.split(":", 1)[1])
                return "break"
            if tag.startswith("delete:"):
                self._delete_unit(tag.split(":", 1)[1])
                return "break"

        x = self.workspace.canvasx(event.x)
        y = self.workspace.canvasy(event.y)
        unit = self._unit_at(x, y)
        if unit:
            self.selected_page_ids = list(unit.page_ids)
            self.drag = DragState(unit=unit, start_x=x, start_y=y, current_x=x, current_y=y)
            self._schedule_draw()
        else:
            self.selected_page_ids.clear()
            self._schedule_draw()
        return None

    def _on_drag_motion(self, event: tk.Event) -> str | None:
        if not self.drag or self.busy:
            return None
        x = self.workspace.canvasx(event.x)
        y = self.workspace.canvasy(event.y)
        if not self.drag.active and abs(x - self.drag.start_x) + abs(y - self.drag.start_y) < self._px(7):
            return None
        self.drag.active = True
        self.drag.current_x = x
        self.drag.current_y = y
        remaining = [unit for unit in self.units if unit.uid != self.drag.unit.uid]
        self.drag.insert_index = self._find_insert_index(remaining, x, y)
        if event.y < self._px(38):
            self.workspace.yview_scroll(-1, "units")
        elif event.y > self.workspace.winfo_height() - self._px(38):
            self.workspace.yview_scroll(1, "units")
        self._draw_workspace()
        return "break"

    def _on_release(self, _event: tk.Event) -> str | None:
        if not self.drag:
            return None
        drag = self.drag
        self.drag = None
        if drag.active:
            remaining_units = [unit for unit in self.units if unit.uid != drag.unit.uid]
            dragged_ids = set(drag.unit.page_ids)
            dragged_pages = [page for page in self.pages if page.uid in dragged_ids]
            remaining_pages = [page for page in self.pages if page.uid not in dragged_ids]
            if drag.insert_index >= len(remaining_units):
                insert_at = len(remaining_pages)
            else:
                anchor_id = remaining_units[drag.insert_index].page_ids[0]
                insert_at = next(index for index, page in enumerate(remaining_pages) if page.uid == anchor_id)
            self.pages = remaining_pages[:insert_at] + dragged_pages + remaining_pages[insert_at:]
            self._set_status(f"已移动 {len(dragged_pages)} 页。")
        self._schedule_draw()
        return "break"

    def _toggle_unit(self, unit_id: str) -> None:
        unit = self.unit_by_id.get(unit_id)
        if not unit:
            return
        if unit.source_id in self.expanded_sources:
            self.expanded_sources.remove(unit.source_id)
        else:
            self.expanded_sources.add(unit.source_id)
        self.selected_page_ids.clear()
        self._schedule_draw()

    def _delete_unit(self, unit_id: str) -> None:
        unit = self.unit_by_id.get(unit_id)
        if not unit:
            return
        self.selected_page_ids = list(unit.page_ids)
        self._delete_selected()

    def _delete_selected(self) -> None:
        if self.busy or not self.selected_page_ids:
            return
        deleting = set(self.selected_page_ids)
        count = len(deleting)
        self.pages = [page for page in self.pages if page.uid not in deleting]
        active_sources = {page.source_id for page in self.pages}
        removed_sources = [source_id for source_id in self.sources if source_id not in active_sources]
        for source_id in removed_sources:
            self.sources.pop(source_id, None)
            self.expanded_sources.discard(source_id)
            for key in [key for key in self.thumbnail_images if key[0] == source_id]:
                self.thumbnail_images.pop(key, None)
        self.selected_page_ids.clear()
        self._set_status(f"已删除 {count} 页。")
        self._update_summary()
        self._schedule_draw()

    def _unit_at(self, x: float, y: float) -> LayoutUnit | None:
        for unit in self.units:
            if unit.x1 <= x <= unit.x2 and unit.y1 <= y <= unit.y2:
                return unit
        return None

    def _find_insert_index(self, units: list[LayoutUnit], x: float, y: float) -> int:
        if not units:
            return 0
        rows: list[list[LayoutUnit]] = []
        for unit in units:
            if not rows or abs(rows[-1][0].y1 - unit.y1) > self._px(2):
                rows.append([unit])
            else:
                rows[-1].append(unit)
        if y < rows[0][0].y1:
            return 0
        if y > max(unit.y2 for unit in rows[-1]):
            return len(units)
        row = min(
            rows,
            key=lambda items: abs(y - sum(unit.center_y for unit in items) / len(items)),
        )
        row_offset = sum(len(items) for items in rows[: rows.index(row)])
        return row_offset + sum(1 for unit in row if x > unit.center_x)

    def _insertion_marker(self, units: list[LayoutUnit], index: int) -> tuple[float, float, float]:
        if not units:
            pad = self._px(self.CANVAS_PAD)
            return pad, pad, pad + self._px(220)
        gap = self._px(self.CARD_GAP_X)
        extension = self._px(6)
        if index <= 0:
            target = units[0]
            return target.x1 - gap / 2, target.y1 - extension, target.y2 + extension
        if index >= len(units):
            target = units[-1]
            return target.x2 + gap / 2, target.y1 - extension, target.y2 + extension
        target = units[index]
        return target.x1 - gap / 2, target.y1 - extension, target.y2 + extension

    def _scroll_workspace(self, *args: str) -> None:
        self.workspace.yview(*args)
        self._schedule_draw()

    def _on_mousewheel(self, event: tk.Event) -> str:
        direction = -1 if event.delta > 0 else 1
        self.workspace.yview_scroll(direction * 2, "units")
        self._schedule_draw()
        return "break"

    def _export(self) -> None:
        if self.busy:
            return
        if not self.pages:
            messagebox.showinfo("没有可导出的页面", "请先添加文件。", parent=self.root)
            return
        if self.pending_conversions:
            messagebox.showinfo("文档仍在转换", "请等待 Word 文档预览生成完成。", parent=self.root)
            return
        failed = [source.path.name for source in self.sources.values() if source.error]
        if failed:
            messagebox.showerror("存在转换失败的文件", "请先删除或重新添加：\n" + "\n".join(failed), parent=self.root)
            return

        first_source = self.sources[self.pages[0].source_id]
        destination = filedialog.asksaveasfilename(
            parent=self.root,
            title="导出 PDF",
            defaultextension=".pdf",
            initialdir=str(first_source.path.parent),
            initialfile=f"merged_{datetime.now():%Y%m%d_%H%M%S}.pdf",
            filetypes=[("PDF 文件", "*.pdf")],
        )
        if not destination:
            return

        plan = []
        for page in self.pages:
            source = self.sources[page.source_id]
            plan.append(PageSelection(source.path, page.page_index, source.prepared_pdf))
        self._set_busy(True)
        self.progress.configure(mode="determinate", maximum=len(plan), value=0)
        worker = threading.Thread(
            target=self._run_export,
            args=(plan, Path(destination)),
            daemon=True,
        )
        worker.start()

    def _run_export(self, plan: list[PageSelection], destination: Path) -> None:
        try:
            pages = merge_selected_pages(plan, destination, progress=self._thread_progress)
        except Exception as exc:
            self._after(self._export_failed, str(exc))
        else:
            self._after(self._export_finished, destination, pages)

    def _thread_progress(self, current: int, total: int, message: str) -> None:
        self._after(self._apply_progress, current, total, message)

    def _apply_progress(self, current: int, total: int, message: str) -> None:
        self.progress.configure(maximum=total, value=current)
        self._set_status(message)

    def _export_failed(self, message: str) -> None:
        self._set_busy(False)
        self._set_status("导出失败，请检查提示后重试。")
        messagebox.showerror("导出失败", message, parent=self.root)

    def _export_finished(self, destination: Path, pages: int) -> None:
        self._set_busy(False)
        self.progress.configure(value=self.progress.cget("maximum"))
        self._set_status(f"导出完成：{destination.name}（{pages} 页）")
        if messagebox.askyesno(
            "导出完成",
            f"已生成 {pages} 页 PDF：\n{destination}\n\n是否立即打开？",
            parent=self.root,
        ):
            try:
                os.startfile(destination)
            except OSError as exc:
                messagebox.showerror("无法打开文件", str(exc), parent=self.root)

    def _set_busy(self, busy: bool) -> None:
        self.busy = busy
        self._sync_controls()

    def _sync_controls(self) -> None:
        add_state = "disabled" if self.busy else "normal"
        export_state = "disabled" if self.busy or self.pending_conversions else "normal"
        self.add_button.configure(state=add_state)
        self.remove_button.configure(state=add_state)
        self.export_button.configure(state=export_state)

    def _set_status(self, text: str) -> None:
        self.status_label.configure(text=text)

    def _update_summary(self) -> None:
        active_sources = {page.source_id for page in self.pages}
        self.summary_label.configure(text=f"{len(active_sources)} 个文件 · {len(self.pages)} 页")
        self._sync_controls()

    def _schedule_draw(self) -> None:
        if self.closing:
            return
        if self.render_job:
            try:
                self.root.after_cancel(self.render_job)
            except tk.TclError:
                pass
        self.render_job = self.root.after(24, self._draw_workspace)

    def _after(self, callback, *args) -> None:
        if not self.closing:
            self.ui_queue.put((callback, args))

    def _drain_ui_queue(self) -> None:
        self.queue_job = None
        if self.closing:
            return
        while True:
            try:
                callback, args = self.ui_queue.get_nowait()
            except queue.Empty:
                break
            callback(*args)
        self.queue_job = self.root.after(40, self._drain_ui_queue)

    @staticmethod
    def _ellipsize(value: str, limit: int) -> str:
        if len(value) <= limit:
            return value
        stem = Path(value).stem
        suffix = Path(value).suffix
        room = max(6, limit - len(suffix) - 1)
        return f"{stem[:room]}…{suffix}"

    def _close(self) -> None:
        self.closing = True
        for job in (self.render_job, self.queue_job):
            if job:
                try:
                    self.root.after_cancel(job)
                except tk.TclError:
                    pass
        self.executor.shutdown(wait=False, cancel_futures=True)
        try:
            self.temp_dir.cleanup()
        except OSError:
            pass
        self.root.destroy()


def _create_root() -> tk.Tk:
    _enable_windows_dpi_awareness()
    if DND_AVAILABLE and TkinterDnD is not None:
        return TkinterDnD.Tk()
    return tk.Tk()


def main() -> None:
    root = _create_root()
    PdfMergerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
