# Gemini / Google AI 产品与模型演进全景设计规格

## 1. 文档状态

- 设计日期：2026-10-22
- 目标仓库：`yyst73Serendipity/gemini-evolution-panorama`
- 页面形态：纯前端、单文件 HTML、构建时预渲染
- 自动检查时间：每天北京时间 08:30
- 发布方式：GitHub Actions + GitHub Pages
- 当前阶段：设计已获用户确认，实施计划已生成并等待执行方式确认

## 2. 项目目标

建立一份可长期维护的 Google AI 产品与模型演进档案，覆盖 2017 年 Transformer 至每次构建时的实际核验日期。页面需要让读者快速回答以下问题：

1. 某个时间点发布或更新了什么模型、产品、平台或订阅计划？
2. 该版本与前一版本相比发生了什么变化？
3. 能力、性能、成本、使用方式或产品定位优化了哪里？
4. 该事件在 Gemini 与 Google AI 整体演进中为什么重要？
5. 结论来自哪个官方来源，日期和事实是否可追溯？

项目同时提供稳定的自动更新机制，但准确性高于更新频率：没有可靠事实更新时不生成空事件，不使用模糊页面变化制造发布记录。

## 3. 收录范围

### 3.1 收录内容

- 技术与模型前史：Transformer、BERT、LaMDA、PaLM、PaLM 2。
- Gemini 模型家族及其重要预览版、稳定版、能力升级、价格变化、迁移和弃用。
- Bard、Gemini App、Gemini Live、Deep Research、Canvas 等消费级产品。
- Gemini API、Google AI Studio、Vertex AI 等开发者和企业平台。
- Project Astra、Jules、Gemini Code Assist、Gemini CLI 等代理与开发工具。
- Gemma 开放模型。
- NotebookLM。
- 与 Gemini 直接相关的重要 Workspace、Android、Chrome、Search 集成。
- Google One AI Premium、Google AI Pro、Google AI Ultra，以及相关企业与教育计划。
- 官方安全报告、模型卡、生命周期和命名体系变化。

### 3.2 不收录内容

- 与 Gemini 主线关系较弱的普通 Google 产品更新。
- 每一项细碎的 Workspace 功能变化。
- 纯营销活动、普通合作、客户案例和没有产品事实的宣传内容。
- AlphaGo、AlphaFold 等没有直接进入 Gemini 产品体系的独立 DeepMind 路线。
- 爆料、传闻和仅由第三方媒体转述的未确认信息。

## 4. 来源策略

### 4.1 自动更新主来源

1. Gemini API Release Notes。
2. Vertex AI Generative AI Release Notes。
3. Google DeepMind Model Cards。
4. Google Blog 的 Gemini 产品专区及明确标注发布日期的正式公告。
5. Google DeepMind 新闻与 Gemini 官方页面。
6. Google Developers Blog、Google Cloud Blog。
7. Google Workspace Updates。
8. Android、Chrome、Google Search 官方博客。
9. Gemini Apps Help Center、Google AI Studio 文档、模型列表、价格页面、模型生命周期页面和订阅计划页。

自动化优先使用 RSS、Atom、结构化发布说明、稳定正文和 sitemap 进行发现。sitemap 的 `lastmod` 只能用于发现可能变化的页面，不能直接作为事件发布日期。

### 4.2 X/Twitter 策略

Google、Google DeepMind、Gemini、Google AI Developers 等官方 X/Twitter 账号只作为人工发现和补充来源，不进入 GitHub Actions 自动抓取主链路，原因包括登录要求、访问限制和页面结构不稳定。

如果某项事实只在官方社交账号发布，可人工收录并标记为“官方社交发布”；若存在对应的 Google 官方文章、文档或帮助页面，则优先引用正式页面。

### 4.3 来源等级

| 等级 | 来源类型 | 使用方式 |
|---|---|---|
| A | 官方 Release Notes、模型卡、开发文档 | 技术事实、模型状态和生命周期主来源 |
| A | Google、Google DeepMind 正式公告 | 模型与产品发布主来源 |
| B | Workspace、Android、Chrome、Cloud、Search 等官方博客 | 生态集成来源 |
| B | 官方帮助中心、价格、计划与地区页面 | 权益、限制、价格和可用性来源 |
| C | 官方 X/Twitter 账号 | 人工发现和补充，不参与稳定自动抓取 |
| 不采用 | 媒体转述、爆料、第三方汇总 | 不作为核心事实依据 |

来源存在冲突时，优先级依次为正式技术文档、产品公告正文、帮助中心、官方社交账号。

## 5. 页面信息架构

### 5.1 首屏总览

首屏展示：

- 时间跨度 `2017—当前核验年份`。
- 数据核验截止日期。
- 收录事件总数和各分类数量。
- 最近一次自动检查时间。
- 最近一次实际内容更新时间。
- 官方来源覆盖状态。
- 快速搜索和主要分类入口。

“自动检查时间”和“内容更新时间”必须分开显示，避免每天执行任务却让用户误以为每天都有事实更新。

### 5.2 主要章节

1. 演进总时间线。
2. 模型谱系。
3. 消费级产品。
4. 开发者与企业平台。
5. 订阅计划。
6. 研究与未来产品。
7. 来源与方法。

### 5.3 交互能力

- 按年份筛选。
- 按模型、产品、开发者平台、订阅计划等类别筛选。
- 按 Gemini、Gemma、Bard、NotebookLM 等产品线筛选。
- 按研究、预览、正式发布、升级、更名、降价、迁移和弃用筛选。
- 关键词搜索。
- 仅查看重大节点。
- URL 保存筛选状态。
- 年份粘性导航和阅读进度。
- 浅色、深色和跟随系统主题。
- 响应式、打印和键盘操作支持。
- 无 JavaScript 时仍可阅读完整时间线。

### 5.4 视觉方向

采用“统一信息结构 + Gemini 独立视觉”：

- 沿用经过验证的档案式信息架构、年份分组、卡片层级和粘性目录。
- 使用蓝、紫、青为核心色，配合克制的 Gemini 星芒和渐变轨迹。
- 首屏突出 `2017—当前年份`，但不使用影响阅读的持续动画。
- 深色模式增强渐变、星芒和层次，正文仍以高对比度和长时间阅读为先。
- 不使用外部字体、CDN、图片热链或前端框架。

## 6. 时间线数据契约

每条事件至少包含以下字段：

| 字段 | 含义 |
|---|---|
| `id` | 稳定且唯一的事件标识 |
| `date` | ISO 日期或允许缺省日、月的规范日期 |
| `date_precision` | `day`、`month` 或 `year` |
| `title` | 简洁事件标题 |
| `category` | 模型、产品、开发者平台、订阅、生态、研究、安全或生命周期 |
| `families` | Gemini、Gemma、Bard、NotebookLM 等产品线 |
| `lifecycle` | 研究、预览、发布、升级、更名、降价、迁移或弃用 |
| `summary` | 更新了什么 |
| `difference` | 与此前版本或状态相比的变化 |
| `optimization` | 优化或解决的问题 |
| `significance` | 对用户、开发者或生态的影响 |
| `importance` | `major` 或 `standard` |
| `predecessors` | 相关前序事件 ID |
| `successors` | 可选的相关后续事件 ID |
| `sources` | 官方来源列表及来源等级 |
| `first_seen_at` | 首次发现时间 |
| `verified_at` | 最近核验时间 |

早期事件没有准确发布日期时必须降低 `date_precision`，不得虚构具体日期。正文卡片重点展示“发生了什么、与此前有什么不同、为什么重要”。

## 7. 自动更新架构

### 7.1 数据流

```text
读取来源配置和上次来源状态
→ 抓取官方来源
→ 提取候选条目
→ 标准化日期、标题、实体和事件类型
→ 校验官方域名、发布日期和内容边界
→ 计算内容指纹并去重
→ 根据置信度决定是否收录
→ 写入临时时间线数据
→ 生成临时单文件 HTML
→ 运行数据、页面和工作流测试
→ 原子替换正式文件
→ 有事实变化时提交并发布
```

### 7.2 自动收录规则

#### 高置信度，允许自动发布

- 结构化 Release Notes。
- DeepMind 官方模型卡。
- 正文明确标注发布日期、模型或产品名称和实际变化的正式公告。
- 明确的模型上线、价格变化、迁移和弃用通知。

#### 中置信度，满足全部规则后自动发布

- Workspace Updates、Developers Blog、Cloud Blog、Android、Chrome、Search 官方博客。
- 必须存在明确日期、明确实体、可提取的事实变化，且不是纯营销内容。
- 必须通过去重、日期边界和官方域名校验。

#### 低置信度，不直接发布

- 页面局部变化但没有发布日期。
- 只有 sitemap `lastmod`。
- 无法判断是功能变化还是文案调整。
- 只有官方 X/Twitter 帖子且没有稳定正文来源。
- 普通合作、客户案例和营销活动。

低置信度变化只更新来源检查状态或人工复核记录，不进入公开时间线。

### 7.3 去重规则

综合使用以下信息生成稳定指纹：

- 规范化来源 URL。
- 规范化标题。
- 事件日期及日期精度。
- 模型或产品实体。
- 生命周期类型。
- 核心事实摘要。

同一发布同时出现在多个官方页面时只生成一条事件，选择技术信息最完整的页面作为主来源，其余页面作为补充来源。

### 7.4 日期规则

- 不收录晚于任务实际运行日期的事件。
- 不把文章修改日期当作首次发布日期。
- 不把 sitemap `lastmod` 当作事件日期。
- 日期冲突时优先使用公告正文明确写出的发布日期。
- 无法确定具体日时使用月级精度，无法确定具体月时使用年级精度。
- 自动构建日期由任务运行环境生成，不在数据中写死“今天”。

### 7.5 原子更新和失败策略

- 新数据和 HTML 先写入临时文件。
- 数据校验、页面生成或测试任一步失败，都不替换正式文件。
- 单个可选来源失败时记录状态并继续处理其他来源。
- 必需来源全部失败时，自动任务失败且不产生提交。
- 没有事实变化时不改写时间线、HTML 和更新日志，不生成空提交。
- 自动提交只能修改时间线数据、来源状态、更新日志和生成的 HTML。

## 8. 工程边界

计划结构：

```text
gemini/
├── .github/workflows/update-gemini-panorama.yml
├── docs/superpowers/specs/
├── docs/superpowers/plans/
├── outputs/gemini-evolution-panorama.html
├── tests/
│   ├── test_timeline_data.py
│   ├── test_gemini_evolution_panorama.py
│   ├── test_auto_update.py
│   └── test_workflow_static.py
├── work/
│   ├── build-page.py
│   ├── source-config.json
│   ├── source-state.json
│   ├── timeline-data.json
│   └── update-gemini-panorama.py
├── .gitignore
├── AGENTS.md
├── CHANGELOG.md
└── README.md
```

技术约束：

- Python 3 标准库负责抓取、解析、数据校验和页面构建。
- 页面使用 HTML、CSS 和原生 JavaScript。
- 不引入第三方运行时依赖、外部字体、CDN 或前端框架。
- 构建时预渲染全部事件，JavaScript 只负责增强交互。
- 自动更新程序与页面生成器分离，便于独立测试和故障定位。

## 9. GitHub Actions 与发布

- 计划创建公开仓库 `yyst73Serendipity/gemini-evolution-panorama`。
- `main` 为默认分支。
- 每天北京时间 08:30 执行，即 UTC 00:30。
- 支持 `workflow_dispatch` 手动触发。
- 工作流依次执行来源更新、页面构建、测试、受限文件检查、提交和 Pages 发布。
- Pages 预计地址为 `https://yyst73serendipity.github.io/gemini-evolution-panorama/`。
- 自动任务使用最小权限，只在确认有事实变化且测试通过后写入仓库。

## 10. 测试策略

### 10.1 数据测试

- JSON 数据契约和必填字段。
- 日期格式、日期精度和运行日期边界。
- 事件 ID、来源 URL 和内容指纹唯一性。
- 分类、产品线、生命周期和重要性枚举。
- 前序、后续事件引用存在且不自引用。
- 官方来源域名和来源等级一致。

### 10.2 页面测试

- 单文件 HTML 成功生成。
- 无 JavaScript 时包含完整事件正文。
- 事件数量与数据一致。
- 搜索和筛选所需属性完整。
- 年份导航、主题、无障碍标签、打印和响应式基础结构存在。
- 页面不依赖 CDN、外部字体和运行时网络资源。

### 10.3 更新器测试

- 新事件识别与已有事件去重。
- 同一事件多来源合并。
- 无事实变化时不改写产物。
- 日期冲突和低精度日期处理。
- 可选来源失败时继续、必需来源全部失败时停止。
- 测试失败时不替换正式文件。
- 自动修改文件范围限制。

测试使用标准库 `unittest`。解析器的确定性单元测试使用仓库内保存的官方页面最小样本；工作流另执行真实官方来源可达性与结构检查，不使用伪造的外部 API 返回结果代替集成验证。

## 11. README 与维护要求

每次代码变更同步更新 README：

- 文件增删时更新目录结构。
- 功能变化时更新功能介绍。
- 命令、配置和入口变化时更新使用方式。
- 自动来源或发布策略变化时更新维护说明。

CHANGELOG 只记录实际事实数据或项目能力变化，不记录没有内容变化的定时检查。

## 12. 验收标准

项目首次发布必须同时满足：

1. 时间线覆盖 2017 年至 2026 年 10 月 22 日核验到的关键事实。
2. 每条事件至少有一个可访问的 Google 官方来源。
3. 重大节点说明更新内容、与前序差异和实际意义。
4. 页面可离线打开、无 JavaScript 可读、移动端可用、可打印。
5. 搜索、筛选、年份导航和主题切换可正常使用。
6. 自动更新支持定时和手动触发，无变化时不产生空提交。
7. 自动更新失败不破坏上一版数据和 HTML。
8. 全部测试通过后才允许自动提交和 Pages 发布。
9. 公开仓库和 GitHub Pages 地址可访问。
