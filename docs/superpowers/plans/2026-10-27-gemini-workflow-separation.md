# Gemini 更新与 Pages 发布工作流拆分实施计划

## 目标

将“官方资料更新”和“GitHub Pages 发布”拆分为两条职责单一的 GitHub Actions 工作流，使人工推送到 `main` 后也会自动部署最新页面，同时保留每日官方来源检查、受限提交和无事实变化时刷新“最近检查时间”的能力。

## 涉及文件

### 新增

- `.github/workflows/deploy-gemini-pages.yml`：独立构建、验证并部署 GitHub Pages。
- `docs/superpowers/plans/2026-10-27-gemini-workflow-separation.md`：记录本次实施计划。

### 修改

- `.github/workflows/update-gemini-panorama.yml`：仅负责官方资料检查、构建验证、受限提交，并复用调用发布工作流。
- `tests/test_workflow_static.py`：分别约束更新和发布工作流的触发器、权限、职责、产物及安全步骤顺序。
- `README.md`：同步工作流拆分后的目录结构、自动更新和发布说明。
- `CHANGELOG.md`：记录工作流拆分和 `main` 推送自动发布能力。

## 实现步骤

1. 先修改静态工作流测试，分别定义更新工作流和发布工作流的预期行为。
2. 运行测试，确认测试因发布工作流不存在、旧工作流仍混合部署职责而失败。
3. 新增独立 Pages 发布工作流，支持 `main` 推送、手动触发和可复用调用。
4. 修改官方资料更新工作流，移除 Pages 部署职责，输出 `checked_at` 并调用发布工作流。
5. 更新 README 与 CHANGELOG，使文档与实际自动化保持一致。
6. 运行完整单元测试、Python 语法检查、JSON 校验和 Git 差异检查。
7. 提交并安全推送到远程 `main`，等待 GitHub Actions 与 Pages 完成后验证线上页面。

## 关键设计决策

- 更新工作流仅持有 `contents: write`；发布工作流仅持有 `contents: read`、`pages: write`、`id-token: write`，避免单一工作流拥有不必要的组合权限。
- 更新工作流使用 `workflow_call` 调用发布工作流，确保 GitHub Actions 机器人推送不会触发普通 `push` 工作流时仍能完成部署。
- 发布工作流监听 `main` 的 `push`，确保人工推送 UI 或代码更新后立即发布。
- 发布工作流接受可选字符串输入 `checked_at`：自动检查后可把本轮检查时间写进临时站点；普通推送时则沿用仓库 `source-state.json` 中的时间。
- 发布工作流统一检出 `main`，发布远程主分支的最新状态，不部署更新工作流提交前的旧检出内容。
- 保留 `cancel-in-progress: false`，避免正在进行的 Pages 部署被后续运行直接取消。
- 不引入第三方依赖，不修改时间线数据、来源数据或页面 UI。
