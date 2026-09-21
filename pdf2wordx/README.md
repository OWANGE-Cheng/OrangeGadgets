# PDF2WORDX 简体中文版

将 PDF 文件离线转换为可编辑的 DOCX 文档，带有简体中文图形界面。

## 来源与翻译声明

本工具基于 **Tutos Rive** 开发的开源项目 [pdf2wordx](https://github.com/tutosrive/pdf2wordx/) **v2.1.1**。

- 原作者：Tutos Rive（SRM / TRG）
- 上游项目主页：<https://tutosrive.github.io/pdf2wordx/>
- 上游源代码：<https://github.com/tutosrive/pdf2wordx/>
- 上游许可证：MIT，完整文本见 [LICENSE](./LICENSE)
- OrangeGadgets 所做工作：简体中文翻译、项目目录集成，以及让资源路径不依赖启动目录的必要兼容性调整

OrangeGadgets **不是该工具的原作者**，也未宣称对转换核心作出原创贡献。西班牙语上游 README 原文保存在 [UPSTREAM_README_ES.md](./UPSTREAM_README_ES.md)，更完整的说明见 [TRANSLATION_NOTICE.md](./TRANSLATION_NOTICE.md)。

转换功能由 [ArtifexSoftware/pdf2docx](https://github.com/ArtifexSoftware/pdf2docx) 提供。程序内“开源许可”窗口和 `src/pdf2wordx/files/info/NOTICE*` 保留了相关声明。

## 功能

- 选择单个 PDF 文件并转换为 DOCX
- 自动沿用原 PDF 的文件名与所在目录，也可手动修改
- 显示文档分析、逐页解析和 DOCX 生成进度
- 转换引擎跳过无法解析的页面时明确提示页码
- 本地离线转换，不上传文件
- 简体中文界面、提示框、帮助和许可说明

PDF 与 DOCX 的排版模型不同，复杂页面、特殊字体、非 RGB 图片或扫描件可能出现样式偏差、文字错位或内容缺失。转换前请保留原始文件。

## 已知限制与后续优化方向

当前版本已经可以完成日常 PDF 转 DOCX 操作，但转换质量仍受 `pdf2docx` 转换引擎能力限制，后续主要关注：

- 改善转换后 Word 文档中的段落、图片、表格等排版错位。
- 改善数学公式、上下标和公式编号的位置与可编辑性。
- 提升复杂学术论文的解析和渲染成功率，避免个别页面因复杂矢量图形或表格结构而被跳过。

这些项目仅作为后续优化记录，不影响当前版本的基本使用。

## 环境要求

- Python 3.8–3.14
- Windows、Linux 或 macOS（图标设置在非 Windows 平台会自动跳过）

## 安装与运行

Windows 下可以直接双击 `run.pyw`。首次启动时程序会自动在本目录创建 `.venv` 运行环境并安装转换组件；这一过程需要网络连接，通常需要一到数分钟。后续启动会直接复用该环境。

也可以手动安装：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\pythonw.exe run.pyw
```

如果自动准备失败，错误窗口会给出 `setup.log` 的位置，可据此查看详细原因。

也可以安装为本地包：

```powershell
python -m pip install .
pdf2wordx
```

## 使用方法

1. 点击“选择 PDF 文件”。
2. 程序会自动沿用原 PDF 的文件名，并把原目录设为默认保存位置。
3. 如有需要，修改输出文件名或选择其他输出目录。
4. 点击“开始转换”，可在窗口底部查看当前阶段、页码和总体进度。

转换期间无需处理额外的“正在转换”提示框。若某页无法由转换引擎解析，程序会继续处理其余页面，并在完成时列出被跳过的页码。

## 许可证

本子工具继续使用上游 MIT License。原作者版权声明未经删除或替换：

> Copyright (c) 2025 Tutos Rive

详见 [LICENSE](./LICENSE)。依赖库 `pdf2docx` 的许可条件以其上游发布内容为准。
