# 贡献指南

## 分支策略（强制）

- 默认分支：`main`
- **禁止直接向 `main` 推送代码**（包括 force-push）
- 外部协作者与贡献者：请从最新 `main` 拉出功能分支，例如：
  - `feature/xxx`
  - `fix/xxx`
  - `docs/xxx`
- 完成后提交 **Pull Request** 合并到 `main`
- 仓库已开启分支保护：`main` 仅允许通过 PR 合并

## 本地开发注意

1. 复制环境变量模板后自行填写密钥，**不要提交真实密钥**：
   - `ruoyi-fastapi-backend/.env.dockersentiment.example` → `.env.dockersentiment`
   - `ruoyi-fastapi-frontend/.env.docker.example` → `.env.docker`
2. 勿提交 `node_modules/`、`dist/`、`.env*`、密钥与本地数据

## PR 建议

- 说明改动目的与验证方式
- 保持变更聚焦，避免无关格式化
