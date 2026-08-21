# 智慧金融桌面端

Electron 壳。启动后**先配置网关地址**，探测通过才打开平台登录页。

本机 Docker 与云上部署的入口不同，桌面端不内置业务服务，只连接你填写的前端网关。

## 网关怎么填

| 场景 | 地址 | 说明 |
|------|------|------|
| 本机 Docker | `http://127.0.0.1:12580` | `docker-compose.sentiment.yml` 默认前端，已反向代理 `/docker-api` |
| 局域网 | `http://<这台机器的 IP>:12580` | 手机/另一台电脑不要填 127.0.0.1 |
| 云上 | `https://your-domain` | 已部署的前端入口，不是后端 `19099` / `9099` |

后端 API 端口不能当网关用。填错时桌面会提示。

## 开发启动

```bash
cd desktop
npm install
npm start
```

**每次启动都会先打开网关配置窗**（已保存的地址会预填）。探测通过并点「进入」后才打开登录页。菜单 **平台 → 网关设置** 可随时改地址。

## 打包

```bash
cd desktop
npm run dist:mac    # macOS dmg/zip
npm run dist:win    # Windows 安装包
npm run dist:linux  # AppImage
```

产物在 `desktop/release/`。安装包同样会先弹出网关配置窗，探测通过后才打开登录页。
