# Gemini / Google AI 产品与模型演进全景 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建并发布一套覆盖 2017 年至实际核验日期的 Gemini / Google AI 模型、产品、开发者平台和订阅计划全景网页，并通过 GitHub Actions 每天自动检查官方来源、验证、重建和发布。

**Architecture:** 使用 Python 3 标准库维护结构化时间线、解析 Google 官方来源并在构建时生成包含全部数据、CSS 和 JavaScript 的单文件 HTML。历史事件由官方来源人工核验后写入数据文件，自动更新器只发布高置信度事件；更新过程先在临时目录构建并校验，再原子替换，GitHub Actions 负责完整测试、受限提交和 Pages 发布。

**Tech Stack:** Python 3.12 标准库、HTML5、CSS3、原生 JavaScript、`unittest`、GitHub Actions、GitHub Pages。

**Spec:** `docs/superpowers/specs/2026-10-22-gemini-evolution-panorama-design.md`

## Global Constraints

- 事实范围从 2017 年 Transformer 开始，截止日期使用任务实际运行日期；不得虚构未来事件。
- 自动事实主来源仅限 Google、Google DeepMind、Google Cloud、Google Developers、Google Workspace、Android、Chrome 和 Search 官方网站。
- X/Twitter 仅作人工发现和补充，不进入 GitHub Actions 自动抓取主链路。
- 页面必须是纯前端单文件 HTML，构建时预渲染全部事件，无 JavaScript 时仍可阅读。
- 不引入第三方运行时依赖、前端框架、CDN、外部字体或图片热链；新增依赖必须再次获得用户确认。
- Python 文件顶部写中文多行用途注释，核心函数和复杂判断使用简洁中文注释。
- 新增功能必须同步增加根目录 `tests/` 下的测试，并同步更新 README。
- 所有外部输入在系统边界校验：HTTPS、允许域名、日期、内容长度、事件数量和文件修改范围。
- 没有可靠事实变化时不生成空事件，不更新 `content_updated_at`，不创建仅含时间戳的 Git 提交。
- 自动任务只能提交 `work/timeline-data.json`、`work/source-state.json`、`outputs/gemini-evolution-panorama.html` 和 `CHANGELOG.md`。
- 手工 Git commit、远程仓库创建和 push 仅在用户明确授权后执行；计划中的提交信息只是建议检查点。

---

## File Map

| 文件 | 单一职责 |
|---|---|
| `work/timeline_core.py` | 定义枚举、官方域名、数据校验、事件指纹和原子 JSON 写入 |
| `work/timeline-data.json` | 保存页面全部结构化历史事件和内容更新时间 |
| `work/source-config.json` | 声明发现源、监控页、关键词和必需/可选级别 |
| `work/source-state.json` | 保存已知 URL、页面稳定正文哈希、来源健康状态和最近检查时间 |
| `work/source_parser.py` | 解析 RSS/Atom、sitemap、页面元数据和发布说明条目 |
| `work/update-gemini-panorama.py` | 抓取来源、分类候选事件、去重、暂存构建和原子更新 |
| `work/build-page.py` | 校验时间线并生成可离线使用的单文件 HTML |
| `outputs/gemini-evolution-panorama.html` | GitHub Pages 首页和可下载网页产物 |
| `tests/test_timeline_data.py` | 验证数据契约、日期、来源、谱系引用和代表性里程碑 |
| `tests/test_gemini_evolution_panorama.py` | 验证单文件 HTML、预渲染、交互钩子、无障碍和离线约束 |
| `tests/test-source-parser.py` | 验证 Google 官方源解析、日期提取、域名限制和分类 |
| `tests/test_auto_update.py` | 验证去重、置信度、边界、无变化行为和原子替换 |
| `tests/test_workflow_static.py` | 验证工作流时间、权限、测试、提交范围和 Pages 部署 |
| `.github/workflows/update-gemini-panorama.yml` | 每天北京时间 08:30 更新、测试和发布 |
| `docs/source-audit.md` | 记录首版历史资料核验方法、来源覆盖和边界决策 |
| `CHANGELOG.md` | 记录事实数据或项目能力的实际变化 |
| `README.md` | 说明功能、结构、命令、自动化和发布地址 |

---

### Task 1: 建立数据契约和核心校验模块

**Files:**
- Create: `work/timeline_core.py`
- Create: `work/timeline-data.json`
- Create: `work/source-state.json`
- Create: `tests/test_timeline_data.py`
- Create: `CHANGELOG.md`
- Modify: `README.md`

**Interfaces:**
- Produces: `load_timeline(path: Path) -> dict`
- Produces: `validate_timeline(data: dict, today: date | None = None) -> None`
- Produces: `canonical_source_url(url: str) -> str`
- Produces: `event_fingerprint(event: dict) -> str`
- Produces: `write_json_atomic(path: Path, payload: dict) -> None`
- Produces constants: `ALLOWED_HOSTS`, `CATEGORIES`, `LIFECYCLES`, `IMPORTANCE_LEVELS`, `VERIFICATION_LEVELS`

- [ ] **Step 1: 先写数据契约失败测试**

在 `tests/test_timeline_data.py` 中通过 `sys.path.insert(0, str(ROOT / "work"))` 导入 `timeline_core`，至少写出以下独立场景：

```python
def test_rejects_event_after_cutoff(self) -> None:
    data = self.valid_data()
    data["events"][0]["date"] = "2026-10-23"
    with self.assertRaisesRegex(ValueError, "晚于截止日期"):
        validate_timeline(data, today=date(2026, 10, 22))


def test_rejects_non_official_source(self) -> None:
    data = self.valid_data()
    data["events"][0]["sources"][0]["url"] = "https://example.com/gemini"
    with self.assertRaisesRegex(ValueError, "非允许的官方来源"):
        validate_timeline(data, today=date(2026, 10, 22))


def test_rejects_duplicate_event_id(self) -> None:
    data = self.valid_data()
    data["events"].append(dict(data["events"][0]))
    with self.assertRaisesRegex(ValueError, "重复事件 ID"):
        validate_timeline(data, today=date(2026, 10, 22))
```

另写测试覆盖：必填字段、日期精度、升序、枚举值、空来源、非 HTTPS、前序/后续引用不存在、自引用、重复指纹、`content_updated_at <= cutoff`、`cutoff <= today` 和原子写入。

- [ ] **Step 2: 运行测试并确认因模块不存在而失败**

Run:

```bash
python3 -m unittest tests/test_timeline_data.py -v
```

Expected: `ModuleNotFoundError: No module named 'timeline_core'`。

- [ ] **Step 3: 实现核心模块和明确枚举**

`work/timeline_core.py` 使用以下数据边界：

```python
CATEGORIES = {"技术基础", "模型", "产品", "开发者平台", "订阅计划", "生态集成", "研究", "安全治理", "生命周期"}
LIFECYCLES = {"研究", "预览", "发布", "升级", "更名", "降价", "迁移", "弃用"}
IMPORTANCE_LEVELS = {"major", "standard"}
VERIFICATION_LEVELS = {"人工核验", "自动收录", "官方社交补充"}
ALLOWED_HOSTS = {
    "research.google", "ai.google", "ai.google.dev", "blog.google",
    "deepmind.google", "developers.googleblog.com", "cloud.google.com",
    "workspaceupdates.googleblog.com", "support.google.com",
    "one.google.com", "gemini.google.com", "android.com",
    "blog.google.com", "chromium.org", "x.com", "twitter.com",
}
```

来源对象固定包含 `label`、`url`、`grade`、`type`；X/Twitter 来源只能使用 `grade="C"`、`type="official-social"`，且所属事件必须标记 `verification="官方社交补充"`。自动来源配置不得包含 X/Twitter。

事件必填字段固定为：

```python
EVENT_REQUIRED = {
    "id", "date", "date_precision", "category", "families", "lifecycle",
    "title", "summary", "difference", "optimization", "availability",
    "significance", "importance", "predecessors", "successors", "sources",
    "first_seen_at", "verified_at", "auto_generated", "verification",
}
```

`canonical_source_url()` 必须移除 fragment、追踪参数和多余尾斜杠，保留有语义的查询参数；`event_fingerprint()` 对日期、规范化标题、类别、生命周期和主来源 URL 计算 SHA-256；`write_json_atomic()` 在目标目录创建临时文件、`flush()`、`os.fsync()` 后 `os.replace()`。

- [ ] **Step 4: 创建最小合法时间线数据**

`work/timeline-data.json` 使用以下顶层结构，并先放入 2017 Transformer 这一条经官方论文核验的最小事件：

```json
{
  "schema_version": 1,
  "title": "Gemini / Google AI 产品与模型演进全景",
  "cutoff": "2026-10-22",
  "content_updated_at": "2026-10-22T00:00:00+08:00",
  "events": []
}
```

实际事件必须补齐 `EVENT_REQUIRED` 全部字段，来源使用 Transformer 官方论文页 `https://research.google/pubs/attention-is-all-you-need/`；`date_precision` 使用官方页面可核验的精度，不人为补日。

同时创建初始 `work/source-state.json`：

```json
{
  "last_checked_at": "2026-10-22T00:00:00+08:00",
  "known_urls": [],
  "page_hashes": {},
  "source_health": {}
}
```

该时间表示首版人工核验状态，不代表自动抓取已经运行。

- [ ] **Step 5: 运行测试并修正到全部通过**

Run:

```bash
python3 -m unittest tests/test_timeline_data.py -v
```

Expected: 所有数据契约单元测试通过。

- [ ] **Step 6: 更新 README 和 CHANGELOG**

README 增加 `timeline_core.py`、时间线字段说明和校验命令；CHANGELOG 使用 `# 更新日志` 标题并记录“建立项目数据契约与官方来源边界”。

- [ ] **Step 7: 检查变更并保留提交检查点**

Run:

```bash
git diff --check
git status --short
```

建议提交信息（仅用户明确授权后执行）：`新增: 建立 Gemini 时间线数据契约`。

---

### Task 2: 调研并建立首版历史时间线

**Files:**
- Modify: `work/timeline-data.json`
- Modify: `tests/test_timeline_data.py`
- Create: `docs/source-audit.md`
- Modify: `README.md`
- Modify: `CHANGELOG.md`

**Interfaces:**
- Consumes: Task 1 的数据契约和 `validate_timeline()`。
- Produces: 覆盖 2017 至实际核验日的首版人工核验事件集。

- [ ] **Step 1: 写代表性覆盖失败测试**

增加独立测试，要求首版语料至少覆盖以下稳定主线，不要求不存在官方事实的年份强行产生事件：

```python
def test_representative_milestones_are_covered(self) -> None:
    corpus = " ".join(
        f"{event['title']} {event['summary']} {' '.join(event['families'])}"
        for event in self.events
    )
    expected = (
        "Transformer", "BERT", "LaMDA", "PaLM", "PaLM 2", "Bard",
        "Gemini 1.0", "Gemini 1.5", "Gemini 2.0", "Gemini 2.5",
        "Gemma", "Google AI Studio", "Vertex AI", "NotebookLM",
        "Project Astra", "Gemini Live", "Deep Research",
        "Google One AI Premium", "Google AI Pro", "Google AI Ultra",
        "Gemini Code Assist", "Jules",
    )
    for phrase in expected:
        with self.subTest(phrase=phrase):
            self.assertIn(phrase, corpus)
```

再写测试要求所有主要类别均有事件，`major` 事件都有 `difference`、`optimization` 和 `significance` 的非模板化描述，并要求每条事件至少一个 A/B 级官方来源。

- [ ] **Step 2: 运行测试并确认代表性覆盖失败**

Run:

```bash
python3 -m unittest tests/test_timeline_data.py -v
```

Expected: 代表性里程碑和类别覆盖测试失败。

- [ ] **Step 3: 只从官方来源建立事实清单**

按以下顺序浏览和核验，优先打开正文、发布说明和模型卡；搜索结果本身不作为来源：

1. `research.google`：Transformer、BERT 等论文和研究项目。
2. `blog.google`：Bard、Gemini App、订阅计划、Workspace、Android、Search、Chrome 集成。
3. `deepmind.google`：Gemini 模型发布、模型卡、Project Astra、研究能力。
4. `ai.google.dev`：Gemini API、Google AI Studio、模型与发布说明。
5. `cloud.google.com`：Vertex AI、企业发布和模型生命周期。
6. `developers.googleblog.com`：开发者工具、Gemini Code Assist、Gemini CLI、Jules。
7. `workspaceupdates.googleblog.com` 与 `support.google.com`：Workspace、计划权益和产品可用性。
8. `one.google.com`：Google AI 订阅计划的正式名称、价格与权益页面。

每个事件核验发布日期、标题、具体更新、前序差异、优化重点、可用范围和意义；日期不精确时降低 `date_precision`。任何截至核验日尚未出现于官方页面的未来版本都不进入数据。

- [ ] **Step 4: 写入首版事件并建立关系**

至少形成以下演进链：

```text
Transformer → BERT → LaMDA → PaLM → PaLM 2 → Gemini 1.0
Gemini 1.0 → Gemini 1.5 → Gemini 2.0 → Gemini 2.5 → 后续已核验版本
Bard → Gemini App → Gemini Live / Deep Research / Canvas
Google AI Studio → Gemini API 重要版本 → Vertex AI 生命周期事件
Google One AI Premium → Google AI Pro / Google AI Ultra
Gemma 首发 → 重要 Gemma 版本
```

`predecessors` 和 `successors` 使用稳定事件 ID；一项公告影响多个产品时保留一条主事件，通过 `families` 和多个来源表达，不重复建卡。

- [ ] **Step 5: 编写来源审计文档**

`docs/source-audit.md` 必须记录：

- 首版核验截止日期和时区。
- 官方域名白名单。
- 每个主要产品线使用的主来源类型。
- 日期冲突处理方式。
- X/Twitter 只作人工补充的规则。
- 未收录 AlphaGo、AlphaFold、普通 Google 更新和纯营销内容的原因。
- 自动化不能可靠提炼前后差异时使用保守措辞，不推断未公布指标。

- [ ] **Step 6: 运行数据测试**

Run:

```bash
python3 -m unittest tests/test_timeline_data.py -v
```

Expected: 契约、边界、代表性里程碑、类别覆盖和引用关系全部通过。

- [ ] **Step 7: 更新 README、CHANGELOG 并检查 diff**

README 增加来源审计入口和事件覆盖说明；CHANGELOG 记录首版资料核验范围。运行：

```bash
git diff --check
git status --short
```

建议提交信息（仅用户明确授权后执行）：`新增: 建立 Google AI 历史时间线`。

---

### Task 3: 实现静态页面构建器和预渲染结构

**Files:**
- Create: `work/build-page.py`
- Create: `tests/test_gemini_evolution_panorama.py`
- Create: `outputs/gemini-evolution-panorama.html`
- Modify: `README.md`

**Interfaces:**
- Consumes: `timeline_core.load_timeline()`、`validate_timeline()` 和 `work/source-state.json` 中最近一次已发布检查状态。
- Produces: `format_event_date(event: dict) -> str`
- Produces: `build_event_card(event: dict) -> str`
- Produces: `build_page(data: dict) -> str`
- Produces: `write_page(output_path: Path, html_text: str) -> None`
- CLI: `python3 work/build-page.py [--data PATH] [--state PATH] [--output PATH] [--checked-at ISO_DATETIME]`

- [ ] **Step 1: 写页面结构失败测试**

`tests/test_gemini_evolution_panorama.py` 先运行构建器，再断言：

```python
def test_page_is_single_file_and_contains_prerendered_events(self) -> None:
    html = self.output.read_text(encoding="utf-8")
    self.assertIn("<!doctype html>", html.lower())
    self.assertNotRegex(html, r'<(?:script|link|img)[^>]+(?:src|href)="https?://')
    self.assertEqual(html.count('class="event-card"'), len(self.data["events"]))
    self.assertIn("<noscript>", html)


def test_every_event_has_filter_attributes_and_source_links(self) -> None:
    html = self.output.read_text(encoding="utf-8")
    for event in self.data["events"]:
        self.assertIn(f'id="event-{event["id"]}"', html)
        self.assertIn(f'data-year="{event["date"][:4]}"', html)
        for source in event["sources"]:
            self.assertIn(source["url"], html)
```

另写测试覆盖：页面标题、截止日、事件统计、年份导航、七个主要章节、语义 `<main>`/`<nav>`/`<article>`、`lang="zh-CN"`、viewport、打印样式和 HTML 转义。

- [ ] **Step 2: 运行测试并确认构建器不存在**

Run:

```bash
python3 -m unittest tests/test_gemini_evolution_panorama.py -v
```

Expected: 构建器文件不存在或输出文件不存在。

- [ ] **Step 3: 实现构建器基础结构**

`build-page.py` 必须：

- 使用 `argparse` 支持自定义数据、来源状态、输出路径和只用于 Pages 临时产物的检查时间覆盖值。
- 页面“最近自动检查时间”优先使用 `--checked-at`，否则使用 `source-state.json` 的 `last_checked_at`；覆盖值不得回写时间线数据。
- 使用 `html.escape(str(value), quote=True)` 转义所有数据字段。
- 先调用 `validate_timeline()`，再生成页面。
- 按年份升序生成语义时间线；每年有稳定锚点 `year-YYYY`。
- 预渲染首屏统计、模型谱系摘要、产品矩阵、订阅计划摘要、全部事件和来源方法。
- 每张卡包含 `data-year`、`data-category`、`data-family`、`data-lifecycle`、`data-importance` 和供搜索使用的规范文本。
- 使用 `details/summary` 展示“与前序相比、优化重点、可用范围、为什么重要”。
- 通过临时文件和 `os.replace()` 写输出。

事件卡接口保持：

```python
def build_event_card(event: dict) -> str:
    """把一条已校验事件渲染成可搜索、可筛选的静态档案卡。"""
    source_links = "".join(
        f'<a href="{esc(source["url"])}">{esc(source["label"])}</a>'
        for source in event["sources"]
    )
    return (
        f'<article class="event-card" id="event-{esc(event["id"])}" '
        f'data-year="{esc(event["date"][:4])}" '
        f'data-category="{esc(event["category"])}" '
        f'data-family="{esc("|".join(event["families"]))}" '
        f'data-lifecycle="{esc(event["lifecycle"])}" '
        f'data-importance="{esc(event["importance"])}">'
        f'<h3>{esc(event["title"])}</h3><p>{esc(event["summary"])}</p>'
        f'<div class="sources">{source_links}</div></article>'
    )
```

- [ ] **Step 4: 生成首版 HTML 并运行测试**

Run:

```bash
python3 work/build-page.py
python3 -m unittest tests/test_gemini_evolution_panorama.py -v
```

Expected: 页面结构和预渲染测试通过。

- [ ] **Step 5: 更新 README 并检查 diff**

README 增加构建命令和输出文件说明。运行：

```bash
git diff --check
git status --short
```

建议提交信息（仅用户明确授权后执行）：`新增: 生成 Gemini 单文件全景网页`。

---

### Task 4: 完成 Gemini 独立视觉、筛选和无障碍交互

**Files:**
- Modify: `work/build-page.py`
- Modify: `tests/test_gemini_evolution_panorama.py`
- Regenerate: `outputs/gemini-evolution-panorama.html`
- Modify: `README.md`

**Interfaces:**
- Consumes: Task 3 的预渲染 DOM 和 `data-*` 属性。
- Produces browser functions: `applyFilters()`, `syncUrlState()`, `restoreUrlState()`, `setTheme(theme)`, `updateReadingProgress()`。

- [ ] **Step 1: 写交互与视觉钩子失败测试**

独立断言以下静态结构和脚本标识存在：

```python
def test_interaction_controls_and_accessibility_hooks_exist(self) -> None:
    html = self.html
    for token in (
        'id="timeline-search"', 'id="category-filter"',
        'id="family-filter"', 'id="lifecycle-filter"',
        'id="major-only"', 'id="theme-toggle"',
        'id="result-count"', 'aria-live="polite"',
        'function applyFilters()', 'function syncUrlState()',
        'function restoreUrlState()', 'function setTheme(',
        'function updateReadingProgress()',
    ):
        self.assertIn(token, html)
```

另写测试确保存在 `prefers-color-scheme`、`prefers-reduced-motion`、`:focus-visible`、`@media print`、跳到主内容链接、筛选无结果提示和 `localStorage` 主题键 `gemini-panorama-theme`。

- [ ] **Step 2: 运行测试并确认交互测试失败**

Run:

```bash
python3 -m unittest tests/test_gemini_evolution_panorama.py -v
```

Expected: 新增的交互和无障碍断言失败。

- [ ] **Step 3: 实现 Gemini 独立视觉系统**

在生成器内嵌 CSS 中使用：

- 蓝、紫、青色变量和高对比正文变量。
- CSS 渐变与伪元素绘制克制星芒，不使用远程图片。
- 档案式最大阅读宽度、年份粘性目录、卡片层级和紧凑元信息。
- 深色主题通过 `data-theme="dark"` 覆盖变量。
- `prefers-reduced-motion: reduce` 禁止非必要过渡。
- 打印时隐藏导航、筛选和主题按钮，展开事件详情并保留来源 URL。

- [ ] **Step 4: 实现筛选、搜索和 URL 状态**

脚本使用事件委托和原生 DOM API：

```javascript
function applyFilters() {
  const query = normalizeText(searchInput.value);
  const selectedCategory = categoryFilter.value;
  const selectedFamily = familyFilter.value;
  const selectedLifecycle = lifecycleFilter.value;
  const majorOnly = majorOnlyInput.checked;
  let visible = 0;
  eventCards.forEach((card) => {
    const matches = (!query || card.dataset.search.includes(query))
      && (!selectedCategory || card.dataset.category === selectedCategory)
      && (!selectedFamily || card.dataset.family.split("|").includes(selectedFamily))
      && (!selectedLifecycle || card.dataset.lifecycle === selectedLifecycle)
      && (!majorOnly || card.dataset.importance === "major");
    card.hidden = !matches;
    if (matches) visible += 1;
  });
  resultCount.textContent = `显示 ${visible} / ${eventCards.length} 条事件`;
  emptyState.hidden = visible !== 0;
  syncUrlState();
}
```

URL 查询参数固定为 `q`、`category`、`family`、`lifecycle`、`major`；主题使用 `light`、`dark`、`system` 三种状态。脚本不得从网络加载数据。

- [ ] **Step 5: 检查内嵌 JavaScript 语法**

Run:

```bash
python3 work/build-page.py
python3 - <<'PY'
from pathlib import Path
import re
html = Path("outputs/gemini-evolution-panorama.html").read_text(encoding="utf-8")
scripts = re.findall(r'<script(?![^>]*type="application/json")[^>]*>(.*?)</script>', html, re.S)
Path("/tmp/gemini-panorama-script.js").write_text("\n".join(scripts), encoding="utf-8")
PY
node --check /tmp/gemini-panorama-script.js
```

Expected: Node 返回成功，无 JavaScript 语法错误。

- [ ] **Step 6: 运行页面测试并做桌面/移动端人工检查**

Run:

```bash
python3 -m unittest tests/test_gemini_evolution_panorama.py -v
```

然后在浏览器检查 1440px、768px 和 390px 宽度，验证：首屏信息密度、年份粘性导航、筛选结果、深色主题、键盘焦点、详情展开和打印预览。发现问题只修改生成器，再重新生成输出，禁止直接手改产物。

- [ ] **Step 7: 更新 README 并检查 diff**

README 增加搜索、筛选、URL 状态、主题、打印和无 JavaScript 能力。建议提交信息（仅用户明确授权后执行）：`优化: 完成 Gemini 全景交互与视觉`。

---

### Task 5: 实现官方来源解析和候选分类

**Files:**
- Create: `work/source_parser.py`
- Create: `tests/test-source-parser.py`
- Create: `work/source-config.json`
- Modify: `README.md`

**Interfaces:**
- Consumes: `timeline_core.canonical_source_url()` 和官方域名白名单。
- Produces: `parse_feed(text: str) -> list[dict]`
- Produces: `parse_sitemap(text: str) -> list[dict]`
- Produces: `parse_page_metadata(text: str, url: str) -> dict`
- Produces: `parse_release_notes(text: str, url: str) -> list[dict]`
- Produces: `stable_page_text(text: str) -> str`
- Produces: `classify_candidate(text: str) -> dict`

- [ ] **Step 1: 写解析器失败测试**

使用仓库内嵌的最小官方格式样本，不伪造远程调用结果，分别测试：

```python
def test_parse_atom_uses_published_date_and_official_link(self) -> None:
    atom = """<feed xmlns="http://www.w3.org/2005/Atom"><entry>
      <title>Gemini model update</title>
      <link href="https://blog.google/products/gemini/example/"/>
      <published>2026-10-20T01:00:00Z</published>
      <summary>Official Gemini update.</summary>
    </entry></feed>"""
    item = parse_feed(atom)[0]
    self.assertEqual(item["date"], "2026-10-20")
    self.assertEqual(item["url"], "https://blog.google/products/gemini/example")


def test_sitemap_lastmod_is_not_publish_date(self) -> None:
    xml = """<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://deepmind.google/models/gemini/example/</loc>
      <lastmod>2026-10-20</lastmod></url></urlset>"""
    item = parse_sitemap(xml)[0]
    self.assertEqual(item["lastmod"], "2026-10-20")
    self.assertNotIn("date", item)
```

另写测试覆盖 RSS、JSON-LD `datePublished`、OpenGraph、HTML `<time>`、无发布日期页面、非官方 URL、稳定正文去导航噪声，以及 Gemini/Gemma/Bard/NotebookLM/开发者平台/订阅/生命周期分类。

- [ ] **Step 2: 运行测试并确认模块不存在**

Run:

```bash
python3 -m unittest tests/test-source-parser.py -v
```

Expected: `ModuleNotFoundError: No module named 'source_parser'`。

- [ ] **Step 3: 实现标准库解析器**

- RSS/Atom 和 sitemap 使用 `xml.etree.ElementTree`。
- HTML 元数据使用 `html.parser.HTMLParser`，只提取 title、meta、JSON-LD、time 和主内容稳定文本。
- 日期使用 `datetime.fromisoformat()`、`email.utils.parsedate_to_datetime()` 和明确的年月日正则；不从 `lastmod` 推断发布日期。
- JSON-LD 同时支持对象、数组和 `@graph`，优先 `datePublished`，不使用 `dateModified` 作为首次日期。
- `stable_page_text()` 排除 `nav`、`footer`、`script`、`style`、cookie banner 等不稳定区域。
- `classify_candidate()` 返回 `category`、`families`、`lifecycle`、`confidence` 和 `matched_keywords`，没有明确 Gemini 关联时返回 `confidence="low"`。

- [ ] **Step 4: 配置来源并逐个实网验证**

`work/source-config.json` 配置以下核心页面；实施时先对每个 URL 发起真实 HTTPS GET，若发生官方重定向则保存最终规范 URL：

```text
https://ai.google.dev/gemini-api/docs/changelog
https://cloud.google.com/vertex-ai/generative-ai/docs/release-notes
https://deepmind.google/models/model-cards/
https://blog.google/products/gemini/
https://developers.googleblog.com/
https://workspaceupdates.googleblog.com/
https://support.google.com/gemini/
https://ai.google.dev/gemini-api/docs/models
https://ai.google.dev/gemini-api/docs/pricing
https://cloud.google.com/vertex-ai/generative-ai/docs/learn/model-versions
https://one.google.com/about/google-ai-plans/
```

配置字段固定为 `name`、`label`、`type`、`url`、`required`、`grade`、`path_prefixes`、`required_keywords`；结构化发布说明和 Gemini API changelog 标记为必需源，普通产品博客和帮助中心标记为可选源。

- [ ] **Step 5: 运行解析器测试和真实来源只读检查**

Run:

```bash
python3 -m unittest tests/test-source-parser.py -v
python3 - <<'PY'
import json
from pathlib import Path
from urllib.request import Request, urlopen
config = json.loads(Path("work/source-config.json").read_text(encoding="utf-8"))
for source in config["sources"]:
    request = Request(source["url"], headers={"User-Agent": config["user_agent"]})
    with urlopen(request, timeout=30) as response:
        print(response.status, response.geturl())
PY
```

Expected: 单元测试通过；所有必需源返回成功的 HTTPS 响应，可选源失败时记录原因并评估是否更换为稳定官方入口。

- [ ] **Step 6: 更新 README 并检查 diff**

README 增加来源配置和实网检查说明。建议提交信息（仅用户明确授权后执行）：`新增: 解析 Gemini 官方更新来源`。

---

### Task 6: 实现自动更新、去重和原子替换

**Files:**
- Create: `work/update-gemini-panorama.py`
- Modify: `work/source-state.json`
- Create: `tests/test_auto_update.py`
- Modify: `work/build-page.py`
- Modify: `README.md`
- Modify: `CHANGELOG.md`

**Interfaces:**
- Consumes: `timeline_core`、`source_parser`、`build-page.py`、`source-config.json`。
- Produces: `fetch_text(url: str, user_agent: str, timeout: int = 30) -> tuple[str, str]`
- Produces: `build_candidate_event(metadata: dict, source: dict, checked_at: str) -> dict`
- Produces: `merge_candidates(existing: list[dict], candidates: list[dict], cutoff: str, max_additions: int = 20) -> tuple[list[dict], list[dict]]`
- Produces: `stage_update(paths: UpdatePaths, candidates: list[dict], checked_at: datetime) -> UpdateResult`
- Produces: `apply_staged_update(result: UpdateResult) -> None`
- CLI: `python3 work/update-gemini-panorama.py [--bootstrap] [--result-path PATH]`

- [ ] **Step 1: 写更新器失败测试**

测试纯函数和临时目录中的真实文件操作，不 mock 远程服务返回：

```python
def test_merge_rejects_future_and_duplicate_candidates(self) -> None:
    merged, accepted = merge_candidates(
        self.existing_events(),
        [self.duplicate_candidate(), self.future_candidate(), self.new_candidate()],
        cutoff="2026-10-22",
    )
    self.assertEqual([item["id"] for item in accepted], ["2026-10-20-gemini-example"])
    self.assertEqual(len(merged), len(self.existing_events()) + 1)


def test_timestamp_only_check_does_not_mark_content_changed(self) -> None:
    result = stage_update(
        paths=self.temp_paths(),
        candidates=[],
        checked_at=datetime(2026, 10, 22, 8, 30, tzinfo=ZoneInfo("Asia/Shanghai")),
    )
    self.assertFalse(result.content_changed)
    self.assertTrue(result.checked_at_changed)
```

另写测试覆盖：同 URL 去重、不同 URL 同事实指纹合并、多来源附加、单次超过 20 条终止、低置信度不发布、必需源全部失败终止、可选源失败继续、构建失败不替换、JSON 写入失败不替换、替换中途失败时回滚已替换文件、自动事件保守措辞和允许修改文件清单。

- [ ] **Step 2: 运行测试并确认更新器不存在**

Run:

```bash
python3 -m unittest tests/test_auto_update.py -v
```

Expected: 更新器文件或接口不存在导致失败。

- [ ] **Step 3: 实现候选事件和置信度规则**

`build_candidate_event()` 只接受：

- 明确 `date` 和 `title`。
- A/B 级官方 HTTPS 来源。
- 分类结果为 high，或满足全部中置信度条件。
- 日期不晚于截止日。
- 标题、摘要和稳定正文至少命中一个 Gemini 关联关键词。

自动生成字段采用保守模板：

```python
"difference": "相较此前公开状态，Google 官方新增或更新了该模型、产品或平台信息；具体差异以官方原文为准。",
"optimization": "优化重点以官方公布的能力、效率、可用范围或开发者工作流说明为准。",
"significance": "该条目用于标记 Google AI 官方演进中的新节点，不推断官方未公布的性能或商业指标。",
"verification": "自动收录",
"auto_generated": True,
```

如果来源正文提供明确能力、上下文、价格、地区或迁移事实，允许使用经过清洗的原文摘要替换模板，但不得生成来源没有表达的比较结论。

- [ ] **Step 4: 实现暂存、构建和原子替换**

使用 `tempfile.TemporaryDirectory(dir=ROOT)` 暂存：

1. 新 `timeline-data.json`。
2. 新 `source-state.json`。
3. 新 `CHANGELOG.md`。
4. 调用 `build-page.py --data TEMP_DATA --output TEMP_HTML` 生成新 HTML。
5. 调用 `validate_timeline()` 并检查 HTML 事件数、doctype 和禁止远程资源规则。
6. 所有检查通过后才对单个正式文件使用 `os.replace()`；替换前保留同目录备份，任一步失败时恢复已替换文件。
7. 如果只有检查时间变化而没有事实、来源哈希或来源健康状态变化，不替换任何跟踪文件；把本次 `checked_at` 写入仓库外的结果 JSON，供 Pages 临时构建使用。

`UpdateResult` 使用 `dataclasses.dataclass`：

```python
@dataclass(frozen=True)
class UpdateResult:
    additions: int
    source_state_changed: bool
    content_changed: bool
    checked_at_changed: bool
    changed_paths: tuple[str, ...]
```

只有新增/合并事件、来源哈希变化或来源健康状态变化才令 `content_changed=True`；仅 `checked_at` 变化不替换时间线、状态、HTML 或 CHANGELOG，也不创建提交。结果 JSON 必须包含本次 `checked_at`，供工作流生成不回写仓库的 Pages 临时 HTML。

- [ ] **Step 5: 实现 bootstrap 和来源状态**

`--bootstrap` 必须抓取当前来源，将发现到的 URL 和页面哈希写入 `source-state.json`，但不自动新增事件，用于避免首次启用自动化时把历史页面重复收录。状态结构固定包含：

```json
{
  "last_checked_at": "2026-10-22T08:30:00+08:00",
  "known_urls": [],
  "page_hashes": {},
  "source_health": {}
}
```

正常模式读取这些状态，只处理新 URL、发生稳定正文变化的监控页和新增发布说明条目。仅检查时间变化时，新的检查时间只写结果 JSON；当事实、哈希或健康状态变化需要提交时，才同步更新 `source-state.json` 的 `last_checked_at`。

- [ ] **Step 6: 运行更新器测试并执行 bootstrap 实网验证**

Run:

```bash
python3 -m unittest tests/test_auto_update.py -v
python3 work/update-gemini-panorama.py --bootstrap --result-path /tmp/gemini-update-result.json
cat /tmp/gemini-update-result.json
python3 work/build-page.py
```

Expected: 单元测试通过；bootstrap 不新增时间线事件；结果文件显示 `additions: 0`；必需源健康；页面可重新构建。

- [ ] **Step 7: 验证无变化运行和文件边界**

连续运行两次：

```bash
cp work/timeline-data.json /tmp/gemini-timeline-before.json
python3 work/update-gemini-panorama.py --result-path /tmp/gemini-update-result.json
cmp /tmp/gemini-timeline-before.json work/timeline-data.json
python3 -m unittest tests/test_auto_update.py -v
```

如果没有新官方事实，`cmp` 必须成功，`content_updated_at` 不变，且 `git diff -- work/timeline-data.json work/source-state.json outputs/gemini-evolution-panorama.html CHANGELOG.md` 为空；仅检查时间变化不得被视为事实变化。

- [ ] **Step 8: 更新 README、CHANGELOG 并检查 diff**

README 增加 bootstrap、正常更新、结果文件和失败策略命令；CHANGELOG 记录自动更新能力。建议提交信息（仅用户明确授权后执行）：`新增: 自动同步 Gemini 官方资料`。

---

### Task 7: 配置每日工作流和 GitHub Pages 发布

**Files:**
- Create: `.github/workflows/update-gemini-panorama.yml`
- Create: `tests/test_workflow_static.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: 更新器 CLI、构建器 CLI、四组测试和生成 HTML。
- Produces: 每日北京时间 08:30 和手动触发的 Pages 工作流。

- [ ] **Step 1: 写工作流静态失败测试**

测试必须精确验证：

```python
def test_daily_schedule_and_manual_trigger(self) -> None:
    self.assertIn('cron: "30 0 * * *"', self.workflow)
    self.assertRegex(self.workflow, r"(?m)^\s*workflow_dispatch:\s*$")


def test_commit_scope_is_explicit(self) -> None:
    self.assertNotRegex(self.workflow, r"git add\s+(?:-|--\s+)?[.]\s*(?:$|\n)")
    for path in (
        "work/timeline-data.json", "work/source-state.json",
        "outputs/gemini-evolution-panorama.html", "CHANGELOG.md",
    ):
        self.assertIn(path, self.workflow)
```

另写测试覆盖：Python 3.12、Node 24、`contents/pages/id-token` 权限、无 `pull-requests: write`、并发组、四个测试文件、JavaScript 语法检查、结果 JSON 判定、Pages artifact、`index.html`、可下载副本和 `.nojekyll`。

- [ ] **Step 2: 运行测试并确认工作流不存在**

Run:

```bash
python3 -m unittest tests/test_workflow_static.py -v
```

Expected: 工作流文件不存在导致失败。

- [ ] **Step 3: 实现更新、测试、受限提交和发布流程**

工作流关键约束：

```yaml
on:
  schedule:
    - cron: "30 0 * * *"
  workflow_dispatch:

permissions:
  contents: write
  pages: write
  id-token: write

concurrency:
  group: gemini-panorama-pages
  cancel-in-progress: false
```

步骤顺序固定为：checkout → Python → Node → 更新器 → 构建器 → JS 语法检查 → 全部 unittest → 读取结果 JSON → 使用结果中的 `checked_at` 生成仓库外 `site/index.html` → 仅 `content_changed=true` 时受限 `git add`/commit/push → Pages 配置、上传和部署。

Pages 临时产物使用：

```bash
CHECKED_AT="$(python3 -c 'import json; print(json.load(open("/tmp/gemini-update-result.json"))["checked_at"])')"
python3 work/build-page.py \
  --checked-at "$CHECKED_AT" \
  --output site/index.html
cp site/index.html site/gemini-evolution-panorama.html
touch site/.nojekyll
```

该步骤更新线上“最近自动检查时间”，但在没有事实变化时不修改仓库跟踪文件。提交命令只能使用：

```bash
git add -- \
  work/timeline-data.json \
  work/source-state.json \
  outputs/gemini-evolution-panorama.html \
  CHANGELOG.md
```

自动提交信息使用：`更新: 自动同步 Gemini 官方资料`。

- [ ] **Step 4: 运行工作流静态测试和全套测试**

Run:

```bash
python3 -m unittest \
  tests/test_timeline_data.py \
  tests/test_gemini_evolution_panorama.py \
  tests/test-source-parser.py \
  tests/test_auto_update.py \
  tests/test_workflow_static.py \
  -v
```

Expected: 全部测试通过。

- [ ] **Step 5: 更新 README 并检查 diff**

README 增加定时规则、手动触发、自动提交范围和 Pages 发布说明。建议提交信息（仅用户明确授权后执行）：`新增: 配置 Gemini 全景自动发布`。

---

### Task 8: 进行完整验证和页面质量审查

**Files:**
- Modify as needed: `work/*.py`, `work/*.json`, `tests/*.py`, `README.md`, `CHANGELOG.md`
- Regenerate: `outputs/gemini-evolution-panorama.html`

**Interfaces:**
- Consumes: 前七个任务的完整系统。
- Produces: 可提交、可发布的首版候选产物。

- [ ] **Step 1: 从干净状态重新生成**

Run:

```bash
python3 work/build-page.py
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

Expected: 全部测试通过，生成文件没有依赖未提交的本地缓存。

- [ ] **Step 2: 运行语法、JSON 和时间边界检查**

Run:

```bash
python3 -m py_compile work/timeline_core.py work/source_parser.py work/build-page.py work/update-gemini-panorama.py
python3 -m json.tool work/timeline-data.json >/dev/null
python3 -m json.tool work/source-config.json >/dev/null
python3 -m json.tool work/source-state.json >/dev/null
python3 - <<'PY'
from pathlib import Path
import re
html = Path("outputs/gemini-evolution-panorama.html").read_text(encoding="utf-8")
scripts = re.findall(r'<script(?![^>]*type="application/json")[^>]*>(.*?)</script>', html, re.S)
Path("/tmp/gemini-panorama-script.js").write_text("\n".join(scripts), encoding="utf-8")
PY
node --check /tmp/gemini-panorama-script.js
```

Expected: 全部命令退出码为 0。

- [ ] **Step 3: 做事实与来源抽样审计**

至少逐项复核：

- 2017 Transformer。
- BERT、LaMDA、PaLM、PaLM 2。
- Bard 首发和更名 Gemini。
- Gemini 1.0、1.5、2.0、2.5 与核验日之前的后续正式节点。
- Gemma、NotebookLM、Project Astra。
- Gemini API、AI Studio、Vertex AI。
- Gemini Live、Deep Research、Canvas、Code Assist、Jules。
- Google AI Pro / Ultra 和企业计划。
- 至少一项模型生命周期或弃用事件。

检查事件日期、前序差异、来源 URL、可用范围和是否存在推断性措辞；发现问题修改数据并重新跑全套测试。

- [ ] **Step 4: 做浏览器视觉与交互审查**

检查浅色/深色、桌面/平板/手机、键盘导航、搜索组合筛选、URL 恢复、年份锚点、详情展开、无结果、打印预览和禁用 JavaScript 阅读。使用浏览器控制台确认无错误、无失败网络请求、无远程资源。

- [ ] **Step 5: 检查 README 和最终 diff**

README 必须包含项目名称、功能、目录、技术栈、构建、测试、更新、bootstrap、工作流、Pages、来源策略和维护边界。运行：

```bash
git diff --check
git status --short
git diff --stat
```

确认没有 Claude/OpenAI 项目文件、临时文件、浏览器缓存或 `/tmp` 产物混入。

建议提交信息（仅用户明确授权后执行）：`新增: 完成 Gemini 演进全景首版`。

---

### Task 9: 创建公开仓库、推送并启用 GitHub Pages

**Files:**
- No source changes expected unless deployment verification exposes a defect.

**Interfaces:**
- Consumes: Task 8 验证通过的本地 `main` 分支。
- Produces: `yyst73Serendipity/gemini-evolution-panorama` 公开仓库和可访问 Pages 地址。

- [ ] **Step 1: 在执行外部写操作前确认授权状态**

确认用户仍授权：创建公开仓库、提交当前项目文件、推送 `main`、启用 GitHub Pages 和运行 Actions。若缺少“提交并推送”的明确授权，在此停止并询问，不以此前其他项目的授权代替。

- [ ] **Step 2: 最终提交前复核**

Run:

```bash
git status --short
git diff --check
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

Expected: 只有 Gemini 项目预期文件，全部测试通过。

- [ ] **Step 3: 创建首个中文提交**

仅获得授权后执行：

```bash
git add -- .gitignore AGENTS.md README.md CHANGELOG.md docs work tests outputs .github
git commit -m "新增: 发布 Gemini 产品与模型演进全景"
```

- [ ] **Step 4: 创建公开仓库并推送**

仅获得授权后执行：

```bash
gh repo create yyst73Serendipity/gemini-evolution-panorama \
  --public \
  --source=. \
  --remote=origin \
  --push
```

如果仓库已经存在，先核验所有者、可见性和远端 URL，再使用 `git remote add origin https://github.com/yyst73Serendipity/gemini-evolution-panorama.git` 与 `git push -u origin main`，不得覆盖未知远端历史。

- [ ] **Step 5: 启用 Actions Pages 并手动运行工作流**

使用 GitHub CLI/API 将 Pages 构建来源设为 GitHub Actions，然后执行：

```bash
gh workflow run update-gemini-panorama.yml --repo yyst73Serendipity/gemini-evolution-panorama
gh run list --repo yyst73Serendipity/gemini-evolution-panorama --workflow update-gemini-panorama.yml --limit 1
```

等待工作流完成，失败时读取具体 job 日志，不重复盲目触发。

- [ ] **Step 6: 验证公开页面和自动化**

验证：

```text
https://yyst73serendipity.github.io/gemini-evolution-panorama/
https://yyst73serendipity.github.io/gemini-evolution-panorama/gemini-evolution-panorama.html
```

检查首页、下载副本、深色主题、筛选、移动端和来源链接；确认仓库公开、Actions 定时为 UTC 00:30、Pages environment 部署成功。

- [ ] **Step 7: 报告最终状态**

向用户提供：仓库地址、Pages 地址、首个 commit SHA、工作流运行结果、测试数量、事件数量、核验截止日期和已知限制。若任何步骤未验证，不得表述为“已完成”。
