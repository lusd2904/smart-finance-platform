# Windows 宿主

本机（macOS）不能交叉编译 Windows。发布 zip 与 NSIS 安装包由 CI `build-windows`（`.github/workflows/flutter.yml`）在 `windows-latest` 上产出：`sff-windows.zip`、`sff-windows-setup.exe`。

安装脚本：`packaging/installer.nsi`。CI 以绝对路径 `/DSRCDIR` 指向 `build/windows/x64/runner/Release`，再 `File /r "${SRCDIR}\*.*"`。

在 Windows 机器上本地运行：

```bat
cd flutter_client
flutter run -d windows
```

默认窗口 1440×900，最小 1100×700，标题「智慧金融分析平台」，启动后在主显示器工作区居中。
