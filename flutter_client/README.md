# flutter_client

智慧金融四端统一客户端（macOS / Windows / iOS / Android），Flutter 单工程交付。规划基线见 `docs/四端客户端规划.md`。

## 开发环境

- Flutter stable（SDK ^3.13.1）
- macOS 构建需完整 Xcode；若 `xcode-select -p` 指向 CommandLineTools，用环境变量绕过：
  ```bash
  export DEVELOPER_DIR=/Applications/Xcode-beta.app/Contents/Developer
  ```

## 运行

```bash
flutter pub get
flutter run -d macos     # 或 windows / ios / android
```

## 首启流程（复刻 desktop 语义）

网关配置页 → 探测通过才落盘 → 路由放行进登录页。网关填**前端地址**（本机默认 `http://127.0.0.1:12580`），业务 API 自动走 `{网关}/docker-api`；后端端口（19099/9099）不能当网关。

## 测试

```bash
flutter test                                    # 单测（含 dioProvider 回归）
flutter test integration_test -d macos          # M0 冒烟：配网关→探测→登录页（需本地栈在 12580）
dart run tool/probe_smoke.dart                  # 探测判定真实环境冒烟
```

CI：`.github/workflows/flutter.yml` 四平台构建矩阵（analyze + test + apk/ipa/macos/windows 产物）。
