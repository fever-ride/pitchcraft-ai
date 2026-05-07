# Architecture Design: Marketing Automation Multi-Agent System

**版本**：v0.2  
**状态**：草稿  
**最后更新**：2026-05  
**关联文档**：PRD v0.4  
**更新内容**：完善文件库和资源库的数据层设计，对齐PRD全部文件类型和资源类型

---

## 1. 系统全景

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                            │
│                  Next.js Frontend (Port 3000)                   │
│           React + TypeScript + Redux + WebSocket                │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTPS / WSS
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                       API GATEWAY LAYER                         │
│                      Nginx Reverse Proxy                        │
│                  HTTP → /api   WS → /ws                        │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                     APPLICATION LAYER                           │
│                    FastAPI Backend (Port 8000)                  │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │              LangGraph Multi-Agent Pipeline               │  │
│  │                                                           │  │
│  │  BriefAnalyzer → [Research ‖ Strategy] → Resource →      │  │
│  │  DeckOrchestrator → SlideContent → Narrative → PPTBuilder │  │
│  │                                                           │  │
│  │  ┌─────────────────┐    ┌──────────────────────────────┐ │  │
│  │  │  Request Budget  │    │   Deterministic Fallback     │ │  │
│  │  │  (per-pipeline   │    │   Chain (per external dep)   │ │  │
│  │  │   cost cap)      │    │                              │ │  │
│  │  └─────────────────┘    └──────────────────────────────┘ │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────┐   ┌─────────────────────────────┐    │
│  │     RAG Pipeline     │   │      Memory & Cache         │    │
│  │  - Brand Library     │   │  - Project State            │    │
│  │    (规范类/历史类)    │   │  - Semantic Response Cache  │    │
│  │  - Project Library   │   │  - Client Feedback Store    │    │
│  │    (需求/竞品资料)    │   │                             │    │
│  │  - Resource Index    │   │                             │    │
│  │    (KOL/媒体/供应商)  │   │                             │    │
│  └──────────────────────┘   └─────────────────────────────┘    │
└──────────┬──────────────────────────────┬───────────────────────┘
           │                              │
           ▼                              ▼
┌──────────────────┐            ┌──────────────────────┐
│   TASK QUEUE     │            │    EXTERNAL TOOLS    │
│  Celery + Redis  │            │  - Tavily Search     │
│  - PPT生成        │            │  - Anthropic API     │
│  - 文件向量化      │            │  - python-pptx       │
│  - Research任务   │            │                      │
└──────────────────┘            └──────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────┐
│                          DATA LAYER                             │
│                                                                 │
│  ┌────────────────────────┐    ┌───────────────────────────┐   │
│  │      MongoDB Atlas     │    │        Pinecone DB        │   │
│  │                        │    │                           │   │
│  │  - clients             │    │  brand_spec_{client_id}   │   │
│  │  - projects            │    │  brand_history_{client_id}│   │
│  │  - proposals           │    │  project_{project_id}     │   │
│  │  - files               │    │  resource_kol             │   │
│  │    (brand & project)   │    │  resource_media           │   │
│  │  - resources           │    │  resource_vendor          │   │
│  │    (kol/media/vendor/  │    │  resource_placement       │   │
│  │     placement)         │    │                           │   │
│  │  - feedback            │    │  (namespace隔离，          │   │
│  │  - stage_metrics       │    │   防跨库污染)              │   │
│  └────────────────────────┘    └───────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Agent系统设计

### 2.1 LangGraph状态机

整个pipeline用LangGraph管理状态，支持条件分支、Human-in-the-loop暂停、定点重跑。

```python
class PipelineState(TypedDict, total=False):
    # 基础信息
    client_id: str
    project_id: str
    proposal_id: str

    # Brief层
    raw_brief: str
    structured_brief: dict          # BriefAnalyzer输出
    brief_confirmed: bool           # 节点1用户确认

    # 调研层
    research_result: dict           # ResearchAgent输出
    strategy_result: dict           # StrategyAgent输出
    brand_check_passed: bool        # 品牌一致性检查

    # 策略层
    strategy_confirmed: bool        # 节点2用户确认
    strategy_feedback: str          # 用户修改意见

    # 资源层
    resource_result: dict           # ResourceAgent输出
    resource_types_needed: list     # ["kol", "media", "vendor"]

    # Deck层
    deck_structure: list            # 页面列表
    structure_confirmed: bool       # 节点3用户确认
    slides: list                    # 逐页内容
    slides_confirmed: bool          # 节点4用户确认
    narrative_passed: bool          # Narrative检查
    narrative_feedback: str
    narrative_retry_count: int      # 最多2次

    # 输出
    pptx_path: str

    # 控制
    rerun_from: str                 # 定点重跑起始节点
    request_budget: RequestBudget   # 成本控制
    stage_metrics: dict             # 各阶段价值追踪
```

### 2.2 Agent拓扑图

```
                    ┌─────────────────┐
                    │  Brief Analyzer  │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  [节点1] 用户    │  ← Human-in-the-loop
                    │  确认Brief解读   │    WebSocket推送，等待前端响应
                    └────────┬────────┘
                             │
              ┌──────────────┴──────────────┐
              │          并行执行            │
              ▼                             ▼
    ┌──────────────────┐         ┌──────────────────┐
    │  Research Agent  │         │  Strategy Agent  │
    │  - 网络搜索       │         │  - Big Idea      │
    │  - 竞品分析       │         │  - 传播逻辑       │
    │  - 历史库检索     │         │  - 渠道组合       │
    └────────┬─────────┘         └────────┬─────────┘
              │                            │
              └──────────────┬─────────────┘
                             │
                    ┌────────▼────────┐
                    │  品牌一致性检查  │  ← RAG检索Brand Library
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  [节点2] 用户    │  ← 最重要的节点
                    │  确认策略方向   │    可要求重跑Strategy
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  Resource Agent │  ← 可选，按渠道类型触发
                    │  (可插拔)        │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ Deck Orchestrator│  ← 三级结构优先级
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  [节点3] 用户    │
                    │  确认页面结构   │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ Slide Content   │  ← 逐页生成，含文案
                    │    Agent        │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  [节点4] 用户    │
                    │  逐页审阅       │  ← 单页重生成，不影响其他页
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ Narrative Agent  │  ← 叙事逻辑检查
                    │                 │    最多循环2次
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │   PPT Builder   │  ← 纯技术执行
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  [节点5] 客户   │
                    │  反馈录入       │  ← 沉淀Brand Library
                    │                 │    触发定点重跑
                    └─────────────────┘
```

---

## 3. RAG系统设计

### 3.1 Pinecone namespace索引结构

不同类型的文件和资源用独立namespace隔离，防止检索时跨库污染，也让每类检索能单独调整权重和策略。

```
Pinecone Index: mkt-agent
│
│  ── 品牌长期库（Brand Library）──────────────────────────────
├── namespace: brand_spec_{client_id}
│       品牌规范类文件
│       VI指南、品牌手册、Tone of Voice、设计规范
│       检索用途：品牌一致性检查（Strategy输出对比）
│       chunk size：800字符 / 100重叠
│       生命周期：长期，跨项目复用
│
├── namespace: brand_history_{client_id}
│       历史提案类 + 品牌内容类
│       过往campaign deck、策略文档、历史文案、social内容
│       检索用途：风格参照（Slide Content Agent生成文案时）
│       chunk size：历史提案1200字符/200重叠，文案400字符/50重叠
│       生命周期：长期，持续积累
│
│  ── 项目临时库（Project Library）────────────────────────────
├── namespace: project_{project_id}
│       项目级文件，项目结束后归档
│       需求文档、客户brief、会议记录、竞品资料、竞品文案
│       检索用途：Brief解析背景参考、Research Agent查历史竞品分析
│       chunk size：需求文档600字符/100重叠，竞品资料800字符/150重叠
│       生命周期：项目周期内，结束后标记archived
│
│  ── 资源库（Resource Index）─────────────────────────────────
├── namespace: resource_kol
│       KOL/KOC档案描述文本（平台、内容方向、受众画像、风格描述）
│       检索用途：Resource Agent按受众和风格向量匹配KOL
│
├── namespace: resource_media
│       媒体资源描述文本（媒体定位、覆盖领域、受众特征）
│       检索用途：Resource Agent按行业和受众匹配媒体资源
│
├── namespace: resource_vendor
│       供应商描述文本（服务类型、擅长行业、过往案例描述）
│       检索用途：Resource Agent按活动类型匹配供应商
│
└── namespace: resource_placement
        媒介资源描述文本（媒介类型、覆盖城市、受众场景）
        检索用途：Resource Agent按地域和受众匹配媒介资源
```

### 3.2 各namespace检索用途对照

| 检索场景       | Agent               | Namespace                 | 检索逻辑                         |
| -------------- | ------------------- | ------------------------- | -------------------------------- |
| 品牌一致性检查 | Strategy Agent后    | brand*spec*{client_id}    | 策略关键词 vs 品牌规范语义相似度 |
| 文案风格参照   | Slide Content Agent | brand*history*{client_id} | 调性描述词检索历史文案风格       |
| 历史竞品查重   | Research Agent      | project\_{project_id}     | 竞品名称检索是否有历史分析       |
| KOL匹配        | Resource Agent      | resource_kol              | 受众画像+内容方向向量匹配        |
| 媒体匹配       | Resource Agent      | resource_media            | 行业+受众特征向量匹配            |
| 供应商匹配     | Resource Agent      | resource_vendor           | 活动类型+地域向量匹配            |
| 媒介匹配       | Resource Agent      | resource_placement        | 受众场景+城市向量匹配            |

### 3.3 文件处理pipeline

```
用户上传文件（PDF / PPTX / DOCX / 图片）
        ↓
Celery异步任务接收
        ↓
文件归属判断
├── 有project_id → Project Library
└── 无project_id → Brand Library
        ↓
文件类型识别（决定走哪个namespace和chunk策略）
├── brand_spec    → brand_spec_{client_id}
├── brand_history → brand_history_{client_id}
├── project_doc   → project_{project_id}
├── competitor    → project_{project_id}
└── visual_ref    → 暂存MongoDB，Phase 2接入多模态处理
        ↓
格式解析
├── PDF  → PyPDF2
├── PPTX → python-pptx提取文本+页面结构
└── DOCX → python-docx
        ↓
按类型分块（chunk size见3.1）
        ↓
Embedding（text-embedding-3-small）
        ↓
写入对应Pinecone namespace
        ↓
元数据写入MongoDB files collection
（filename、file_category、file_type、namespace、processing_status）
```

---

## 4. 稳定性设计

### 4.1 Request Budget

每次pipeline执行设置资源上限，防止Agent循环或外部调用失控：

```python
@dataclass
class RequestBudget:
    max_llm_calls: int = 30        # 整个pipeline最多调用LLM次数
    max_search_calls: int = 10     # Research Agent最多搜索次数
    max_retry_per_agent: int = 2   # 单个Agent最多重试次数
    max_total_seconds: int = 300   # 整个pipeline最长5分钟
    current_llm_calls: int = 0
    current_search_calls: int = 0
    start_time: float = field(default_factory=time.time)

    def check(self) -> None:
        """预算超出时抛出异常，触发降级"""
        if self.current_llm_calls >= self.max_llm_calls:
            raise BudgetExceeded("LLM call limit reached")
        if time.time() - self.start_time > self.max_total_seconds:
            raise BudgetExceeded("Pipeline timeout")
```

### 4.2 Deterministic Fallback降级链

每个外部依赖都有有序降级方案，任何一个挂掉不影响整体流程：

```
Tavily搜索挂了
    → 降级到DuckDuckGo
    → 再降级到只用内部历史库
    → 标记Research结果为"仅内部数据"

Pinecone挂了
    → 降级到MongoDB全文索引检索
    → 标记RAG结果为"降级模式"

LLM超时
    → 重试一次
    → 换备用模型
    → 返回模板化内容 + 警告提示

python-pptx生成失败
    → 降级输出Markdown格式提案
    → 通知用户PPT生成失败，提供文字版
```

### 4.3 Semantic Response Cache

针对Research Agent的重复调研场景做缓存，避免相同客户重复搜索：

```
缓存Key：{client_id}:{competitor_name}:{date_bucket}
date_bucket：按30天分桶（同一客户30天内竞品数据复用）

命中条件：
- 同一client_id
- 竞品名称完全匹配
- 距上次搜索30天内

命中后：直接返回缓存的Research结果
        在结果中标注"数据来源：缓存（{date}）"
        让用户决定是否强制刷新
```

存储：Redis，TTL = 30天

---

## 5. 可观测性设计

### 5.1 Per-Stage Metrics

追踪每个Agent节点的实际价值，数据存入MongoDB：

```python
stage_metrics = {
    "project_id": "...",
    "brief_analyzer": {
        "clarification_triggered": True,    # 是否触发了追问
        "missing_fields": ["kpi", "budget"] # 缺了哪些字段
    },
    "brand_consistency_check": {
        "triggered_revision": False,         # 是否打回修改
        "issues_found": []
    },
    "narrative_agent": {
        "issues_found": 2,                   # 发现几处逻辑断裂
        "retry_count": 1,                    # 循环了几次
        "issues_detail": ["洞察与策略不一致", "预算与渠道优先级矛盾"]
    },
    "resource_agent": {
        "triggered": True,
        "resource_types": ["kol", "media"],
        "matched_count": 8
    },
    "request_budget": {
        "llm_calls_used": 18,
        "search_calls_used": 5,
        "total_seconds": 142
    }
}
```

### 5.2 Analytics Dashboard（前端页面）

基于stage_metrics数据展示：

- 各Agent触发率和拦截率
- Brief Analyzer追问频率（说明哪类信息客户最常遗漏）
- Narrative Agent发现逻辑断裂的分布（哪类问题最常见）
- 平均pipeline执行时间
- Request Budget使用分布（成本分析）
- 缓存命中率

---

## 6. 技术选型汇总

### 6.1 后端

| 组件      | 技术                            | 版本    | 说明                   |
| --------- | ------------------------------- | ------- | ---------------------- |
| API框架   | FastAPI                         | 0.115   | 异步REST + WebSocket   |
| Agent编排 | LangGraph                       | 0.2     | 状态机 + HITL支持      |
| LLM       | Claude claude-sonnet-4-20250514 | -       | 主力模型               |
| Embedding | text-embedding-3-small          | -       | 文档向量化             |
| 网络搜索  | Tavily                          | -       | Research Agent搜索工具 |
| 任务队列  | Celery + Redis                  | 5.3 / 7 | 异步重任务             |
| PPT生成   | python-pptx                     | -       | Deck输出               |
| PDF解析   | PyPDF2                          | -       | 文件处理               |

### 6.2 数据层

| 组件       | 技术          | 用途                             |
| ---------- | ------------- | -------------------------------- |
| 主数据库   | MongoDB Atlas | 客户档案、项目、提案、反馈、指标 |
| 向量数据库 | Pinecone      | RAG检索（namespace隔离）         |
| 缓存       | Redis         | Celery broker + 语义缓存         |

### 6.3 前端

| 组件     | 技术          | 说明                             |
| -------- | ------------- | -------------------------------- |
| 框架     | Next.js 14    | App Router + SSR                 |
| 语言     | TypeScript    | 类型安全                         |
| 状态管理 | Redux Toolkit | 全局状态 + RTK Query             |
| 实时通信 | WebSocket     | Agent执行流式输出 + HITL节点推送 |
| 样式     | Tailwind CSS  | 工具类样式                       |

### 6.4 基础设施

| 组件     | 技术                    | 说明                  |
| -------- | ----------------------- | --------------------- |
| 容器化   | Docker + Docker Compose | 本地和部署            |
| 反向代理 | Nginx                   | 路由 + SSL            |
| CI/CD    | GitHub Actions          | 自动测试 + Docker构建 |
| 代码质量 | Black + isort + flake8  | 格式化和lint          |
| 测试     | pytest                  | 单元测试              |

---

## 7. MongoDB数据模型

```
collections:
│
├── clients                         # 客户账户
│   ├── _id
│   ├── name
│   ├── industry
│   ├── default_deck_structure      # 客户级PPT默认结构
│   └── created_at
│
├── projects                        # 提案项目
│   ├── _id
│   ├── client_id
│   ├── name
│   ├── status                      # draft / in_progress / completed / archived
│   ├── custom_deck_structure       # 项目级PPT结构（最高优先级）
│   └── created_at
│
├── proposals                       # 提案版本
│   ├── _id
│   ├── project_id
│   ├── version                     # v1, v2, v3...
│   ├── structured_brief
│   ├── strategy_result
│   ├── deck_structure
│   ├── slides
│   ├── pptx_path
│   ├── stage_metrics
│   └── created_at
│
│  ── 文件库 ────────────────────────────────────────────────────
│
├── files                           # 所有上传文件的元数据记录
│   ├── _id
│   ├── client_id
│   ├── project_id                  # null = Brand Library；有值 = Project Library
│   ├── filename
│   ├── file_category               # brand_library / project_library
│   ├── file_type
│   │     brand_library下：
│   │       brand_spec              # VI、品牌手册、ToV
│   │       brand_history_proposal  # 历史提案deck
│   │       brand_history_copy      # 历史文案、social内容
│   │     project_library下：
│   │       project_brief           # 客户brief、会议记录
│   │       competitor_copy         # 竞品文案、竞品资料
│   │       visual_ref              # Moodboard、竞品截图（Phase 2处理）
│   ├── pinecone_namespace           # 写入的namespace名称
│   ├── chunk_count                 # 分块数量
│   ├── processing_status           # pending / processing / done / failed
│   ├── processing_error            # 失败原因
│   └── uploaded_at
│
│  ── 资源库 ────────────────────────────────────────────────────
│
├── resources                       # 统一资源库（四类共用collection，type区分）
│   ├── _id
│   ├── type                        # kol / media / vendor / placement
│   ├── name
│   ├── tags                        # 标签数组，各类型标签体系不同（见下）
│   ├── pricing                     # { min, max, unit, currency }
│   ├── collaboration_history       # [{ client, project_type, date, performance }]
│   ├── pinecone_namespace          # 对应resource_{type} namespace
│   └── metadata                    # 类型特有字段（见下）
│
│   KOL metadata示例：
│   { platform, followers, content_direction, audience_profile,
│     mcn, contact, engagement_rate }
│
│   媒体 metadata示例：
│   { media_name, media_type, coverage_domain, contact_name,
│     contact_line, publish_types }
│
│   供应商 metadata示例：
│   { service_types, regions, past_clients, quality_rating }
│
│   媒介 metadata示例：
│   { placement_type, cities, audience_size, available_periods }
│
│  ── 反馈与学习 ─────────────────────────────────────────────────
│
├── feedback                        # 客户反馈
│   ├── _id
│   ├── proposal_id
│   ├── client_id
│   ├── content                     # 反馈原文
│   ├── approved_directions         # 认可的方向（写回Brand Library参考）
│   ├── rejected_directions         # 否定的方向（后续生成自动规避）
│   ├── rerun_triggered             # bool
│   ├── rerun_from_node             # strategy / resource / deck_structure / slide / null
│   └── created_at
│
└── stage_metrics                   # 各阶段执行指标（独立collection便于聚合分析）
    ├── _id
    ├── proposal_id
    ├── project_id
    ├── client_id
    ├── brief_analyzer              # { clarification_triggered, missing_fields }
    ├── brand_consistency_check     # { triggered_revision, issues_found }
    ├── research_agent              # { sources_used, cache_hit, search_count }
    ├── narrative_agent             # { issues_found, retry_count, issues_detail }
    ├── resource_agent              # { triggered, resource_types, matched_count }
    ├── request_budget              # { llm_calls_used, search_calls_used, total_seconds }
    └── created_at
```

---

## 8. API端点设计

```
认证
POST   /api/v1/auth/login
POST   /api/v1/auth/refresh

客户管理
GET    /api/v1/clients
POST   /api/v1/clients
PATCH  /api/v1/clients/{id}/deck-structure   # 设置客户级默认结构

项目管理
GET    /api/v1/projects?client_id=...
POST   /api/v1/projects
PATCH  /api/v1/projects/{id}

文件管理
POST   /api/v1/files/upload                  # 上传（异步处理）
GET    /api/v1/files?client_id=&project_id=
DELETE /api/v1/files/{id}

Pipeline执行
POST   /api/v1/pipeline/start               # 启动pipeline
POST   /api/v1/pipeline/{id}/confirm        # HITL节点用户确认
POST   /api/v1/pipeline/{id}/rerun          # 指定节点重跑
GET    /api/v1/pipeline/{id}/status         # 查询执行状态

提案管理
GET    /api/v1/proposals?project_id=...
GET    /api/v1/proposals/{id}
GET    /api/v1/proposals/{id}/download      # 下载.pptx
POST   /api/v1/proposals/{id}/feedback      # 录入客户反馈

资源库
GET    /api/v1/resources?type=&tags=
POST   /api/v1/resources
POST   /api/v1/resources/import             # Excel批量导入

分析
GET    /api/v1/analytics/pipeline-metrics   # Stage metrics汇总
GET    /api/v1/analytics/cache-stats        # 缓存命中率

系统
GET    /health
WS     /ws/pipeline/{pipeline_id}           # 实时推送Agent执行状态
```

---

## 9. WebSocket事件设计

前端通过WebSocket实时接收pipeline执行状态，实现流式展示和HITL节点交互：

```
Server → Client 事件：
{
  "event": "agent_started",
  "agent": "research_agent",
  "message": "正在搜索竞品信息..."
}

{
  "event": "agent_completed",
  "agent": "strategy_agent",
  "output": { ...strategy_result }
}

{
  "event": "hitl_required",        ← 触发前端弹出确认界面
  "node": "node_2_strategy",
  "data": { ...strategy_result },
  "message": "请确认策略方向"
}

{
  "event": "pipeline_completed",
  "pptx_url": "/api/v1/proposals/xxx/download"
}

{
  "event": "budget_warning",
  "message": "LLM调用已达80%上限"
}

{
  "event": "fallback_triggered",
  "agent": "research_agent",
  "reason": "Tavily不可用，已切换至内部历史库"
}

Client → Server 事件：
{
  "event": "hitl_response",
  "node": "node_2_strategy",
  "action": "confirm"             # confirm / revise
  "feedback": "Big Idea方向偏了，希望更聚焦科技感"
}
```

---

## 10. Docker Compose服务编排

```yaml
services:
  frontend:        # Next.js,  Port 3000
  backend:         # FastAPI,  Port 8000
  worker:          # Celery Worker（文件处理 + PPT生成）
  redis:           # Port 6379（Celery broker + 语义缓存）
  mongodb:         # Port 27017
  nginx:           # Port 80/443（反向代理）

networks:
  mkt_agent_network

volumes:
  mongodb_data
  redis_data
  pptx_output      # 生成的PPT文件
  uploaded_files   # 用户上传的原始文件
```

---

## 11. CI/CD Pipeline

```
git push
    ↓
GitHub Actions触发
    │
    ├── 并行执行
    │   ├── pytest（后端单元测试）
    │   ├── lint（Black + flake8）
    │   └── 前端build检查
    │
    └── 全部通过
            ↓
        Build Docker Images
            ↓
        Push to Docker Hub
            ↓
        Ready to Deploy
```

---

## 12. 项目目录结构

```
mkt-agent/
├── backend/
│   ├── api/
│   │   ├── main.py
│   │   └── v1/
│   │       ├── endpoints/
│   │       │   ├── auth.py
│   │       │   ├── clients.py
│   │       │   ├── projects.py
│   │       │   ├── files.py
│   │       │   ├── pipeline.py
│   │       │   ├── proposals.py
│   │       │   ├── resources.py
│   │       │   └── analytics.py
│   │       └── websocket.py
│   ├── core/
│   │   ├── agents/
│   │   │   ├── brief_analyzer.py
│   │   │   ├── research_agent.py
│   │   │   ├── strategy_agent.py
│   │   │   ├── resource_agent.py
│   │   │   ├── deck_orchestrator.py
│   │   │   ├── slide_content_agent.py
│   │   │   ├── narrative_agent.py
│   │   │   └── ppt_builder.py
│   │   ├── graph/
│   │   │   ├── pipeline.py          # LangGraph主流程
│   │   │   ├── state.py             # PipelineState定义
│   │   │   └── nodes.py             # 各节点函数
│   │   ├── rag/
│   │   │   ├── indexer.py           # 文件向量化
│   │   │   ├── retriever.py         # 检索逻辑
│   │   │   └── cache.py             # 语义缓存
│   │   ├── stability/
│   │   │   ├── budget.py            # Request Budget
│   │   │   └── fallback.py          # 降级链
│   │   ├── database/
│   │   │   └── repositories/        # MongoDB操作
│   │   ├── models/                  # Pydantic models
│   │   ├── tasks.py                 # Celery任务
│   │   └── config.py
│   ├── tests/
│   │   └── unit/
│   └── requirements.txt
├── frontend/
│   ├── app/                         # Next.js App Router
│   ├── components/
│   │   ├── pipeline/                # Pipeline执行界面
│   │   ├── hitl/                    # HITL确认组件
│   │   ├── deck-preview/            # PPT预览
│   │   └── analytics/               # Dashboard
│   ├── store/                       # Redux
│   ├── hooks/
│   │   └── usePipelineSocket.ts     # WebSocket hook
│   └── types/
├── infrastructure/
│   └── docker/
│       └── docker-compose.yml
├── .github/
│   └── workflows/
│       └── ci.yml
└── README.md
```

---

_本文档随开发推进持续更新_
