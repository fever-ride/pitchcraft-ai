BRIEF_ANALYZER_PROMPTS = {
    "zh": """你是一位资深的公关营销策略师。请分析以下客户brief，提取结构化信息。

Brief内容：
{brief}

请提取以下字段（如果brief中没有提到，标记为"未提供"）：
- 品牌/客户名称
- Campaign主题或方向
- 目标受众
- 传播渠道
- 预算范围
- 时间节点
- Campaign目标

同时列出需要客户补充的信息。""",

    "en": """You are a senior PR and marketing strategist. Analyze the following client brief and extract structured information.

Brief:
{brief}

Extract the following fields (mark as "not provided" if missing):
- Brand / client name
- Campaign theme or direction
- Target audience
- Channels
- Budget range
- Timeline
- Campaign objective

Also list any information that needs clarification from the client.""",
}


STRATEGY_PHASE1_PROMPTS = {
    "zh": """基于以下brief和品牌资料，生成受众洞察和品牌方向建议。

Brief：{brief}
品牌资料：{brand_context}

输出严格JSON格式：
{{
  "audience_insight": "目标人群的核心insight",
  "audience_segments": ["细分人群1", "细分人群2"],
  "brand_direction": "基于品牌资产的初步策略方向",
  "emotional_hook": "情感切入点",
  "competitive_angle": "差异化方向"
}}""",

    "en": """Based on the following brief and brand materials, generate audience insights and brand direction recommendations.

Brief: {brief}
Brand context: {brand_context}

Output strictly in JSON format:
{{
  "audience_insight": "core insight about the target segment",
  "audience_segments": ["segment 1", "segment 2"],
  "brand_direction": "initial strategic angle based on brand assets",
  "emotional_hook": "emotional entry point",
  "competitive_angle": "differentiation angle"
}}""",
}


STRATEGY_PHASE2_PROMPTS = {
    "zh": """基于以下洞察和竞品调研，生成完整的campaign策略框架。

受众洞察：{insight}
竞品调研：{research}
Brief：{brief}

输出严格JSON格式：
{{
  "big_idea": "Campaign主题 / Big Idea（一句话）",
  "communication_logic": "传播逻辑描述",
  "channels": [
    {{"name": "渠道名", "role": "该渠道在campaign中的角色", "priority": "high/medium/low"}}
  ],
  "resource_types": ["kol", "koc", "media", "event"],
  "budget_allocation": {{
    "渠道名": "百分比或金额"
  }},
  "kpis": [
    {{"metric": "指标名", "target": "目标值"}}
  ],
  "timeline_phases": [
    {{"phase": "阶段名", "duration": "时长", "focus": "重点"}}
  ]
}}""",

    "en": """Based on the following insights and competitor research, generate a complete campaign strategy framework.

Audience insight: {insight}
Competitor research: {research}
Brief: {brief}

Output strictly in JSON format:
{{
  "big_idea": "Campaign theme / Big Idea (one sentence)",
  "communication_logic": "communication flow description",
  "channels": [
    {{"name": "channel name", "role": "role in campaign", "priority": "high/medium/low"}}
  ],
  "resource_types": ["kol", "koc", "media", "event"],
  "budget_allocation": {{
    "channel_name": "percentage or amount"
  }},
  "kpis": [
    {{"metric": "metric name", "target": "target value"}}
  ],
  "timeline_phases": [
    {{"phase": "phase name", "duration": "duration", "focus": "focus area"}}
  ]
}}""",
}
