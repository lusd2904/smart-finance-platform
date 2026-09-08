# SFP Web Portal (v2)

New Smart Finance Platform web portal. Visual language is adapted from
[longbridge-platform-core](https://github.com/lusd2904/longbridge-platform-core)
`apps/frontend/web-portal` (`glass-dark` / `glass-light`), branded for **智慧金融**.

This package is a **sibling** of the current production frontend
`ruoyi-fastapi-frontend`. It does **not** replace or delete that tree. Cut over
only after this portal is validated.

## Stack

Vue 3 + Vite + Element Plus + Pinia + vue-router + echarts

## Run

```bash
cd apps/frontend/web-portal
cp .env.development.example .env.development   # optional
npm install
npm run dev
```

Default URL: [http://127.0.0.1:5180](http://127.0.0.1:5180)

| Env | Purpose |
| --- | --- |
| `VITE_APP_BASE_API` | Axios prefix, default `/dev-api` |
| `VITE_PROXY_TARGET` | Vite proxy target. Default `https://sfp.luapi.top/docker-api` (live gateway). Local FastAPI: `http://127.0.0.1:9099` |
| `VITE_USE_STUBS` | `true` to skip live APIs and show labeled stub data |
| `VITE_DEV_PORT` | Dev server port (5180) |

```bash
npm run build
npm run preview   # :4180
```

## Theme toggle

Header and login page expose **皮肤**:

- `幻彩琉璃 (深色)` → `data-theme="glass-dark"`
- `晨曦白玉 (浅色)` → `data-theme="glass-light"`

Choice is stored in `localStorage` key `sfp-active-theme`. Tokens live in
`src/styles/experience.scss` (copied from longbridge) plus `src/styles/theme.scss`
(Element Plus / chrome mappings).

## Screens in this slice

| Route | Page | Notes |
| --- | --- | --- |
| `/login` | Login | SFP `POST /login` + captcha; **演示模式** if API is down |
| `/index` | 工作台 | Same IA as live workbench: sessions, assets, reviews, quick nav, sentiment, heat, quotes, health |
| `/market/terminal` and `/trade/terminal` | 行情交易 | Same component. Top tickers + 自选 / 图表 / 盘口+下单 |
| Other SFP menus | Placeholder | Keep sidebar IA; full pages stay on the old frontend until cutover |

APIs are called when reachable. Failures fall back to a visible **stub banner**
rather than a blank page. Production transport-crypto envelopes are **not**
ported yet — if the live gateway requires them, use local backend or 演示模式.

## Migration plan (keep old until validated)

1. Review this portal against live [https://sfp.luapi.top](https://sfp.luapi.top) on Login / 工作台 / 行情交易.
2. Confirm glass-dark / glass-light matches longbridge, not the abandoned Gemini mockups.
3. Port remaining modules page-by-page from `ruoyi-fastapi-frontend` (do not mass-copy).
4. Add transport-crypto + market WS when wiring production.
5. Only then switch nginx / Flutter WebView from `ruoyi-fastapi-frontend/dist` to this package’s `dist`.
6. Delete the old frontend **after** that confirmation — not in this PR.

## Layout note

Path is `apps/frontend/web-portal` to match longbridge. There is no `ruoyi` in
the new folder name.
