# Campaign Knowledge Base — Test Log

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

## 待测试项（Backlog）

| 测试内容 | 类型 | 所需条件 | 优先级 |
|---------|------|---------|-------|
| Proposal 文档（提案）端到端 | Integration | 一份提案 PDF/PPTX | 高 |
| Step 8：Pinecone 向量化 upsert | Integration | Pinecone key + embedding 服务 | 高 |
| Step 9：retrieve_campaign_knowledge() | Integration | Pinecone + ≥1 indexed record | 高 |
| 自验证（Self-verification）质量门 | Integration | ≥2 indexed records + 不相关查询 | 中 |
| 中等/高质量提案（图文结合 PPTX）| Integration | 提案 PPTX 文件 | 中 |
| 超长结案报告（>40,000 chars）| Integration | 长文档 | 中 |
| 英文文档提取 | Integration | 英文报告 | 低 |
| 混合语言文档 | Integration | 中英混排报告 | 低 |
| Middle-section fallback for outcome | Unit | mock LLM 返回空 outcome | 低 |
