# PDF 合并与转换

一个本地运行的 Windows 图形化小工具。可将 PDF、图片、DOC、DOCX 拖入窗口，预览内容、拖动调整顺序，最后合并导出为一个 PDF。

## 功能

- 窗口内拖入文件，也可点击“添加文件”选择文件
- Acrobat 风格的多行缩略图工作台，文件首页直接显示在预览卡片中
- 根据首页实际宽高比生成卡片；横向、竖向和方形页面不再强制使用同一尺寸
- 卡片随窗口宽度自动换行，并通过鼠标滚轮纵向浏览
- 多页文件默认以堆叠卡片显示，可展开为每一页的独立缩略图
- 折叠时拖动整个文件；展开后可抽出任意单页参与跨文件排序
- 支持浅色 / 夜间模式切换（`Ctrl+D`），当前选择会自动保留
- “设置”中可指定启动时跟随系统、使用浅色模式或使用夜间模式
- 支持 Windows Per-Monitor V2 高 DPI，主界面、缩略图和系统文件窗口均按显示器原生分辨率渲染
- 悬停卡片可删除文件或单页，鼠标滚轮可横向浏览
- 支持 PDF、JPG、PNG、BMP、TIFF、WebP、GIF、DOC、DOCX
- 图片自动转换为 PDF；多帧 TIFF / GIF 会保留为多页
- DOC / DOCX 优先使用 Microsoft Word 转换，未安装 Word 时自动尝试 LibreOffice
- 转换和合并全程在本机完成，不上传文件

## 安装与运行

建议使用 Python 3.10 或更高版本：

```powershell
cd pdf_merger
python -m pip install -r requirements.txt
python run.pyw
```

也可以直接双击 `run.pyw` 启动。若双击没有反应，请先按上面的命令安装依赖。

DOC / DOCX 转换还需要满足以下任一条件：

1. Windows 已安装 Microsoft Word；或
2. 已安装 LibreOffice。

## 快捷操作

- `Ctrl+O`：添加文件
- `Delete`：移除所选文件
- `Ctrl+D`：切换浅色 / 夜间模式

## 测试

```powershell
cd pdf_merger
python -m unittest discover -s tests -v
```
