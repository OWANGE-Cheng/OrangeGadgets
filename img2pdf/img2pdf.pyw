"""
img2pdf — 多张图片合并为单个 PDF
拖放图片到本文件上即可合并，也支持命令行调用。

用法 / Usage:
  拖放图片文件到 img2pdf.pyw 上 → 在图片所在目录生成 merged_<时间戳>.pdf
  命令行:
    python img2pdf.pyw 1.jpg 2.png              # 合并指定文件
    python img2pdf.pyw -o result.pdf *.jpg       # 指定输出文件名
    python img2pdf.pyw -d ./screenshots          # 合并整个目录的图片
"""

import sys
import os
import glob
import argparse
from datetime import datetime

IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp", ".gif"}


def _in_gui_mode() -> bool:
    """检测是否在 GUI 模式（pythonw.exe 启动，无控制台）"""
    return os.path.splitext(sys.executable)[0].endswith("w")  # pythonw.exe


def _report(title: str, msg: str, *, use_gui: bool = False):
    """输出消息——GUI 模式弹窗，CLI 模式打印到 stdout"""
    if use_gui and _in_gui_mode():
        try:
            import tkinter.messagebox as mb
            mb.showinfo(title, msg)
            return
        except Exception:
            pass
    print(f"[{title}]\n{msg}")


def find_images(paths: list[str]) -> list[str]:
    result = []
    for p in paths:
        if os.path.isfile(p):
            if os.path.splitext(p)[1].lower() in IMG_EXTS:
                result.append(p)
        elif os.path.isdir(p):
            for f in sorted(os.listdir(p)):
                if os.path.splitext(f)[1].lower() in IMG_EXTS:
                    result.append(os.path.join(p, f))
        else:
            expanded = sorted(glob.glob(p))
            for f in expanded:
                if os.path.isfile(f) and os.path.splitext(f)[1].lower() in IMG_EXTS:
                    result.append(f)
    return result


def images_to_pdf(image_paths: list[str], output: str, *, use_gui: bool = False):
    if not image_paths:
        _report("img2pdf", "没有找到图片文件。\nNo images found.", use_gui=use_gui)
        return

    from PIL import Image

    imgs = []
    first = None
    failed = []
    for i, path in enumerate(image_paths):
        try:
            img = Image.open(path).convert("RGB")
            if i == 0:
                first = img
            else:
                imgs.append(img)
        except Exception as e:
            failed.append(f"  {os.path.basename(path)}: {e}")

    if first is None:
        _report("img2pdf", f"无法打开任何图片。\nCannot open any image.\n\n" + "\n".join(failed), use_gui=use_gui)
        return

    first.save(output, "PDF", save_all=True, append_images=imgs, resolution=150)
    msg = f"已生成 PDF:\n{output}\n\n共 {len(image_paths)} 张图片"
    if failed:
        msg += f"\n\n以下文件跳过:\n" + "\n".join(failed)
    _report("img2pdf ✓", msg, use_gui=use_gui)


def main():
    # ── 拖放模式: 参数全是文件路径，没有 -o/-d 等选项 ──
    if len(sys.argv) > 1 and not any(a.startswith("-") for a in sys.argv[1:]):
        files = sys.argv[1:]
        images = find_images(files)
        if not images:
            _report("img2pdf", "拖放的文件中没有支持的图片格式。\nNo supported image formats found.", use_gui=True)
            return
        out_dir = os.path.dirname(images[0]) or "."
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = os.path.join(out_dir, f"merged_{ts}.pdf")
        images_to_pdf(images, output, use_gui=True)
        return

    # ── 命令行模式 ──
    parser = argparse.ArgumentParser(
        description="Merge images into a single PDF / 多张图片合并为 PDF"
    )
    parser.add_argument("files", nargs="*", help="图片文件或目录")
    parser.add_argument("-o", "--output", default="output.pdf", help="输出文件名")
    parser.add_argument("-d", "--dir", help="从目录读取所有图片")
    args = parser.parse_args()

    search = []
    if args.dir:
        search.append(args.dir)
    if args.files:
        search.extend(args.files)
    if not search:
        search = ["."]

    images = find_images(search)
    if not images:
        print("No images found. 没有找到图片。")
        return

    print(f"Found {len(images)} image(s)")
    images_to_pdf(images, args.output, use_gui=False)


if __name__ == "__main__":
    main()
