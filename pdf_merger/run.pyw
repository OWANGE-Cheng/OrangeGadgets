try:
    from pdf_merger.app import main
except ModuleNotFoundError as exc:
    import tkinter as tk
    from tkinter import messagebox

    root = tk.Tk()
    root.withdraw()
    messagebox.showerror(
        "缺少运行依赖",
        f"缺少组件：{exc.name}\n\n请先在本目录运行：\npython -m pip install -r requirements.txt",
        parent=root,
    )
    root.destroy()
    raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
