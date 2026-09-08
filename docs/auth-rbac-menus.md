# 认证、RBAC 与菜单（精简后）

Smart Finance Platform 保留 RuoYi 的 **登录会话 + 用户/角色/菜单权限** 能力，已移除系统监控、代码生成、表单构建、部门/岗位/字典/参数/通知等 RuoYi 管理台页面。

## 前端契约（保持不变）

| 接口 | 用途 |
|------|------|
| `POST /login` | 登录，返回 JWT |
| `GET /captchaImage` | 验证码（若启用） |
| `GET /getInfo` | 当前用户、角色、权限标识 |
| `GET /getRouters` | 动态侧边栏与路由树 |
| `POST /logout` | 退出 |

流程：`permission.js` → token → `getInfo` → `generateRoutes` → `getRouters`。

## 系统管理菜单（IAM）

执行 `sql/strip-ruoyi-admin-menus.sql` 后，**系统管理** 下仅保留：

- **用户管理**（`system/user`）
- **角色管理**（`system/role`）
- **菜单管理**（`system/menu`）

个人中心（`/user/profile`）为静态路由，不依赖菜单 SQL。

## 后端保留说明

| 模块 | 说明 |
|------|------|
| `login_controller` | 登录、注册、getInfo、getRouters |
| `user_controller` / `role_controller` / `menu_controller` | IAM CRUD |
| `dept_controller` | **无管理页**；用户/角色表单仍调用 `deptTree` |
| `dict_controller` / `config_controller` | **无管理页**；`useDict`、`getConfigKey` 只读依赖 |
| `captcha_controller` | 验证码 |
| `transport_crypto_controller` | 仅 `frontend-config` / `public-key`（监控页已移除） |

已删除 HTTP 层：监控（在线/任务/日志/缓存/服务/Druid）、代码生成、通知/岗位管理 API。

SFP 业务模块（行情、交易、量化、舆情、AI、任务中心等）**未改动**。

## 任务与健康

- 定时任务运维请使用 **任务中心**（`analysis:job:*`，菜单见 `analysis-scheduler.sql`）。
- 工作台「运行健康」块权限由 `monitor:job:list` 改为 `analysis:job:list`。

## 新环境 / 已有库

- **新装**：`ruoyi-fastapi.sql` 种子已同步精简菜单。
- **已有库**：执行 `sql/strip-ruoyi-admin-menus.sql`，然后用户重新登录。

## 各模块「使用说明」

业务子系统说明仍通过 `GET /common/guide/{module}` 与 `views/guide/index.vue` 提供，菜单见 `subsystem-guides.sql`。
