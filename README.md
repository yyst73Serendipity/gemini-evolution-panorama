# Gemini / Google AI 产品与模型演进全景

一个整理 Google AI 技术前史、Gemini 模型家族、产品生态、开发者平台和订阅计划演进的纯前端单文件时间线项目。网页运行时不需要后端、框架、CDN、远程字体或远程脚本；Python 仅用于本地构建和 GitHub Actions 自动维护。

## ✨ 功能介绍

- 覆盖 2017 年 Transformer 至当前核验日期的重要演进事件，首版包含 44 条人工核验事件。
- 统一展示模型、消费级产品、开发者平台、企业生态、订阅计划、安全治理和生命周期。
- 使用 Google、Google DeepMind、Google Cloud、Google for Developers 等官方页面、发布说明和模型卡作为事实来源。
- 提供全文搜索、年份/类别/产品线/生命周期组合筛选、重大节点开关、年份导航和 URL 状态恢复。
- 支持浅色、深色、跟随系统三态主题，响应式布局、键盘焦点、减少动画、阅读进度和打印样式。
- 所有事件预渲染进单个 HTML；禁用 JavaScript 时仍可完整阅读。
- 每天北京时间 08:30 自动检查 11 个官方入口，有可信内容变化时才受限提交 4 个发布文件。
- 每次工作流均生成 GitHub Pages 临时站点，即使没有事实变化，也能展示本次最近检查时间而不改写仓库。

## 📁 项目目录结构

```text
gemini/
├── .github/
│   └── workflows/
│       └── update-gemini-panorama.yml   # 每日检查、测试、受限提交和 Pages 发布
├── docs/
│   ├── source-audit.md                   # 官方来源、事实核验和收录边界
│   └── superpowers/
│       ├── plans/                        # 实施计划
│       └── specs/                        # 设计规格
├── outputs/
│   └── gemini-evolution-panorama.html    # 可离线打开的单文件网页
├── tests/
│   ├── test_auto_update.py               # 去重、失败保护和原子替换测试
│   ├── test_gemini_evolution_panorama.py # 页面结构、交互和离线约束测试
│   ├── test_source_parser.py             # 官方来源解析与分类测试
│   ├── test_timeline_data.py             # 数据契约和首版覆盖测试
│   └── test_workflow_static.py           # 工作流权限与提交边界测试
├── work/
│   ├── build-page.py                     # 单文件静态页面构建器
│   ├── source-config.json                # 11 个官方监控入口及来源等级
│   ├── source-state.json                 # 已见 URL、稳定哈希和来源健康状态
│   ├── source_parser.py                  # Feed、Sitemap、HTML 和发布说明解析器
│   ├── timeline-data.json                # 结构化事件数据
│   ├── timeline_core.py                  # 校验、指纹与原子 JSON 写入
│   └── update-gemini-panorama.py         # 自动发现、暂存验证和回滚更新器
├── .gitignore
├── AGENTS.md
├── CHANGELOG.md
└── README.md
```

## 🧰 技术栈

- HTML、CSS、原生 JavaScript
- Python 3 标准库
- GitHub Actions
- GitHub Pages

项目不引入运行时第三方依赖。网页中的数据、样式和交互全部内嵌，打开来源链接时才会访问网络。

## 🚀 安装和使用方式

### 生成离线网页

```bash
python3 work/build-page.py
```

默认输出：

```text
outputs/gemini-evolution-panorama.html
```

构建器会先校验时间线数据，再将来源状态中的最近检查时间写入页面。可只覆盖页面显示时间，不回写时间线：

```bash
python3 work/build-page.py \
  --checked-at "2026-10-22T08:30:00+08:00" \
  --output /tmp/gemini-panorama.html
```

### 运行测试

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

测试夹具会以当前时间线的 `cutoff` 构造检查时间，避免官方资料更新后因固定旧日期触发误报。

检查内嵌 JavaScript：

```bash
python3 - <<'PY'
from pathlib import Path
import re
html = Path("outputs/gemini-evolution-panorama.html").read_text(encoding="utf-8")
scripts = re.findall(r'<script(?![^>]*type="application/json")[^>]*>(.*?)</script>', html, re.S)
Path("/tmp/gemini-panorama-script.js").write_text("\n".join(scripts), encoding="utf-8")
PY
node --check /tmp/gemini-panorama-script.js
```

## 🔄 自动更新

### 首次建立基线

首次启用自动化时必须先执行 bootstrap。它会抓取当前官方入口，记录已见条目、稳定正文哈希和来源健康状态，但不会把历史内容批量新增到时间线：

```bash
python3 work/update-gemini-panorama.py \
  --bootstrap \
  --result-path /tmp/gemini-update-result.json
```

### 正常检查

```bash
python3 work/update-gemini-panorama.py \
  --result-path /tmp/gemini-update-result.json
```

结果 JSON 包含：

- `additions`：新增事件数。
- `source_state_changed`：来源 URL、稳定哈希或健康状态是否变化。
- `content_changed`：是否需要提交仓库文件。
- `checked_at_changed`：本次检查时间是否不同。
- `changed_paths`：经过白名单约束的实际变更文件。
- `checked_at`：供 Pages 临时构建展示的本次检查时间。

只有新增/合并事件、稳定正文哈希或来源健康状态变化才会替换正式文件。**只有检查时间变化时，时间线、来源状态、离线 HTML 和 CHANGELOG 均保持字节不变。**

更新器先在仓库内临时目录完成数据校验、页面构建和离线约束检查，全部成功后才替换正式文件；替换中途失败会恢复已经替换的文件。解析器会按匹配的 HTML 结束标签恢复正文范围，并忽略 void 标签，避免 Google DevSite 导航结构污染发布说明；列表页文章 URL 会在抓取前立即记入已见状态，避免后续重复抓取。必需来源全部失败、低置信候选、未来日期、重复事实或单次超过 20 条新增都会停止或拒绝发布。

## ⚙️ GitHub Actions 与 Pages

工作流：`.github/workflows/update-gemini-panorama.yml`

- 定时：每天 UTC 00:30，即北京时间 08:30。
- 触发：定时运行或 GitHub Actions 手动 `workflow_dispatch`。
- 流程：官方来源检查 → 页面构建 → JavaScript 语法检查 → 全部测试 → Pages 临时构建 → 有内容变化时受限提交 → Pages 部署。
- 自动提交只允许以下文件：
  - `work/timeline-data.json`
  - `work/source-state.json`
  - `outputs/gemini-evolution-panorama.html`
  - `CHANGELOG.md`
- Pages 同时发布 `index.html` 和可下载副本 `gemini-evolution-panorama.html`。

GitHub Pages 发布后，站点仍是纯前端静态文件；自动检查逻辑只在 GitHub Actions 中运行。

## 📚 来源策略与维护边界

- 自动来源以 Google、Google DeepMind、Google Cloud、Google for Developers、Workspace Updates、Gemini Help 和 Google One 官方页面为主。
- Sitemap 的 `lastmod` 只作为变更线索，不用作历史发布日期；首次日期优先采用 `datePublished`、官方发布时间或明确的发布说明日期。
- 自动候选必须包含明确日期、标题、A/B 级官方 HTTPS 来源和高置信 Gemini 关联；描述采用保守模板，不推断未公布的性能、价格、地区或商业指标。
- 首版资料已人工核验至 2026-10-22；这是经过筛选的演进档案，不是 Google 全部 AI 新闻的镜像。
- Google 官方 X/Twitter 账号仅用于人工发现和补充，不进入自动抓取主链路。
- 设计规格：`docs/superpowers/specs/2026-10-22-gemini-evolution-panorama-design.md`
- 实施计划：`docs/superpowers/plans/2026-10-22-gemini-evolution-panorama-implementation.md`
- 来源审计：`docs/source-audit.md`
- 计划发布仓库：`yyst73Serendipity/gemini-evolution-panorama`
