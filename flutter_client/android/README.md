# Android 原生壳

智慧金融 Android 客户端（`applicationId` `com.smartfinance.flutter_client`，桌面名「智慧金融」）。Dart 业务在 `../lib/`，四端共用。

## 运行

```bash
cd flutter_client
flutter pub get
flutter run -d android
```

模拟器访问宿主机网关用 `http://10.0.2.2:12580`（Genymotion 为 `10.0.3.2`）。真机填局域网 HTTP 地址。

## 构建与签名

```bash
flutter build apk --debug
flutter build apk --release
```

- `compileSdk` 37，Java 17。
- Release 签名读本目录 `key.properties`（已 gitignore，勿提交）。缺失时 `build.gradle.kts` 回退 debug 签名，便于本机与 CI 开箱构建。
- 不要提交 `key.properties`、keystore、`local.properties`。

## 明文 HTTP

用户在网关配置页填写任意 HTTP 地址（局域网 / `127.0.0.1` / 模拟器）。清单开启 `usesCleartextTraffic`，并挂 `app/src/main/res/xml/network_security_config.xml`：`base-config` 允许明文（对齐 macOS `NSAllowsArbitraryLoads`），同时显式放行 `localhost`、`127.0.0.1`、`10.0.2.2`、`10.0.3.2`。
