export interface StructuredBrief {
  client_name: string | null;
  campaign_theme: string | null;
  target_audience: string | null;
  channels: string[];
  budget_range: string | null;
  timeline: string | null;
  objective: string | null;
  missing_fields: string[];
  clarification_questions: string[];
}

export interface StrategyResult {
  big_idea: string;
  communication_logic: string;
  channel_mix: Record<string, string>;
  budget_allocation: Record<string, number>;
  kpis: string[];
}

export interface SlideContent {
  index: number;
  title: string;
  type: string;
  body: string;
  bullets: string[];
  data: Record<string, unknown> | null;
}

export interface NarrativeSuggestion {
  page: number;
  issue: string;
}

export interface HitlEvent {
  event: "hitl_response";
  node: string;
  action: "confirm" | "revise";
  feedback?: string;
  refresh_research?: boolean;
}
