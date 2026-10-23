# Gemini / Google AI 时间线来源审计

## 核验范围

- 核验截止日期：**2026-10-22**
- 核验时区：**Asia/Shanghai（UTC+08:00）**
- 首版事件数量：**44 条**
- 时间范围：**2017 年 Transformer 至 2026 年 10 月 22 日**
- 内容范围：技术基础、模型、消费产品、开发者平台、企业生态、订阅计划、安全治理与生命周期。

本项目是经过筛选的演进档案，不是 Google 全部 AI 新闻的逐条镜像。事件只有在能说明产品线演进、模型代际变化、公开可用范围、商业计划变化或生命周期影响时才进入主时间线。

## 官方来源边界

时间线只接受 Google 及其直接产品、研究和开发者站点中的第一方资料。当前白名单为：

```text
research.google
ai.google
ai.google.dev
blog.google
deepmind.google
developers.googleblog.com
cloud.google.com
workspaceupdates.googleblog.com
support.google.com
one.google.com
gemini.google.com
android.com
blog.google.com
chromium.org
```

优先级按事实类型区分：

1. 论文页、技术报告与模型卡：用于架构、训练方式、能力边界与安全评估。
2. 产品公告与开发者博客：用于发布日期、首次公开范围、产品命名和主要差异。
3. API 发布说明与弃用文档：用于模型字符串、稳定/预览状态、替代型号和停服日期。
4. 帮助中心、Workspace 更新和 Google One 计划页：用于订阅权益、地区、席位或企业可用范围。
5. 产品页：用于补充当前定位；动态产品页不单独承担历史发布日期证明。

## 主要产品线与主来源

| 产品线 | 主要来源 | 核验重点 |
| --- | --- | --- |
| Transformer、BERT、LaMDA、PaLM | Google Research、Google Blog | 论文年份、架构变化、研究状态 |
| Gemini 核心模型 | Google DeepMind、Google Blog、模型卡 | 代际、预览/稳定状态、多模态与推理能力 |
| Gemma | Google DeepMind、Google for Developers | 开放权重、模型尺寸、设备与本地运行范围 |
| Bard / Gemini App | Google Blog、产品帮助页 | 更名、移动端、Live、Canvas、Deep Research 与代理功能 |
| NotebookLM | Google Blog | 资料 grounding、底层模型升级和订阅可用性 |
| Gemini API / AI Studio | Google AI for Developers | 模型字符串、发布说明、弃用、迁移与稳定状态 |
| Vertex AI / 企业生态 | Google Cloud | 企业预览/正式可用、治理与集成范围 |
| Code Assist、Jules、Gemini CLI | Google Cloud、Google Developers Blog、Google Blog | 开发者入口、开源状态、异步代理与编码工作流 |
| Google AI Pro / Ultra | Google Blog、Google One | 计划名称、层级变化与主要权益 |
| 安全治理 | Google DeepMind、Google Safety & Security、模型卡 | 风险类别、红队、访问控制与运行时防护 |

## 日期与状态处理规则

- 优先采用原始公告或发布说明正文标注的发布日期。
- 同一能力存在“宣布、预览、稳定、全面可用、停服”多个节点时，按演进价值分别建卡；不能把预览日期写成正式发布日期。
- 只有年份可确认时使用 `year`；只有月份可确认时使用 `month`；正文明确到日才使用 `day`。
- 论文的预印本、会议发表和产品化日期不混为同一日期；卡片正文会说明所采用的节点。
- 动态产品页或模型集合页的更新时间不作为历史发布日期；必须配合原始公告、模型卡或发布说明。
- `sitemap lastmod`、搜索摘要日期和网页抓取时间不作为发布日期证据。
- 若地区博客与全球博客正文相同但 URL 不同，优先保留可稳定访问且发布日期清晰的官方版本。

## 前后差异的写法

每张事件卡把“更新了什么”拆为四个字段：

- **与前序相比**：只描述官方材料能够支持的代际或产品变化。
- **优化重点**：归纳官方明确说明的速度、成本、上下文、多模态、推理、代理、安全或体验目标。
- **可用范围**：区分研究演示、可信测试、公开预览、稳定发布、订阅层级和企业渠道。
- **为什么重要**：解释该节点在演进链中的作用，不把推断写成官方结论。

自动化只能发现候选变化和重建页面，不能在证据不足时自行创造比较结论。若官方未公布参数、基准、价格、地区或上线比例，使用保守措辞，不补写估计值。

## X / Twitter 使用规则

- Google、Google DeepMind、Gemini、Google AI Developers 等官方账号可以帮助人工发现公告。
- X/Twitter 不进入自动抓取主链路，不把转帖、短帖或互动数据作为唯一事实依据。
- 若社交帖包含独有信息，必须记录官方账号、帖子 ID 和发布时间，并尽量回溯到官网正文；当前首版时间线未使用社交帖作为唯一来源。

## 收录与排除边界

### 收录

- 直接构成 Gemini 技术前史的 Transformer、BERT、LaMDA、PaLM 与 PaLM 2。
- Gemini、Gemma 的重要代际和稳定/预览状态变化。
- Bard、Gemini App、NotebookLM、Live、Canvas、Deep Research 等核心产品节点。
- AI Studio、Gemini API、Vertex AI、Code Assist、Jules、Gemini CLI 等开发者与企业入口。
- Google AI Pro / Ultra 等直接影响 Gemini 可用性的订阅计划。
- 会影响生产系统的弃用、停服、自动迁移和稳定模型节点。
- 与前沿模型发布直接绑定的安全治理和模型卡。

### 排除

- AlphaGo、AlphaFold 等重要但不属于本项目 Gemini 产品与模型主线的独立研究项目。
- 与 Gemini 演进无直接关系的普通 Google 产品更新、促销、案例文章和重复地区公告。
- 仅有营销描述、无法确认具体能力变化或可用范围的内容。
- 截止日之后的预告、路线图猜测、泄露信息和第三方传闻。
- 官方未明确公布的参数规模、训练数据、基准分数、价格或发布日期推断。

## 首版复核结论与限制

- 44 条事件均至少包含一个 A/B 级 Google 官方来源，并通过域名、HTTPS、日期边界、枚举、重复事件和前后继引用校验。
- 2025—2026 年重点复核了 Gemini 3、Gemini 3.1 Pro、Gemma 4、Deep Research Max、Gemini 2.0 API 停服、Gemini Omni、Gemini 3.6/3.8 Flash、3.x 迁移和 Gemini 4 Argon。
- Gemini Omni 的 2026 年 6 月公开预览与 8 月稳定发布分为两个节点，避免把预览状态误写为正式发布。
- Gemini 4 Argon 的模型、开发者、安全和 Gemini App 公告分别承担不同事实，不以动态模型集合页单独证明发布日期。
- 订阅价格、地区开放和配额变化频繁；首版只保留具有演进意义的计划层级变化，后续由自动更新流程发现候选并等待人工确认。
