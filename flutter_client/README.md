# flutter_client

智慧金融四端统一客户端（macOS / Windows / iOS / Android），Flutter 单工程交付。Dart 业务在 `lib/`。规划基线见 `docs/四端客户端规划.md`。

**2026-08-26 (V11)**：

- **桌面宽屏**（macOS / Windows）：登录后 WebView 打开网关 Web 控制台（`/portal`），页面与 Docker Web 同一份。
- **手机**：原生五栏——舆情 / 选股 / 热度 / 持仓 / 我的。
- **默认网关**：`https://sfp.luapi.top`。本机 Docker 在网关页改 `http://127.0.0.1:12580`。

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

未配置或仍是模拟器环回（`10.0.2.2` / `10.0.3.2`）时，回落到线上 `https://sfp.luapi.top`。本机 Docker 请在网关页改 `http://127.0.0.1:12580`（Android 模拟器 `http://10.0.2.2:12580`）。网关必须是**前端地址**，业务 API 走 `{网关}/docker-api`；后端端口（19099/9099）不能当网关。

## 测试

```bash
flutter test                                    # 单测（含 dioProvider 回归）
flutter test integration_test -d macos          # 冒烟：配网关→探测→登录页（需本地栈在 12580）
dart run tool/probe_smoke.dart                  # 探测判定真实环境冒烟
```

CI：`.github/workflows/flutter.yml` analyze + test + apk / ios / macos / windows 产物。push 仅 `main` / tag / 向 main 的 PR，避免功能分支狂跑。
