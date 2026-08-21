# Smart Finance Platform - 待办事项清单

## 1. refactor-common-templates
✅ 已完成。`common/dao/`、`common/service/` 提供 BaseDAO / BaseService 模板。现有行情/量化 DAO 继续用 classmethod + `Depends(db)`，避免一次改光所有调用点。

## 2. backend-di-event-driven
✅ 已完成。Controller 使用 FastAPI `Depends()`；`common/aspect/` 处理鉴权与会话。长任务走 Redis 队列（见第 5 条），APScheduler 入队，worker 消费。

## 3. frontend-component-abstraction
✅ 已完成。`src/components/shared/` 导出 Sidebar、TagsView、HeaderSearch、SvgIcon；布局与导航改为从 shared 引用。

## 4. migrate-to-postgres
⏭ 保持 MySQL 为默认生产栈。`docker-compose.pg.yml` 与 `sql/ruoyi-fastapi-pg.sql` 已存在，见 `docs/DEPLOY.md`。不切换正在运行的 sentiment 栈。

## 5. add-background-queue
✅ 已完成。`utils/job_queue.py` Redis 列表队列（不引入 Celery）。行情同步、因子日扫/质检、舆情采集、自选分析、指标快照：队列可用则入队，否则同步执行。

## 6. async-longbridge
✅ 已完成。异步封装 + Redis JSON 缓存 + 最小调用间隔节流。

## 7. svg-sprite-frontend
✅ 已完成。`vite-plugin-svg-icons` 已打 sprite；`SvgIcon` 改为 `<script setup>`。

## 8. echarts-optimization
✅ 已完成。`src/composables/useEChart.js`：init / setOption / resize / dispose。自选、因子雷达、舆情趋势已接入。

## 9. add-monitoring
✅ 已完成。`docker-compose.monitor.yml` + Prometheus `/metrics` + Grafana。启动方式见 `docs/DEPLOY.md`。

## 10. security-audit-log
✅ 已完成。`middlewares/audit_middleware.py` 记录方法/路径/状态/用户/耗时（不记请求体）。登录等接口已有 `ApiRateLimit`。

## 11. modernize-frontend-permission
✅ 已完成。`permission.js` 改为 Vue Router 4 async guard；`usePermission` composable；`v-hasPermi` 走 composable。

## 12. add-e2e-tests
✅ 已完成。`scripts/web_e2e.mjs` 覆盖工作台、自选、因子、策略、交易台、订单、行情台、通知、分市场、舆情。

## 13. improve-docs
✅ 已完成。README 增加监控入口；`docs/DEPLOY.md`；根目录 `.env.example` 指向各环境示例文件。

## 14. upgrade-mobile-app
⏭ 移动端暂不升级（此前约定）。`ruoyi-fastapi-app/` 保持现状。

## 15. dependency-management
⏭ 前端继续 npm lockfile；后端继续 `uv.lock`。不切换 pnpm workspaces。
