# Eval: Campaign Knowledge Base Retrieval Quality

**Module:** Campaign Knowledge Base — Proposition Indexing + Retrieval  
**Files:** `backend/core/rag/campaign_index.py`, `backend/core/rag/campaign_retriever.py`  
**Status:** Phase 3 complete — 14 records, 49 queries, full primary eval run  
**Last run:** 2026-06-06

---

## What We're Testing

Two questions, different priority:

| Priority | Question | Test | Metric |
|---|---|---|---|
| **Primary** | Does the pipeline find the right campaign for agent queries? | Recall@K | Recall@3, false positive rate |
| **Secondary** | Is the proposition count range (8–15) correct? | Coverage + Redundancy sweep | Coverage@N, Redundancy@N |

The primary test validates that the system works end-to-end. The secondary test validates a specific design parameter within it.

---

## Why Semantic Search, Not Grep

Metadata filter (campaign_type, industry, budget_tier) already works like grep — deterministic field matching. It is already in the system.

Propositions + embeddings handle what metadata filter cannot:

**1. Vocabulary mismatch across campaigns and queries**

```
Campaign A wrote:  "KOC tier 占预算 10%"
Campaign B wrote:  "腰部达人投入比例偏低"
Campaign C wrote:  "grassroots influencer budget allocation"
Agent query:       "小 KOL 性价比分析"
```

No single keyword finds all three. Embedding captures semantic meaning regardless of vocabulary.

**2. Derived insights — facts that don't exist in any field**

The record stores:
```json
"koc_budget_ratio": 0.1,
"koc_engagement_contribution": 0.6
```

The proposition states: `"KOC 以 10% 预算贡献 60% 互动量"`

This sentence exists nowhere in the raw record. It is LLM-derived from two fields. Grep cannot find it because it was never written.

**3. Ranking**

Grep returns binary match/no-match. 100 campaigns all contain "KOL" — grep returns all 100. Vector similarity returns ranked top-K, directly usable by agents.

**Two-layer design:**
```
Metadata filter (= grep)   → fast prefilter on known structured fields
Proposition embedding       → semantic ranking on derived insights
```

These are complementary, not competing.

---

## What Propositions Actually Do

Propositions are the **search surface** of a CampaignRecord — they determine whether the right campaign appears in Pinecone top-K results.

They are NOT a replacement for reading the full record. After retrieval, per-agent profiles fetch only the specific modules each agent needs from MongoDB (e.g., Media Planner gets media_plan + outcome only). That filtering is done by profiles, not propositions.

```
Stage 1: Proposition → Campaign   (tested here)
  Purpose:   make the right campaign findable
  Storage:   Pinecone proposition vectors
  Metric:    Recall@K

Stage 2: Campaign → Module        (not tested here — profiles are deterministic)
  Purpose:   return only the fields this agent needs
  Storage:   MongoDB campaign_records
  Mechanism: per-agent profile controls which modules are returned
```

---

## Test Data

**Corpus:** 14 records, ~200 propositions total (avg 14.5/record), archived 2026-06-06

| File | Record ID (first 8) | Industry | Type | Props |
|---|---|---|---|---|
| 安踏24Q3【中国甲】营销结案 | `281feb42` | 运动服饰 | 奥运营销 | 15 |
| MINI汽车品牌全年年度营销方案 | `819f00e5` | 汽车 | 年度规划 | 15 |
| 美团外卖整合营销方案 | `6dac3b91` | 互联网/外卖 | 整合营销 | 15 |
| COSTA罐装咖啡新品上市整合营销 | `cd54c74c` | FMCG/饮料 | 新品上市 | 15 |
| popchrio欧可芮小红书营销方案 | `dfeccd49` | 美妆护肤 | 小红书种草 | 13 |
| 美津浓MIZUNO户外营销计划 | `486b2d6a` | 运动户外 | 年度营销计划 | 15 |
| 雀巢雪咖慕思摇一摇 | `f8b81938` | 快消/饮料 | 新品上市 | 15 |
| 嘉人POWER TRIP女性影响力之夜 | `4f0c75ee` | 时尚媒体 | 品牌活动 | 14 |
| 小天鹅×肯德基跨界联动 | `2dd63675` | 家电 | 跨界联名 | 14 |
| IRONMAN健身器械直播间营销 | `d2d8af23` | 健身器材 | 直播运营 | 15 |
| 百特牛奶×迪卡侬双节联名 | `1781fb74` | 乳制品 | 联名节点 | 15 |
| 本田雅阁新媒体账号矩阵 | `78174665` | 汽车 | 社媒运营 | 16 |
| ETC车宝APP品牌策略 | `95af472b` | 汽车后市场 | 品牌升级 | 15 |
| 山水旅情文化旅游节 | `d6d49672` | 文旅 | 节事整合 | 14 |

**Query set:** 49 queries across 4 types. See `scripts/eval_data/query_set.json`.

| Type | Count | Description |
|---|---|---|
| broad | 16 | Wide-topic queries — test general recall |
| specific | 18 | Narrow-concept queries — test proposition vocabulary depth |
| cross-field | 8 | Multi-concept queries — most realistic for agent use |
| irrelevant | 7 | No relevant record exists — test FPR / gate effectiveness |

---

## PRIMARY TEST: Recall@K

### Step 1: Build Query Set

Write 15–20 queries that simulate what agents actually send to `retrieve_campaign_knowledge()`. Cover three types:

**Relevant queries** (安踏 record should appear in top-3):

```
Broad match:
  "运动品牌借势营销传播策略"
  "奥运营销整合传播方案"

Specific match (targets a particular proposition):
  "KPI 超出预期的运动品牌案例"
  "三阶段传播节奏设计"
  "品牌联名纪录片内容策略"
  "小红书作为主阵地的传播方案"

Cross-field match (tests derived insights):
  "整合传播 + KPI 达成率超 100%"
  "奥运借势 + 内容分发策略"
```

**Irrelevant queries** (安踏 should NOT appear — measures false positive rate):

```
  "银行理财产品老年客户营销"
  "美妆新品电商首发策略"
  "B2B SaaS 品牌建设方案"
  "母婴品牌小红书种草"
```

Store in: `scripts/eval_data/query_set.json`

```json
[
  {
    "id": "Q-01",
    "query": "运动品牌借势营销传播策略",
    "relevant_ids": ["anta_record_id"],
    "type": "broad"
  },
  {
    "id": "Q-02",
    "query": "KPI 超出预期的运动品牌案例",
    "relevant_ids": ["anta_record_id"],
    "type": "specific"
  },
  {
    "id": "Q-10",
    "query": "银行理财产品老年客户营销",
    "relevant_ids": [],
    "type": "irrelevant"
  }
]
```

`relevant_ids` is a list to support multiple relevant records as the KB grows. Empty list = no relevant record exists (used to compute false positive rate and Precision).

### Step 2: Run Retrieval at Different N Values

For each N in [5, 10, 15, 20], index the record with that proposition count, then run all queries.

```python
# scripts/eval_retrieval.py

import asyncio
import json
from backend.core.rag.campaign_retriever import retrieve_campaign_knowledge

TARGET_COUNTS = [5, 10, 15, 20]
QUERY_SET_PATH = "scripts/eval_data/query_set.json"
ORG_ID = "eval-org"
K = 3


def recall_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float:
    """Fraction of relevant records found in top-K results."""
    if not relevant_ids:
        return 0.0
    top_k = set(retrieved_ids[:k])
    hits = sum(1 for rid in relevant_ids if rid in top_k)
    return hits / len(relevant_ids)


def precision_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float:
    """Fraction of top-K results that are actually relevant."""
    top_k = retrieved_ids[:k]
    if not top_k:
        return 0.0
    hits = sum(1 for rid in top_k if rid in relevant_ids)
    return hits / len(top_k)


def reciprocal_rank(retrieved_ids: list[str], relevant_ids: set[str]) -> float:
    """1 / rank of the first relevant result. 0 if not found."""
    for i, rid in enumerate(retrieved_ids, start=1):
        if rid in relevant_ids:
            return 1.0 / i
    return 0.0


async def eval_at_n(n: int, queries: list[dict]) -> dict:
    # Re-index with target_count=n before running (see campaign_index.py)
    per_query = []
    for q in queries:
        relevant = set(q["relevant_ids"])
        retrieved = await retrieve_campaign_knowledge(
            query=q["query"],
            org_id=ORG_ID,
            profile_name="strategy_reference",
        )
        retrieved_ids = [r["campaign_record_id"] for r in retrieved]
        per_query.append({
            "query_id": q["id"],
            "type": q["type"],
            "recall_at_k":    recall_at_k(retrieved_ids, q["relevant_ids"], K),
            "precision_at_k": precision_at_k(retrieved_ids, q["relevant_ids"], K),
            "rr":             reciprocal_rank(retrieved_ids, relevant),
            "retrieved_ids":  retrieved_ids,
        })
    return {"n": n, "k": K, "queries": per_query}


async def main():
    with open(QUERY_SET_PATH) as f:
        queries = json.load(f)

    for n in TARGET_COUNTS:
        result = await eval_at_n(n, queries)
        with open(f"scripts/eval_data/eval_n{n}.json", "w") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        relevant_qs = [q for q in result["queries"] if q["type"] != "irrelevant"]
        irrelevant_qs = [q for q in result["queries"] if q["type"] == "irrelevant"]

        recall    = sum(q["recall_at_k"]    for q in relevant_qs) / len(relevant_qs)
        precision = sum(q["precision_at_k"] for q in relevant_qs) / len(relevant_qs)
        mrr       = sum(q["rr"]             for q in relevant_qs) / len(relevant_qs)
        fpr       = sum(1 for q in irrelevant_qs if q["precision_at_k"] > 0) / len(irrelevant_qs)

        print(f"N={n:>2}  Recall@{K}={recall:.0%}  Precision@{K}={precision:.0%}  MRR={mrr:.2f}  FPR={fpr:.0%}")


asyncio.run(main())
```

### Step 3: Three Metrics Defined

**Recall@K** — did we find what we should have found?
```
Recall@3 = relevant records in top-3 / total relevant records for this query

Example: query has 2 relevant records, both appear in top-3 → Recall@3 = 100%
         query has 2 relevant records, only 1 in top-3   → Recall@3 = 50%
```

**Precision@K** — is what we returned actually relevant?
```
Precision@3 = relevant records in top-3 / 3

Example: top-3 contains 2 relevant + 1 noise → Precision@3 = 67%
         top-3 contains 0 relevant            → Precision@3 = 0%
```

**MRR (Mean Reciprocal Rank)** — how high in the ranking does the relevant result appear?
```
RR per query = 1 / rank of first relevant result
  → relevant result at rank 1: RR = 1.0
  → relevant result at rank 2: RR = 0.5
  → relevant result at rank 3: RR = 0.33
  → not found:                 RR = 0.0

MRR = average RR across all relevant queries
```

MRR matters because Recall@K treats "rank 1" and "rank 3" identically. An agent using top-1 context benefits more from MRR = 1.0 than MRR = 0.33 even if both achieve Recall@3 = 100%.

**False Positive Rate** — are we returning results when we shouldn't?
```
FPR = irrelevant queries that returned ≥1 result / total irrelevant queries

High FPR means the self-verification gate isn't catching low-relevance retrievals.
```

### Results

**Phase 3 — 14 records, 49 queries (run 2026-06-06):**

| Mode | Recall@3 | Precision@3 | MRR | FPR |
|---|---|---|---|---|
| RAW (verify=False) | **81%** | 58% | 0.77 | 100% |
| With Gate (verify=True) | **81%** | 58% | 0.77 | **0%** |
| Gate impact | 0% | 0% | 0.00 | **−100%** |

Full results saved to `scripts/eval_data/eval_results.json`.

**By query type:**

| Query type | Count | Recall@3 | Precision@3 | MRR |
|---|---|---|---|---|
| Broad | 16 | **75%** | 62% | 0.75 |
| Specific | 18 | **94%** | 67% | 0.86 |
| Cross-field | 8 | **67%** | 37% | 0.62 |
| Irrelevant/FPR | 7 | — | — | 100% raw / **0% gated** |

**Recall change vs Phase 2 (6 records):** 94% → 81%  
Expected: as corpus grows from 6 → 14 records, top-3/total changes from 50% → 21% — the retrieval task becomes genuinely harder. MRR improved (0.74 → 0.77), meaning when the system hits, it ranks higher.

**Failure analysis (8 misses out of 42 relevant queries):**

| Query | Root cause |
|---|---|
| Q-04 "品牌借势IP联名" | ANTA联名案例命中rank 4；新增百特×迪卡侬等联名 records 竞争加剧 |
| Q-10 "O2O本地生活平台用户增长" | 美团 propositions 无"用户增长"语言，rank 0 |
| Q-11 COSTA (rank 4) | 雀巢（同为饮料新品上市）推挤，COSTA 退出 top-3 |
| Q-12 popchrio (rank 5) | 同类 records 竞争 + industry=null 历史遗留（已修复，新 propositions 有效） |
| Q-19 ANTA+COSTA 多 record | 两条都需进 top-3，14条语料库下概率降低 |
| Q-20 "电商大促" | 美团外卖 ≠ 电商平台，query 本身偏离 record 内容 |
| Q-24 popchrio cross-field | 跨字段 query rank 4，与同类 records 竞争 |
| Q-29 COSTA+popchrio 多 record | 多 record cross-field，两条均未进 top-3 |

**Gate design note:**  
Gate eliminates 100% of false positives (7/7 irrelevant queries correctly returned empty) with 0% Recall cost. Gate works because it now receives the matched proposition content (not just metadata labels) — allows genuine content-level relevance judgment.

**Historical progression:**

| Phase | Records | Queries | Recall@3 (raw) | MRR | FPR (gated) |
|---|---|---|---|---|---|
| Phase 1 baseline | 6 | 20 | 81% | 0.58 | — (gate broken) |
| Phase 2 (prompt fix + gate fix) | 6 | 16* | 94% | 0.74 | **0%** |
| Phase 3 (expanded corpus) | 14 | 49 | 81% | **0.77** | **0%** |

*16 relevant queries in Phase 2 after removing broken test cases.*

---

## Optimization Opportunities

The 8 misses fall into three distinct patterns. Each maps to a specific component and has a concrete fix.

---

### Pattern 1 — Cross-field query scoring (3 misses: Q-19, Q-24, Q-29)

**What the numbers show:** Cross-field Recall = 67%, vs. Specific = 94% and Broad = 75%. Cross-field queries also have the lowest MRR (0.62) and Precision (37%).

**Root cause:** Every proposition covers one fact. A cross-field query (e.g. "COSTA + popchrio 小红书内容策略对比") requires two concepts to score simultaneously. No single proposition does that → similarity score is split → target record falls below rank 3.

**Fix options:**

| Option | Where | Description |
|---|---|---|
| **More cross-field propositions** | `campaign_index.py` prompt rule C | Current: "at least 1" cross-field synthesis proposition. Increase to "at least 2–3, covering different field combinations" (e.g. channel strategy × budget efficiency, KPI outcome × content format, audience insight × platform role). Re-index all records. |
| **Query decomposition at retrieval** | `campaign_retriever.py` | Split "A + B" queries into two sub-queries, retrieve each, merge and re-rank results. More robust for complex queries; implementation is more involved. |

**Recommended:** Start with the prompt fix — low cost, re-index, re-run eval. If cross-field Recall < 80% after re-index, add query decomposition.

**Expected impact:** Cross-field Recall 67% → 80%+

---

### Pattern 2 — Proposition vocabulary mismatch (2 misses: Q-10, Q-20)

**What the numbers show:** 2 specific-query misses that are vocabulary failures, not semantic failures — the correct record exists but its propositions don't contain the language the agent uses.

- **Q-10** ("O2O 本地生活平台用户增长"): 美团's propositions describe tactics and reach; no proposition contains "用户增长" or business-objective language → rank 0
- **Q-20** ("电商大促节点营销"): 美团外卖 ≠ ecommerce platform, and propositions don't bridge to "大促节点" framing; the semantic miss is partly a query problem but also a vocabulary gap

**Root cause:** Propositions are written in the *campaign's* vocabulary (marketing tactics, channel names, content formats). Agents query in *business objectives* vocabulary (用户增长, 转化率提升, 电商节点, ROI). These two vocabularies don't always overlap in embedding space.

**Fix:** Add an explicit rule to the proposition prompt:

```
对每条涉及业务目标的命题，同时用"营销执行视角"和"业务结果视角"两种表述方式写出。
例：
  执行视角：小红书 KOL+素人双轨布局触达年轻女性
  业务视角：通过 KOL+素人双轨种草策略实现目标人群 awareness 提升
```

**Expected impact:** Specific Recall 94% → ~100% (closes the 2 vocabulary-driven misses)

---

### Pattern 3 — Same-category record displacement (3 misses: Q-04, Q-11, Q-12)

**What the numbers show:** These are near-misses — target record at rank 4 or 5, not absent. As corpus grows, same-category records push each other below the K=3 threshold.

- Q-11: COSTA (饮料新品上市) displaced by 雀巢 (same category, same scenario) → rank 4
- Q-12: popchrio (小红书种草) in a crowded same-type cluster → rank 5
- Q-04: ANTA 联名案例 displaced by 百特×迪卡侬 and 小天鹅×KFC (new co-branding records) → rank 4

**Root cause:** Records sharing industry + campaign_type have similar meta prefixes and overlapping proposition vocabulary. Their proposition embeddings cluster close together. The "wrong" record wins by a small cosine margin.

**Fix options:**

| Option | Where | Description |
|---|---|---|
| **Add brand name to meta prefix** | `campaign_index.py` `_build_meta_prefix()` | Current prefix: `[行业 \| 类型 \| 预算 \| 受众 \| 场景]`. Add `brand_name` as first element → `[品牌 \| 行业 \| ...]`. Differentiates same-category records at the proposition level. |
| **Increase K** | `campaign_retriever.py` | K=3 → K=5 would recover all three near-misses immediately. Tradeoff: agents receive more (possibly noisier) context; changes Precision baseline. |

**Recommended:** Add brand name to meta prefix — fixes the root cause without changing retrieval behavior. K increase is a fallback if displacement continues as corpus grows past 20+ records.

**Expected impact:** Recovers 2–3 near-misses; Recall@3 81% → ~88%

---

### Summary: what to fix, what to leave alone

| Component | Current | Action |
|---|---|---|
| Proposition prompt rule C (cross-field) | "at least 1" synthesis prop | Increase to 2–3 with field-combination templates |
| Proposition prompt (vocabulary coverage) | Marketing-vocabulary only | Add business-objective paraphrase rule |
| Meta prefix | No brand name | Add brand name as first element |
| Gate (FPR) | **0%** | No change — working correctly |
| MRR | **0.77** | No change — ranking quality is healthy |
| K parameter | 3 | Hold at 3; revisit if corpus exceeds 30 records |

**Execution order:** Prompt changes (rule C + vocabulary rule) → re-index all 14 records → re-run eval → assess. If cross-field Recall still < 80%, implement query decomposition. Add brand name to prefix in the same re-index pass.

---

## Known Gaps in Current Metrics

The four primary metrics (Recall@K, Precision@K, MRR, FPR) answer one question: *did the pipeline return the right record?* Two meaningful questions remain unanswered.

---

### Gap 1 — Proposition-level quality

**What we measure:** Record-level retrieval success — whether the correct `campaign_record_id` appears in top-K results.

**What we don't measure:** Whether the specific proposition that triggered the match actually addresses the query concept.

**Why it matters:**

```
Query: "小红书种草 ROI 评估"

Top-1 hit: ANTA record (correct record ✓)

But matched proposition:
  "[运动服饰 | 奥运营销] KOC 以 10% 预算贡献 60% 互动量"

The record is correct. But the agent receives the ANTA case as context because of
a budget-efficiency proposition, not a Xiaohongshu ROI proposition. If the agent
synthesises from this context, it will anchor on KOC budget split instead of
platform ROI evaluation methodology.
```

Current Recall@K cannot detect this — the record appears at rank 1, so Recall = 100%.

**Three implementation options:**

| Option | What it adds | Cost |
|---|---|---|
| **A. Log + inspect** | Extend `eval_results.json` to include matched proposition text alongside each retrieved record ID; manually review after each run | No automation cost; ~15 min inspection per run |
| **B. LLM-judge scoring** | For each (query, matched_proposition) pair, score 0–1: "Does this proposition directly address the query concept?" Average = Proposition Relevance Score | ~49 × 3 = 147 LLM calls per run; ~$0.05; fully automated |
| **C. Ground-truth proposition labels** | For each eval query, manually annotate which specific propositions should match; measure recall at proposition level | Highest fidelity; ~2h labeling effort; needed only once per stable query set |

**Recommended path:** Start with Option A (zero cost — log matched propositions, inspect patterns after the next run). Promote to Option B if inspection reveals systematic mismatch. Option C only if proposition-level recall becomes a primary KPI.

**Current priority:** Low. Phase 3 Specific Recall = 94% suggests propositions are well-targeted for single-concept queries. Cross-field Recall = 67% is more likely explained by multi-concept embedding distance than by proposition content mismatch.

---

### Gap 2 — Downstream impact on proposal quality

**What we measure:** Retrieval quality — whether the KB returns the right records when the agent asks.

**What we don't measure:** Whether retrieved cases actually improve final proposal quality.

**Why it matters:**

```
Retrieval pipeline:  Recall@3 = 81%  ← we measure this
                           ↓
Agent incorporates retrieved cases into proposal
                           ↓
Proposal quality:  ???  ← we don't measure this
```

A pipeline with 100% Recall@3 still produces poor proposals if:
- the agent's synthesis prompt doesn't leverage the retrieved context effectively
- retrieved cases are stylistically mismatched to the current brief
- the agent over-fits to retrieved examples instead of adapting them

This gap cannot be closed with offline retrieval metrics alone — it requires evaluating agent output.

**Three implementation options:**

| Option | What it adds | Cost |
|---|---|---|
| **A. A/B in production** | Route a fraction of real pitches to KB-disabled agents; compare human ratings of final proposals | Statistically rigorous; requires production traffic and domain-expert raters |
| **B. Offline human evaluation** | Generate pitch proposals with/without KB retrieval on 10–15 fixed brief inputs; have experts rate on relevance, specificity, and novelty | Feasible offline; ~$200–500 in rater time per evaluation round |
| **C. LLM proxy metric** | After proposal generation, prompt an LLM: "Does this proposal show evidence of drawing on the provided campaign examples?" | Cheap and automatable (~$0.10/run); imperfect proxy — LLM cannot evaluate true quality improvement |

**Recommended path:** Defer until the agent layer is stable. Gap 2 is not blocking — retrieval is a prerequisite for downstream quality, and Recall@3 = 81% confirms the prerequisite is met. The right moment to close Gap 2 is when the proposal agents are in user testing, at which point Option B (offline human eval) is the most actionable starting point.

---

## SECONDARY TEST: Proposition Quality

Complements the Recall@K test by explaining *why* a given N passes or fails.

### Step A: Ground Truth — Search-Triggering Facts

Manually read the CampaignRecord JSON. For each non-empty field, classify:

**Search-triggering** — if this fact is missing from propositions, a legitimate query will miss this campaign:
```
"传播采用三阶段结构（上市爆发/奥运借势/爆发延续）"
"KPI 超出预期，达成率 130%"
"与中国国家地理联名制作纪录片"
"小红书作为内容主阵地"
```

**Context-only** — agents read this after finding the campaign; not a search entry point:
```
"发布了 4 站分站内容 + 1 站混剪"    → execution detail
"视频播放量 XX 亿"                   → specific metric, in outcome module
"活动时间 2024 年 Q3"                → already in metadata filter
```

**Coverage@N = search-triggering facts covered / total search-triggering facts**

Target: 100%. Missing even one search-triggering fact means a real agent query will fail to surface this campaign.

Store in: `scripts/eval_data/anta_ground_truth.json`

```json
[
  {
    "id": "GT-01",
    "question": "传播结构分几个阶段？",
    "source_field": "communication_plan.phasing_structure",
    "type": "search-triggering"
  },
  {
    "id": "GT-02",
    "question": "具体发布了多少条内容？",
    "source_field": "execution.content_count",
    "type": "context-only"
  }
]
```

**Expected count:** 10–15 search-triggering, 15–20 context-only.

### Step B: Coverage Check

For each proposition set at each N, use LLM judge:

```
Proposition set: {proposition_set}
Question: {gt_question}
Does at least one proposition address this question? Answer yes/no only.
```

~15 GT items × 6 N values = ~90 LLM calls, < $0.20.

### Step C: Redundancy Check

```python
def redundancy_rate(propositions: list[str], threshold=0.85) -> float:
    embeddings = model.encode(propositions, normalize_embeddings=True)
    n = len(embeddings)
    dup_pairs = sum(
        1 for i in range(n) for j in range(i+1, n)
        if np.dot(embeddings[i], embeddings[j]) > threshold
    )
    return dup_pairs / (n * (n - 1) / 2) if n > 1 else 0.0
```

### Secondary Results Table

| N | Coverage@N (search-triggering only) | Redundancy@N | Assessment |
|---|---|---|---|
| 5  | ?% | ?% | |
| 8  | ?% | ?% | |
| 10 | ?% | ?% | |
| 12 | ?% | ?% | |
| 15 | ?% | ?% | ← current |
| 20 | ?% | ?% | |

Use in conjunction with Recall@K results: if Recall@3 fails at N=15 but Coverage@15 = 100%, the problem is embedding quality or query-proposition vocabulary mismatch, not count.

---

## How the Two Tests Relate

```
Recall@K fails at N=15
      ↓
Check Coverage@15:
  Coverage < 100%  → proposition count too low; a search-triggering fact is missing
  Coverage = 100%  → count is fine; problem is elsewhere:
                      - vocabulary mismatch between query and proposition phrasing
                      - meta prefix misconfigured
                      - embedding model underperforms on this domain
```

The secondary test diagnoses *why* the primary test fails.

---

## Phased Execution Plan

Not all metrics are meaningful at every KB size. Run in phases as records accumulate.

| Phase | KB size | Run | Metrics available | Metrics not yet meaningful |
|---|---|---|---|---|
| Phase 1 | 1–3 records | Primary test (Recall@K) with existing data | Recall@3, MRR, FPR | Precision@3 (too few records to dilute) |
| Phase 2 | 5–10 records | Re-run full primary test | Recall@3, Precision@3, MRR, FPR | — |
| Phase 3 | 20+ records | Full suite including proposition sweep | All metrics + N sweep meaningful | — |

**Why Precision@3 needs more records:**  
With 3 records total and top-K=3, the system returns all 3 records for any query. Precision = 1/3 = 33% by definition, regardless of retrieval quality. With 10+ records, top-3 becomes a meaningful selection, and Precision measures real signal-to-noise.

**Query set is stable across phases.** Write it once (Step 1), update `relevant_ids` as new records are added.

---

## Resume Value

Measured numbers from Phase 3 eval run (2026-06-06, 14 records, 49 queries):

**Bullet 1 (propositional indexing + retrieval):**
> "Built proposition-indexed Campaign Knowledge Base (Structured Knowledge RAG); achieved **Recall@3 = 81%**, **MRR = 0.77** on a 49-query evaluation set spanning broad, specific, and cross-field retrieval across 14 archived campaigns; specific-concept Recall = 94%, cross-field Recall = 67%; identified primary gap as multi-concept query drift in a growing corpus"

**Bullet 2 (self-verification gate):**
> "Implemented LLM-as-judge self-verification gate that eliminated **false positive rate from 100% → 0%** on out-of-domain queries with zero Recall cost; gate uses matched proposition content for relevance judgment, not metadata labels alone"

**Bullet 3 (eval infrastructure + robustness):**
> "Designed end-to-end RAG evaluation framework: 14-document batch archive pipeline (parse → extract → MongoDB → Pinecone), 49-query stratified evaluation set (broad / specific / cross-field / irrelevant), automated metric computation (Recall@K, Precision@K, MRR, FPR); diagnosed and fixed 3 proposition extraction failure modes (language misclassification, structured output truncation, meta prefix overflow)"

Numbers distinguish "designed a system" from "designed and measured a system."

---

## Related Files

```
backend/core/rag/campaign_index.py              Proposition extraction (with JSON-text fallback)
backend/core/rag/campaign_retriever.py          Retrieval + self-verification gate
backend/core/language/detector.py              CJK-proportion language detector (fixed)
scripts/batch_archive.py                        Phase 1: archive 6 docs (parse→extract→MongoDB→Pinecone)
scripts/batch_archive_phase2.py                 Phase 3: archive 9 additional docs (APPENDS to archived_records.json)
scripts/fix_reindex_record.py                   One-off: patch meta fields + re-index a specific record
scripts/eval_retrieval.py                       Primary eval: Recall@K, Precision@K, MRR, FPR
scripts/eval_proposition_sweep.py               Secondary: N-count sweep (redundancy + coverage)
scripts/eval_generate_ground_truth.py           LLM-assisted ground truth generator
scripts/eval_data/query_set.json                49-query evaluation set (real record IDs)
scripts/eval_data/archived_records.json         14 archived record IDs + metadata
scripts/eval_data/eval_results.json             Primary eval output (RAW + gated results)
scripts/eval_data/anta_ground_truth.json        Ground truth for ANTA record (manual review needed)
scripts/eval_data/proposition_sweep.json        Secondary eval output (N sweep)
```
