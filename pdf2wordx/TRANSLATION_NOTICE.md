# 简体中文翻译与集成说明

本目录来源于 Tutos Rive 的 `pdf2wordx` v2.1.1 源代码包（源目录标识 `tutosrive-pdf2wordx-6024661`）。

## 上游信息

- 项目名称：pdf2wordx
- 原作者：Tutos Rive
- 上游仓库：<https://github.com/tutosrive/pdf2wordx/>
- 上游主页：<https://tutosrive.github.io/pdf2wordx/>
- 上游版本：2.1.1
- 许可证：MIT

## OrangeGadgets 的改动范围

1. 将桌面界面、文件选择窗口、状态提示、错误提示、帮助及 NOTICE 翻译为简体中文。
2. 将原本依赖当前工作目录的包导入、图标、帮助文件和日志路径改为稳定路径，以便作为 OrangeGadgets 子工具运行。
3. 增加 `run.pyw`、中文 README 和基础本地化测试。
4. 对取消文件/目录选择等情况增加必要保护，不改变 `pdf2docx` 转换核心。
5. 用 Python 标准日志替换仅用于日志记录、且导入时会输出西班牙语提示的 `chromologger`；不影响文件转换功能。
6. 按 Windows 显示缩放比例调整窗口尺寸，使简体中文界面在高 DPI 屏幕上保持清晰且不重叠。
7. 为 `run.pyw` 增加首次启动引导：缺少依赖时自动创建本地 `.venv`、显示安装进度，并在失败时提供中文错误窗口和日志路径。

OrangeGadgets 仅承担上述翻译与集成工作。原始作者、上游链接及许可证均予以保留。西班牙语 README 原文见 [UPSTREAM_README_ES.md](./UPSTREAM_README_ES.md)，上游 MIT License 见 [LICENSE](./LICENSE)。
