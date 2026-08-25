# flutter_client

智慧金融四端统一客户端（macOS / Windows / iOS / Android），Flutter 单工程交付。Dart 业务在 `lib/`。规划基线见 `docs/四端客户端规划.md`。

**2026-08-25**：macOS 已跟上 Web 交易台、盘前/夜盘、北京时间；当晚把 Android / iOS / Windows 原生壳补回并对齐（HTTP 网关、显示名、桌面窗口尺寸）。

## 开发环境

- Flutter stable（SDK ^3.13.1）
- macOS / iOS 构建需完整 Xcode；若 `xcode-select -p` 指向 CommandLineTools：
  ```bash
  export DEVELOPER_DIR=/Applications/Xcode-beta.app/Contents/Developer
  ```
  路径按本机 Xcode.app 调整。iOS 另有 `ios/scripts/xcrun`：Dart native-asset hook 丢掉 `DEVELOPER_DIR` 时，自动找带 `iphoneos` 的 Xcode。

## 运行

```bash
flutter pub get
flutter run -d macos     # 或 windows / ios / android
```

各端说明：`android/README.md`、`ios/README.md`、`macos/`、`windows/README.md`。

## 首启流程（复刻 desktop 语义）

网关配置页 → 探测通过才落盘 → 路由放行进登录页。网关填**前端地址**（本机默认 `http://127.0.0.1:12580`，Android 模拟器常用 `http://10.0.2.2:12580`），业务 API 自动走 `{网关}/docker-api`；后端端口（19099/9099）不能当网关。

## 测试

```bash
flutter test                                    # 单测（含 dioProvider 回归）
flutter test integration_test -d macos          # 冒烟：配网关→探测→登录页（需本地栈在 12580）
dart run tool/probe_smoke.dart                  # 探测判定真实环境冒烟
```

CI：`.github/workflows/flutter.yml` analyze + test + apk / ios / macos / windows 产物。push 仅 `main` / tag / 向 main 的 PR，避免功能分支狂跑。
