# iOS 平台壳

智慧金融 Flutter iOS 工程。显示名 **智慧金融**；Dart 业务在 `../lib/`，与 macOS / Android / Windows 共用。

网关地址由用户配置（本机或局域网 HTTP/HTTPS）。ATS 允许任意负载与本地网络（`NSAllowsArbitraryLoads` + `NSAllowsLocalNetworking`），并声明 `NSLocalNetworkUsageDescription`。客户端未使用自定义加密，`ITSAppUsesNonExemptEncryption` 为 false，便于 TestFlight 出口合规。

iOS 无 macOS App Sandbox 的 `com.apple.security.network.client` 需求；`flutter_secure_storage` 走系统 Keychain，无需额外 Keychain Sharing。

## 开发环境

- Flutter stable（SDK ^3.13.1）
- 完整 Xcode。若 `xcode-select -p` 指向 CommandLineTools，用环境变量绕过：

```bash
export DEVELOPER_DIR=/Applications/Xcode-beta.app/Contents/Developer
```

本机若 Xcode 不在该路径，改为实际 `…/Xcode*.app/Contents/Developer`。`xcode-select` 若仍指向 CommandLineTools，Run Script 会把 `scripts/xcrun` 放到 PATH 前：Dart native-asset hook 会丢掉 `DEVELOPER_DIR`，该包装让 `iphoneos` SDK 仍能被找到。

## 运行

```bash
cd flutter_client
export DEVELOPER_DIR=/Applications/Xcode-beta.app/Contents/Developer
flutter pub get
flutter run -d ios
```

## 构建

```bash
cd flutter_client
export DEVELOPER_DIR=/Applications/Xcode-beta.app/Contents/Developer
flutter pub get
flutter build ios --release --no-codesign
```

调试包可用 `flutter build ios --debug --no-codesign`。

TestFlight / App Store 需有效开发者签名与证书，本仓库不提交签名产物。`ephemeral/` 与 `Pods/` 为生成目录，不要提交。
