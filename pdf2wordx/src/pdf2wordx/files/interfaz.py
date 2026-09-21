from __future__ import annotations

from tkinter import Tk
from typing import Any


class Window:
    """创建并管理应用程序主窗口。"""

    def __init__(
        self,
        root: Tk,
        width: int = 300,
        height: int = 300,
        bg_color: str = "green",
        title: str = "窗口",
        resizable: tuple[bool, bool] = (False, False),
    ) -> None:
        self.root = root
        self.width = width
        self.height = height
        self.bg_color = bg_color
        self.title = title
        self.resizable = resizable
        self._create_window()

    def _create_window(self) -> None:
        self.root["bg"] = self.bg_color
        self.root.title(self.title)
        self.root.geometry(f"{self.width}x{self.height}{self._center_window()}")
        self.root.resizable(self.resizable[0], self.resizable[1])

    def _center_window(self) -> str:
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        center_x = (screen_width - self.width) // 2
        center_y = (screen_height - self.height) // 2
        return f"+{center_x}+{center_y}"

    def loop_window(self) -> None:
        self.root.mainloop()


class Widgets:
    """根据配置列表创建 Tk 控件。"""

    def __init__(self, master: Any, elements: list[type]) -> None:
        self.master = master
        self.elements = elements
        self.widgets_list: list[Any] = []
        self.config_items: list[dict] = []

    def widgets_create(
        self,
        item_options: list[dict] | None = None,
        package: list[str] | None = None,
        pack_options: list[dict] | None = None,
    ) -> None:
        item_options = item_options or [{}]
        package = package or []
        pack_options = pack_options or [{}]
        try:
            for index, widget_type in enumerate(self.elements):
                self._create_widget(item_options, package, pack_options, index, widget_type)
        except Exception as exc:
            print("创建界面控件时出错：", exc)

    def _create_widget(
        self,
        item_options: list[dict],
        pack_types: list[str],
        pack_options: list[dict],
        index: int,
        widget_type: type,
    ) -> None:
        if index >= len(item_options):
            return
        widget = widget_type(self.master, **item_options[index])
        self.widgets_list.append(widget)
        self.config_items.append(item_options[index])
        self._choose_pack_options(index, pack_options, pack_types, widget)

    def _choose_pack_options(
        self,
        index: int,
        pack_options: list[dict],
        pack_types: list[str],
        widget: Any,
    ) -> None:
        options = pack_options[index] if index < len(pack_options) else {}
        pack_type = pack_types[index] if index < len(pack_types) else "pack"
        pack_method = getattr(widget, pack_type, None)
        if callable(pack_method):
            pack_method(**options)

    def get_text(self, position: int) -> str:
        return self.widgets_list[position].get()
