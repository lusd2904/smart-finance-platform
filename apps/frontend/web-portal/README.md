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

Choice is stored in `localStorage` key `sfp-active-theme` and applied on first
paint via `index.html` so the mesh does not flash the wrong theme.

Tokens:

- `src/styles/experience.scss` — byte-aligned with longbridge `experience.scss`
  (`[data-theme=glass-dark|glass-light]`, `.glass-panel` blur 12px)
- `src/styles/theme.scss` — chrome / Element Plus mappings from longbridge
  `App.vue` (`--panel-backdrop` 24px+saturate, `--chrome-backdrop` 28px+saturate,
  `--accent` primary buttons, glass chips, popper/card glass)
- `src/styles/variables.scss` — longbridge SCSS layout vars (unused at runtime)

### Intentional SFP-only deltas

| Delta | Why |
| --- | --- |
| Keep `experience.scss` `body::before` mesh visible | Longbridge `App.vue` later sets `body::before { content: none }`, which kills the glass mesh. We keep the mesh because it **is** the glass-dark/light backdrop. |
| Do not reassign `--page-bg` / `--panel-surface` / `--accent` in `theme.scss` | Lets `[data-theme]` tokens win. Early SFP `theme.scss` overwrote `--panel-surface` with a composed overlay and looked like a third skin. |
| Shell uses `--chrome-surface` + `--chrome-backdrop` | Longbridge `Sidebar.vue` / `Header.vue` hardcode `blur(20px)` + `--panel-surface`. Tokens are the App.vue chrome language the designer asked to close. |
| Primary buttons / EP active states use `--accent` | Designer QA: leftover Element blue and App.vue navy `#164a72` must not win. glass-dark CTA ink is `#06121d` on cyan. |
| `--stat-up` / `--stat-down` neon on glass-dark | `#ff0055` / `#39ff14` (A-share 红涨绿跌 + longbridge neon). glass-light stays `#dc2626` / `#16a34a`. |
| Tables / quote numbers use `tabular-nums` | Designer QA: number columns must not jitter. |
| Pills / chips are tinted glass, not solid neon blocks | Overrides `el-tag` including `effect="dark"`. glass-dark chips use ~15% fill + mixed ink (not solid neon). |
| Brand copy 智慧金融 | Product name only. |
| Stub banner | Shown only in stub/demo. 联调 hide: `VITE_SHOW_STUB_BANNER=false`. |

## Designer QA round 1 (this PR)

| Fix | What changed |
| --- | --- |
| Login habit | Always 账号 / 密码 / 验证码 + 「点击获取」. Does **not** auto-fetch a graphic captcha on mount. CTA is 「登 录」. Footer **演示** is muted and not a peer of the primary path. |
| Numbers + chips | `tabular-nums` on tables / quote / asset figures. Session / market / change / AI / news chips are outline + tint, never solid high-sat blocks. |
| Accent buttons | `--el-color-primary`, primary buttons, switch, radio-button, checkbox, tabs consume `--accent`. |
| Workbench 快捷入口 | Live SFP labels: 交易终端 / 舆情大盘 / 资讯列表 / 行情中心 / 资金与日历 / 行情台 / 财经简报 / 量化策略 / 自选清单 / 市场分析 / **自动分析**. |

### Screenshot note (6 shots)

Prefer capturing glass-dark + glass-light for **登录 / 工作台 / 行情交易**. 金融台大管家 may host the preview separately. Local helper:

```bash
npm run dev
# then, with Playwright + Chrome:
PORTAL_URL=http://127.0.0.1:5180 ARTIFACT_DIR=/opt/cursor/artifacts \
  node scripts/verify-screens.mjs
```

Files: `qa1_login_{dark,light}.png`, `qa1_workbench_{dark,light}.png`, `qa1_terminal_{dark,light}.png`.

## Designer QA round 2 (this PR)

QA1 login habit / accent / tabular-nums / glass chips / 快捷入口 copy must not regress.

| Polish | What changed |
| --- | --- |
| Login mesh quieter | Login uses `<CyberBackground quiet />`: canvas opacity 0.36, particle/line alpha ~42%, fewer shooting lines. Glass card stays the focus. |
| glass-dark 「偏多」 chips | `--chip-fill: 15%` + ink mixed toward `--text-primary`. Stance tags use `--stat-up` / `--stat-down`, not solid neon. |
| Terminal quote colors | Depth / quote / change pills / K-line candles all read `--stat-up` / `--stat-down`. **极速买入 / 卖出** stay A-share solid `--order-buy-solid` `#dc2626` / `--order-sell-solid` `#16a34a`. |
| Stub banner | Shown only in stub/demo. 联调: `VITE_SHOW_STUB_BANNER=false`. |

金融台大管家: re-screenshot glass-dark + glass-light × **登录 / 工作台 / 行情交易** (6 shots) for designer round 3.

## Screens in this slice

| Route | Page | Notes |
| --- | --- | --- |
| `/login` | Login | SFP `POST /login` + 验证码「点击获取」; footer **演示** if API is down |
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
