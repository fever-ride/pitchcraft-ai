# Knowledge Base — Test Log

每次测试记录：测试范围、输入文档、各步骤结果、发现问题、后续动作。

---

## 格式说明

- **测试类型**：Unit（单元） / Integration（集成） / E2E（端到端）
- **步骤状态**：✅ 通过 / ❌ 失败 / ⊘ 跳过（依赖未就绪）
- **文档类型**：proposal（提案）/ campaign（结案）

---

## 2026-05-29 — Phase 5 Pipeline 端到端集成测试 #1

**测试类型**：Integration（Steps 1-7）  
**测试脚本**：`scripts/test_campaign_kb_pipeline.py`  
**运行环境**：本地 macOS，MongoDB + Redis via Docker Compose  
**测试文档**：安踏24Q3【中国甲】营销结案.pdf（结案报告，运动服饰行业）  
**文档特征**：以图片/设计为主，文字稀疏，解析后约 8,648 chars  

### 各步骤结果

| Step | 内容 | 状态 | 备注 |
|------|------|------|------|
| 1 | PDF 解析 | ✅ | 8,648 chars；大量内容为图片，文字覆盖率低 |
| 2 | LLM 提取（3 calls 并行） | ✅ | confidence=high；record_type=campaign（正确）|
| 3 | MongoDB 写入 | ✅ | `campaign_records` collection |
| 4 | MongoDB 读取验证 | ✅ | 所有关键字段 round-trip 正确 |
| 5 | 模拟人工确认 | ✅ | status 更新为 confirmed |
| 6 | Proposition 提取（1 LLM call） | ✅ | 14-15 条命题（两次运行结果略有差异）|
| 7 | Proposition MongoDB 存储 | ✅ | `campaign_propositions` collection，按 record_id 可检索 |
| 8 | BGE-M3 Embedding + Pinecone upsert | ✅ | 15 vectors, 1024-dim, namespace: campaign_knowledge_test-org-001 |

### 提取质量评估（Step 2）

| 字段 | 提取值 | 质量评估 |
|------|--------|---------|
| `record_type` | campaign | ✅ 正确 |
| `confidence` | high | ✅ 正确（3 calls 全部成功） |
| `client_name` | 安踏 | ✅ 精准（非代理公司名） |
| `industry` | 运动服饰 | ✅ |
| `campaign_type` | branding / event（两次运行不一致） | ⚠️ 枚举边界模糊导致不稳定 |
| `campaign_subtype` | 奥运营销（两次运行一致） | ✅ 稳定且具体 |
| `budget_tier` | null | ✅ 正确（文档无预算信息，未幻觉填值） |
| `big_idea` | 穿中国甲为中国加油 | ✅ |
| `kpi_results` | 13 项指标（曝光、互动、视频播放等）| ✅ 丰富 |
| `phasing_structure` | 三阶段传播（上市爆发/奥运借势/爆发延续）| ✅ |

### 命题质量评估（Step 6）

- 数量：14-15 条（合理，覆盖所有有实质内容的字段）
- 前缀格式：`[运动服饰 | 奥运营销 | 预算未知 | 体育、生活圈层用户]` — 所有命题一致 ✅
- 自包含性：每条命题含具体品牌名/数字/事件，无"该项目"类代词 ✅
- 覆盖维度：传播策略 ✅ 执行活动（纪录片/影展/KOL矩阵）✅ KPI 数据 ✅ 渠道分工 ✅

命题示例：
```
[运动服饰 | 奥运营销 | 预算未知 | 体育、生活圈层用户]
安踏与中国国家地理联名制作《沿着丝路到巴黎 与奥运同行》纪录片，
共发布4站分站内容和1站混剪内容，并举办线下沉浸式影展
```

### 发现的问题及处理

| 问题 | 影响 | 处理方式 | 参见 |
|------|------|---------|------|
| `campaign_type` 两次运行输出不一致（branding vs event）| Metadata filter 精度 | 新增 `campaign_subtype` 自由文本字段，向量化前缀优先用 subtype | issues.md #28 |
| pydantic-settings 不读 `.env`（被 shell 空 env var 覆盖）| 本地测试 API 认证失败 | 测试脚本入口手动解析 `.env`，覆盖空值 | issues.md #29 |

### 第二轮补测（2026-05-29 同日）

配置 Pinecone（`app.pinecone.io` 免费 tier），补测 Step 8-9，并追加 Step 10-11 检索质量测试：

| Step | 内容 | 状态 | 备注 |
|------|------|------|------|
| 8 | BGE-M3 Embedding + Pinecone upsert | ✅ | 15 vectors, 1024-dim cosine；namespace: `campaign_knowledge_test-org-001` |
| 9 | Pinecone 裸检索验证 | ✅ | 查询"运动品牌奥运营销KOL传播策略"，top-5 命中目标 record，top score ≈ 0.69 |
| 10 | 不相关查询 score 对比 | ✅ | "银行理财老年客户" score ≈ 0.45，比相关查询低 ~0.24；score > 0.40，交由 self-verification 决策 |
| 11 | `retrieve_campaign_knowledge()` 全路径 | ✅ | 修复2个 bug 后：不相关查询 → `[]`；稀疏库（1条 record）相关查询 → `insufficient`（符合预期） |

**全流程 11/11 步通过。**

### 测试中发现并修复的 bug

| Bug | 文件 | 症状 | 修复 |
|-----|------|------|------|
| `_summarise_results` 中 `None` 导致 `str.join()` 报错 | `campaign_retriever.py` | self-verification 静默失败，不相关查询照常返回结果，质量门形同虚设 | 所有 meta 字段改用 `str(val or "—")` 兼容显式 `None` |
| `verify_retrieval_sufficiency` 只传 `SystemMessage` | `campaign_retriever.py` | Anthropic API 返回 400，self-verification 静默失败 | 拆为 `SystemMessage`（规则）+ `HumanMessage`（数据）|

参见 issues.md 待补充。

### 关键观察：稀疏库下 self-verification 的行为

只有 1 条 record 时，即使查询语义高度相关（"运动品牌奥运借势营销策略"），self-verification 仍返回 `insufficient`——因为 `budget_tier=None`（未知），只有 2 个维度能匹配，未达到 `sufficient` 的 3 项门槛。这是**符合预期的保守行为**：宁可不给 agent 参考，也不给可能误导的稀疏参考。质量门的价值在 10+ confirmed records 之后才完全体现。

### 遗留问题（非阻塞）

- **文档图片内容无法提取**：大量策略信息嵌在图片/设计稿中，无法被文字解析捕获。当前不引入 OCR，鼓励上传 PPTX 而非 PDF。参见 issues.md #27（OCR 决策）。

### 后续动作

- [ ] 测试 proposal（提案）类型文档：验证 2-call 路径、record_type 自动检测、confidence 不被空 outcome 拖低
- [ ] issues.md 补充 bug #31（`_summarise_results` None 处理）和 #32（self-verification 消息格式）

---

## 2026-05-29 — Unit Tests #1（schema + 提取模型）

**测试类型**：Unit  
**测试文件**：`backend/tests/unit/test_archive.py`  
**运行命令**：`pytest backend/tests/unit/test_archive.py -v`  

### 测试结果

共 9 个测试用例，全部通过：

| 测试名 | 覆盖内容 | 状态 |
|--------|---------|------|
| `test_campaign_meta_client_name` | `CampaignMeta.client_name` 字段存在且可赋值 | ✅ |
| `test_campaign_meta_budget_tier_nullable` | `budget_tier` 可为 null | ✅ |
| `test_extraction_background_has_record_type` | `ExtractionBackground` 含 `record_type` 字段 | ✅ |
| `test_campaign_meta_subtype` | `campaign_subtype` 自由文本字段存在 | ✅ |
| `test_extraction_schemas` | 三个提取 schema 可正确实例化 | ✅ |
| `test_campaign_record_defaults` | `CampaignRecord` 默认值正确 | ✅ |
| `test_campaign_record_types` | record_type / pitch_outcome 枚举正确 | ✅ |
| `test_record_type_enum` | RecordType 枚举值完整 | ✅ |
| `test_pitch_outcome_enum` | PitchOutcome 枚举值完整 | ✅ |

---

---

## 2026-05-31 — Brand Library 端到端集成测试 #1

**测试类型**：Integration（解析 → 提取 → 格式化 → Brand Check）  
**运行环境**：本地 macOS，脚本直接调用 backend 模块（无 HTTP 层）  
**测试文档**：`test_docs/brand_library/forget+in+香薰情绪个护品牌手册.pdf`  
**品牌类别**：香薰情绪个护，中文文档，图文结合但文字可提取  
**文档特征**：4,890 chars，含品牌故事、定位、受众、调性体系、产品线、传播渠道

### 各步骤结果

| Step | 内容 | 状态 | 备注 |
|------|------|------|------|
| 1 | PDF 解析（`parse_file`） | ✅ | 4,890 chars；文字内容完整，结构段落清晰 |
| 2 | LLM 结构化提取（`extract_brand_profile`，Haiku） | ✅ | 全字段正确提取，见质量评估 |
| 3 | Prompt 格式化（`format_brand_profile_for_prompt`） | ✅ | 输出结构清晰，feedback 字段标签区分正确 |
| 4 | Brand Check — 符合调性策略 | ✅ | `passed=True`，无误报 |
| 5 | Brand Check — 违背调性策略 | ✅ | `passed=False`，输出 4 条精准 issues |

**全流程 5/5 步通过。**

### 提取质量评估（Step 2）

| 字段 | 提取结果摘要 | 质量评估 |
|------|------------|---------|
| `brand_name` | "forget in" | ✅ 精准 |
| `positioning` | "透过肌肤触达内心，致力感官沉浸享受的情绪个护品牌" | ✅ 原文直取 |
| `target_audience` | Z世代新青年（体验/颜值/绿色）；小镇青年（平替/成分/出挑欲） | ✅ 两类受众均提取，含细节描述 |
| `personality` | 7 个特质：敢于表达、拥抱情绪、自由不羁、年轻热血、感性细腻、反叛精神、包容多元 | ✅ 从品牌故事和产品命名中合理推断 |
| `tone_principles` | 6 条：直白宣泄情绪、符号化语言、打破常规、情绪共鸣优先、年轻化网感、包容转化情绪 | ✅ 从品牌理念段落提炼 |
| `forbidden_directions` | 空 | ✅ 正确——文档无明确禁忌，未幻觉填值 |
| `key_messages` | 感性宣泄+理性臻护、情绪香氛体系（粉红胡椒+百里香）、面护级成分用于身体、绿色植萃 | ✅ 核心卖点全覆盖 |
| `competitive_position` | 整合全球香氛资源，首席调香师曾为 Hermès/Lanvin 创作，GMP 工厂，澳洲生产标准 | ✅ 从生产实力和调香师档案提取 |

### Brand Check 测试（Step 4-5）

**符合调性策略**（Z世代情绪共鸣 + 符号化香氛 + 小红书种草）：
```
passed=True，no issues
```

**违背调性策略**（极简高冷 + 精英背书 + 避免情绪化表达）：
```
passed=False，4 issues：
  1. 极简主义高冷定位与「敢于表达、拥抱情绪」个性相悖
  2. 避免过多情绪化表达，直接违反「直白宣泄情绪」核心原则
  3. 精英阶层背书不符合「年轻化网感强」调性要求
  4. 缺少符号化语言和情感表达元素
```

每条 issue 均指向具体被违反的品牌规则，无泛化输出。

### Prompt 注入格式示例（Step 3）

（含模拟 feedback 方向，验证标签区分逻辑）

```
[Brand Profile: forget in]
Positioning: 透过肌肤触达内心，致力感官沉浸享受的情绪个护品牌
Target Audience: Z世代新青年（…）；小镇青年（…）
Personality: 敢于表达, 拥抱情绪, 自由不羁, 年轻热血, 反叛精神
Competitive Position: 整合全球香氛资源，首席调香师曾为 Hermès、Lanvin 创作
Tone Principles:
  - 直白宣泄情绪
  - 用符号化语言表达复杂情感
  - 年轻化、网感强
Key Messages:
  - 感性宣泄与理性臻护
  - 情绪香氛体系（粉红胡椒+百里香）
  - 自然植萃与绿色生产
Previously Approved Directions (from client feedback):
  - 聚焦香氛记忆点，主打气味唤醒情绪的故事线
Previously Rejected Directions (from client feedback):
  - 不要走极简高冷路线，与品牌调性相悖
```

### 关键观察

- **`forbidden_directions` 为空不是问题**：forget+in 的品牌手册侧重讲"我们是什么"，没有明确列出禁忌。Brand Check 的约束此时完全来自 `tone_principles` + `personality` 的反向推断——效果同样准确。
- **PDF 文字提取质量足够**：4,890 chars 覆盖了品牌手册的所有核心章节（品牌故事/定位/受众/香氛体系/传播），提取结果未见明显遗漏。
- **Haiku 模型的提取质量**：在这类有明确结构（目录 + 分章节）的文档上，Haiku 表现与 Sonnet 相当，cost 更低，路由合理。

### 遗留限制（已知）

- 图片为主的 VI 手册（如麦当劳视觉识别手册）提取字符量极低，无法走本流程。文字型品牌规范文档是当前可靠输入形式。
- `forbidden_directions` 依赖文档中有明确描述；如果品牌方用"不得…"以外的表达方式陈述禁忌，可能漏提取。

---

## 2026-06-01 — Resource Library Unit Tests #1（resource_to_text 文本层 eval）

**测试类型**：Unit  
**测试文件**：`backend/tests/unit/test_resource_import.py`  
**运行命令**：`pytest backend/tests/unit/test_resource_import.py -v`

### 背景与设计思路

`resource_to_text()` 将资源结构化数据拼接成自然语言摘要，是 BGE-M3 embedding 的直接输入，向量搜索质量完全依赖它。该函数是纯函数（无 DB/embedding 依赖），适合做文本层单元测试。

向量质量评估分两层：

| 层次 | 验证内容 | 成本 | 何时做 |
|------|---------|------|-------|
| 第一层（文本层） | 各字段是否出现在摘要文本中 | 低，无外部依赖，CI 可跑 | 现在 |
| 第二层（搜索层） | ground-truth 查询能否在 Pinecone 中召回正确资源 | 高，需 BGE-M3 + Pinecone | Resource Agent 接入后 |

`resource_to_text()` 所在模块顶层 import 了 motor/pinecone 等重依赖，无法直接 import（参见 issues.md #1）。沿用项目既有做法：在测试文件中 inline 函数逻辑并注明"需与真实函数保持同步"。

发现原有 inline 版本（`_resource_to_text`）为早期简化版，缺少 `tier`、`categories`、`content_style`、`audience_tags`、`outlet_type`、`beat` 等核心字段，与真实代码已完全脱节。本次一并更新。

### 测试覆盖范围（16 个新测试）

| 测试名 | 验证内容 |
|--------|---------|
| `test_resource_to_text_kol_full` | KOL 全字段均出现（tier、platform、followers、categories、content_style、audience_tags、past_cpe、pricing、notes）|
| `test_resource_to_text_content_style_v2_takes_priority` | `content_style_v2` 有内容时优先于 `content_style` 字符串 |
| `test_resource_to_text_content_style_fallback` | `content_style_v2` 缺失时 fallback 到 `content_style` 字符串 |
| `test_resource_to_text_content_style_v2_empty_dict_falls_back` | `content_style_v2 = {}` 时应 fallback，不静默丢弃（**此测试发现 bug**）|
| `test_resource_to_text_audience_demographics_takes_priority` | `audience_demographics` 有内容时优先于 `audience_tags` |
| `test_resource_to_text_audience_tags_fallback` | `audience_demographics` 缺失时 fallback 到 `audience_tags` |
| `test_resource_to_text_media` | 媒体资源：`outlet_type`、`beat` 出现；`Platform:`、`Followers:` 不出现 |
| `test_resource_to_text_vendor` | 供应商：`service_type`、`region` 出现 |
| `test_resource_to_text_placement` | 投放资源：`placement_type`、`location`、`audience_reach` 出现 |
| `test_resource_to_text_missing_optional_fields_no_crash` | 仅 name + type 的最简 doc 不报错 |
| `test_resource_to_text_categories_as_list` | categories 为 list，各元素均出现 |
| `test_resource_to_text_categories_as_string` | categories 为字符串（历史数据）正常处理 |
| `test_resource_to_text_empty_categories_excluded` | `categories = []` 不产生空的 `Categories:` 标签 |
| `test_resource_to_text_platform_excluded_when_absent` | platform 缺失时不产生 `Platform:` 标签 |
| `test_resource_to_text_separator_is_pipe` | 字段间分隔符为 ` \| `（影响 embedding tokenization）|

### 测试结果

```
26 passed in 0.25s
```

（含原有 10 个 parse/column-recognition 测试 + 16 个新 text 测试，首次运行 1 failed → fix → 全通过）

### 发现并修复的问题

| 问题 | 症状 | 修复 | 参见 |
|------|------|------|------|
| `content_style_v2 = {}` 静默丢弃 `content_style` | 空 dict 进入 v2 分支但无产出，elif 被跳过，内容风格从向量中消失 | 先收集 `style_parts` 再决定走哪条分支 | issues.md #36 |

### 后续（第二层 eval）

等 Resource Agent 接入 Pinecone 检索后，用已导入的 17 条测试资源（`client_id=test-client-001`）做搜索召回测试：

```python
# ground-truth 对（届时补充）
("小红书头部美妆KOL 粉丝超50万",     ["甜蜜生活Cindy"]),
("抖音数码测评 男性用户 理性消费",    ["老爸爱测评"]),
("科技创投媒体 发稿合作",            ["36氪", "虎嗅"]),
("活动策划供应商 上海",              ["禾木创意"]),
("减脂健身 小红书女性",              ["减脂日记by颜颜"]),
```

指标：Recall@3（期望资源是否出现在前 3 名）。

---

## 2026-06-01 — Full Pipeline Happy Path #1（完整流水线端到端）

**测试类型**：E2E  
**测试脚本**：`scripts/happypath_test.py`  
**运行环境**：本地 macOS，全服务本地启动（MongoDB Docker + Redis brew + BGE-M3 本地 + FastAPI + Celery + Next.js）  
**测试 Brief**：可口可乐2026夏季年轻化营销提案（中文，约 600 字，标注预算 800万 + 音乐节 IP + 抖音/小红书/微博）  
**输出语言**：zh  

### 服务启动清单

| 服务 | 启动方式 | 状态 |
|------|---------|------|
| MongoDB | `docker run -d --name pitchcraft-mongo-local -p 27017:27017 mongo:7` | ✅ |
| Redis | brew services（已有） | ✅ |
| BGE-M3 Embedding | `uvicorn server:app --port 8001`（infrastructure/docker/embedding/） | ✅ |
| FastAPI backend | `set -a && source .env && set +a && uvicorn backend.api.main:app --port 8000 --reload` | ✅ |
| Celery worker | `celery -A backend.core.tasks worker --loglevel=info` | ✅ |
| Next.js frontend | `npm run dev`（frontend/） | ✅ |

**前置操作**：新 MongoDB 容器无用户，需 seed（`python3 << 'PYEOF'` 直接插入 org + user + client）。

### Pipeline 执行轨迹（第三次运行，前两次各发现一个 bug）

| 节点 | 耗时 | 状态 |
|------|------|------|
| brief_analyzer | ~10s | ✅ |
| hitl_brief | auto-confirm | ✅ |
| parallel（research + strategy_phase1） | ~40s | ✅ |
| strategy_phase2 | ~15s | ✅ |
| brand_check | ~8s | ✅ |
| hitl_strategy | auto-confirm | ✅ |
| resource_agent | ~10s | ✅（无资源库数据，返回空列表）|
| deck_orchestrator | ~55s | ✅（修复 #37 后）|
| hitl_structure | auto-confirm | ✅ |
| slide_content（18 slides × 3 并发） | ~60s | ✅（修复 #38 后）|
| narrative_agent | ~10s | ✅ |
| hitl_gallery | auto-confirm | ✅ |
| ppt_builder | ~2s | ✅ |

**总耗时**：约 4 分钟（含 4 次 HITL auto-confirm）  
**输出文件**：`backend/output/a1058483-f600-46bc-9523-fa4fb022335e.pptx`（57KB，19 slides）

### 输出质量抽查

| 检验项 | 结果 |
|--------|------|
| 幻灯片数量 | 19（1 template + 18 content）|
| Big Idea | "开罐即开场" ✓ |
| 渠道覆盖 | 抖音/小红书/微博/音乐节IP/便利店/B站 全部有对应 slide ✓ |
| 语言 | 全中文 ✓ |
| 结构类型分布 | cover/insight/strategy/channel/budget/timeline/kpi/appendix ✓ |

### 发现并修复的问题

| # | 节点 | 症状 | 修复 | 参见 |
|---|------|------|------|------|
| 1 | deck_orchestrator | `ValidationError: slides Field required, input_value={}` | max_tokens 3000→6000，channel role/KPI 截断至 60 字 | issues.md #37 |
| 2 | slide_content | `429: concurrent connections exceeded` | `asyncio.Semaphore(3)` 限制在途 LLM 请求 | issues.md #38 |

### 注记

- `langgraph` 未包含在系统 Python 中，需手动 `pip install langgraph`（已装，pipeline 模块延迟 import 所以 backend 重启无需重装）
- 本地 .env 缺少 `MONGODB_URL`/`REDIS_URL`/`CELERY_*`/`EMBEDDING_SERVICE_URL` 的 localhost 覆盖，需补充（已加入 .env 注释区段）
- `TAVILY_API_KEY` 未设置，Research Agent 自动 fallback 到 DuckDuckGo（无感）

---

## 待测试项（Backlog）

**Campaign Knowledge Base**

| 测试内容 | 类型 | 所需条件 | 优先级 |
|---------|------|---------|-------|
| Proposal 文档（提案）端到端 | Integration | 一份提案 PDF/PPTX | 高 |
| 中等/高质量提案（图文结合 PPTX）| Integration | 提案 PPTX 文件 | 中 |
| 超长结案报告（>40,000 chars）| Integration | 长文档 | 中 |
| 英文文档提取 | Integration | 英文报告 | 低 |
| 混合语言文档 | Integration | 中英混排报告 | 低 |
| Middle-section fallback for outcome | Unit | mock LLM 返回空 outcome | 低 |

**Brand Library**

| 测试内容 | 类型 | 所需条件 | 优先级 |
|---------|------|---------|-------|
| PPTX 品牌手册提取（QMS/Hulu） | Integration | 已有文件 | 中 |
| IKEA 英文品牌手册提取 | Integration | 已有文件 | 中 |
| feedback 方向 → BrandProfile `$addToSet` 同步 | Integration | 运行中的 MongoDB 实例 | 中 |
| Strategy Phase 1 含 BrandProfile 上下文的完整 pipeline | E2E | 运行中的后端服务 | 高 |
| 图片型 VI 手册（仅视觉，几乎无文字）| Integration | 有文件 | 低（已知限制）|

**Resource Library**

| 测试内容 | 类型 | 所需条件 | 优先级 |
|---------|------|---------|-------|
| 第二层 eval：ground-truth 查询 → Pinecone 召回验证（Recall@3）| Integration | Resource Agent 接入 + 17 条测试资源在 Pinecone | 中（等 Agent 接入后）|
| 跨类型搜索：同一查询命中 KOL + 媒体 + 供应商 | Integration | 同上 | 低 |
