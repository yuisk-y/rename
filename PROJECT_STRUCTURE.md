# 项目结构规划

```text
file_sort_renamer/
├─ main.py                 # 程序入口
├─ app/
│  ├─ __init__.py
│  ├─ dialogs.py           # 确认对话框
│  ├─ file_model.py        # 文件/文件夹列表、排序、屏蔽、搜索定位和预览模型
│  ├─ history.py           # 最近一次重命名历史与撤销记录
│  ├─ main_window.py       # PySide6 主窗口和交互逻辑
│  ├─ naming.py            # 旧序号清理、新名称生成、Windows 名称校验
│  └─ rename_service.py    # 预检查、两阶段重命名、失败回滚、撤销执行
├─ tests/
│  ├─ test_file_model.py
│  ├─ test_history.py
│  ├─ test_naming.py
│  └─ test_rename_service.py
├─ requirements.txt        # 运行、测试和打包依赖
├─ build.ps1               # PyInstaller Windows 单文件打包脚本
├─ README.md               # 使用说明
├─ PROJECT_STRUCTURE.md    # 项目结构说明
└─ .gitignore
```

## 仓库保留内容

- 保留源码、测试、文档、依赖声明和打包脚本。
- 不提交 `dist/`、`build/`、`*.spec`、缓存目录和日志。
- `dist\重命名工具.exe` 由 `.\build.ps1` 重新生成。

