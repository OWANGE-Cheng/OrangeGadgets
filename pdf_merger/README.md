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
- 悬停卡片可删除文件或单页，鼠标滚轮可纵向浏览
- 支持鼠标拖动框选、`Ctrl+单击`增减选择、`Shift+单击`连续选择
- 多选后可整体拖动、复制、剪切、粘贴或删除
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
- `Ctrl+S`：合并并导出 PDF
- `Ctrl+A`：全选全部文件和页面
- `Ctrl+C / Ctrl+X / Ctrl+V`：复制、剪切、粘贴所选页面
- `Ctrl+Z / Ctrl+Y`：撤销、重做编辑操作
- `Delete / Backspace`：删除所选文件或页面
- `Shift+单击`：从上次选择位置连续选择
- `Ctrl+单击`：增减单个文件或页面的选择状态
- `方向键 / Home / End`：移动当前选择
- `Enter`：展开或收起所选多页文件
- `Esc`：清除选择
- `Ctrl+D`：切换浅色 / 夜间模式

在工作台中单击鼠标右键，也可以打开包含上述常用操作的快捷菜单。

## 测试

```powershell
cd pdf_merger
python -m unittest discover -s tests -v
```
