// Shared API types — mirror the backend Pydantic schemas.

export interface Project {
  id: number;
  name: string;
  description: string;
  created_at: string;
  updated_at: string;
}

export type RequirementStatus = 'parsed' | 'confirmed' | 'archived';
export type AssetSource = 'ai' | 'manual';

export interface Requirement {
  id: number;
  project_id: number;
  title: string;
  description: string;
  acceptance_criteria: string[];
  risks: string[];
  gaps: string[];
  ambiguities: string[];
  status: RequirementStatus;
  source: AssetSource;
  doc_ref: string | null;
  created_at: string;
  updated_at: string;
}

export type TestCasePriority = 'P0' | 'P1' | 'P2' | 'P3';
export type TestCaseType =
  | 'smoke'
  | 'functional'
  | 'boundary'
  | 'exception'
  | 'performance'
  | 'security'
  | 'compatibility';
export type TestCaseStatus =
  | 'draft'
  | 'pending_review'
  | 'approved'
  | 'needs_work'
  | 'executed'
  | 'archived';

export interface TestCaseStep {
  id?: number;
  step_number: number;
  action: string;
  expected_result: string;
}

export interface TestCase {
  id: number;
  project_id: number;
  requirement_id: number | null;
  test_point_id: number | null;
  case_id: string;
  title: string;
  priority: TestCasePriority;
  type: TestCaseType;
  precondition: string;
  test_data: Record<string, unknown>;
  expected_result: string;
  status: TestCaseStatus;
  source: AssetSource;
  steps: TestCaseStep[];
  created_at: string;
  updated_at: string;
}

export type TestPointStatus = 'extracted' | 'confirmed' | 'archived';
export type TestPointTechnique =
  | 'equivalence'
  | 'boundary'
  | 'state_transition'
  | 'exception'
  | 'error_guessing';

export interface TestPoint {
  id: number;
  requirement_id: number;
  title: string;
  technique: TestPointTechnique;
  description: string;
  status: TestPointStatus;
  created_at: string;
  updated_at: string;
}

export interface TestPointCreate {
  title: string;
  technique?: TestPointTechnique;
  description?: string;
  status?: TestPointStatus;
}

export interface AnalyzeRequirementResponse {
  status: 'success' | 'partial' | 'failed';
  requirements: Requirement[];
  warnings: string[];
}

export interface ExtractTestPointsResponse {
  status: 'success' | 'partial' | 'failed';
  test_points: TestPoint[];
  warnings: string[];
}

export interface AIAuditLog {
  id: number;
  agent_name: string;
  schema_version: number;
  input_hash: string;
  input_summary: string;
  output_summary: string;
  tokens_in: number;
  tokens_out: number;
  latency_ms: number;
  status: string;
  created_at: string;
}

export interface GenerateTestCasesResponse {
  run_id: number;
  status: string;
  total: number;
}

export interface GenerationRun {
  id: number;
  project_id: number;
  status: string;
  total_items: number;
  processed_items: number;
  created_count: number;
  warnings: string[];
  failed_items: Array<{ test_point_id?: number; reason?: string; error_code?: string }>;
  started_at: string | null;
  ended_at: string | null;
  created_at: string;
  updated_at: string;
}

export type ReviewVerdict = 'approved' | 'needs_work';
export type ReviewerType = 'ai' | 'human';

export interface TestCaseReview {
  id: number;
  test_case_id: number;
  reviewer_type: ReviewerType;
  verdict: ReviewVerdict;
  scores: { completeness: number; accuracy: number; executability: number } | null;
  issues: string[];
  missing_scenarios: string[];
  suggestions: string[];
  created_at: string;
  updated_at: string;
}

export interface UncoveredTestPoint {
  id: number;
  requirement_id: number;
  requirement_title: string;
  title: string;
  technique: string;
  status: string;
}

export interface ReviewTestCasesResponse {
  reviewed: number;
  failed: Array<{ test_case_id?: number; reason?: string; error_code?: string }>;
  warnings: string[];
}

export type QaMode = 'none' | 'selector-change' | 'logic-bug' | 'slow-network' | 'auth-break';

export interface RunConfig {
  base_url: string;
  qa_mode: QaMode;
  browser: string;
  headless: boolean;
}

export interface TestStepResult {
  id: number;
  run_case_id: number;
  step_number: number;
  description: string;
  status: string;
  message: string;
  duration_ms: number;
  screenshot_ref: string | null;
  element_found: boolean;
}

export interface TestRunCase {
  id: number;
  run_id: number;
  test_case_id: number | null;
  kind?: 'ui' | 'api';
  api_case_id?: number | null;
  case_label: string;
  status: string;
  duration_ms: number;
  error: string;
  evidence_ids: unknown[];
  script_path: string;
  created_at: string;
  updated_at: string;
  step_results?: TestStepResult[];
  failure_analysis?: FailureAnalysis | null;
}

export interface TestRun {
  id: number;
  project_id: number;
  name: string;
  status: string;
  config: RunConfig;
  started_at: string | null;
  ended_at: string | null;
  created_at: string;
  updated_at: string;
  total_count: number;
  passed_count: number;
  failed_count: number;
  running_count: number;
  cases?: TestRunCase[];
}

export interface RunCreateResponse {
  run_id: number;
  status: string;
  total: number;
}

// --- Phase 6: execution evidence ---

export type EvidenceKind = 'screenshot' | 'trace' | 'console' | 'network' | 'log';

export interface Evidence {
  id: number;
  run_id: number;
  run_case_id: number | null;
  kind: EvidenceKind;
  file_path: string;
  meta: Record<string, unknown>;
  created_at: string;
}

export interface ConsoleEntry {
  type: string;
  text: string;
  timestamp: number;
}

export interface NetworkEntry {
  url: string;
  method: string;
  status: number;
  resource_type: string;
  duration_ms: number;
}

export interface TraceAction {
  api_name: string;
  error: string | null;
  start_time: number | null;
  end_time: number | null;
  duration_ms: number | null;
}

export interface TraceNetwork {
  url: string;
  method: string;
  status: number | null;
  resource_type: string;
  duration_ms: number | null;
}

export interface TraceConsole {
  type: string;
  text: string;
}

export interface TraceParse {
  id: number;
  evidence_id: number;
  actions: TraceAction[];
  network: TraceNetwork[];
  console: TraceConsole[];
  snapshots: string[];
  created_at: string;
}

// --- Phase 7: failure analysis ---

export type FailureCategory = 'BROKEN_LOCATOR' | 'REAL_BUG' | 'FLAKY' | 'ENV_ISSUE';
export type DecisionSource = 'rule' | 'llm';

export interface FailureAnalysis {
  id: number;
  run_case_id: number;
  category: FailureCategory;
  confidence: number;
  reason: string;
  suggested_fix: string;
  decision_source: DecisionSource;
  needs_human: boolean;
  status: 'pending' | 'classified' | 'confirmed';
  created_at: string;
  updated_at: string;
}

// --- Phase 8: test report + quality summary ---

export type Recommendation = 'GO' | 'CONDITIONAL_GO' | 'NO_GO';

export interface QualitySummary {
  id: number;
  report_id: number;
  overall_score: number;
  pass_rate: number;
  risk_factors: string[];
  recommendation: Recommendation;
  reasoning: string;
  created_at: string;
  updated_at: string;
}

export interface ReportSummary {
  run_id: number;
  run_name: string;
  run_status: string;
  total: number;
  passed: number;
  failed: number;
  blocked: number;
  skipped: number;
  pass_rate: number;
  duration_ms: number;
}

export interface ReportCase {
  case_label: string;
  status: string;
  duration_ms: number;
  error: string;
  priority: string | null;
  failure_analysis: {
    category: FailureCategory;
    confidence: number;
    reason: string;
    suggested_fix: string;
    decision_source: DecisionSource;
    needs_human: boolean;
    status: string;
  } | null;
}

export interface ReportStats {
  run_id: number;
  run_name: string;
  run_status: string;
  overview: ReportSummary;
  priority: Record<string, { total: number; passed: number; failed: number; pass_rate: number }>;
  failure_categories: Record<string, number>;
  cases: ReportCase[];
}

export interface TestReport {
  id: number;
  run_id: number;
  html_path: string;
  json_path: string;
  summary: ReportSummary;
  created_at: string;
  updated_at: string;
  quality_summary?: QualitySummary | null;
  stats?: ReportStats;
}

export interface ReportListItem {
  id: number;
  run_id: number;
  summary: ReportSummary;
  created_at: string;
  updated_at: string;
  recommendation: Recommendation | null;
}

export interface ProjectCreate {
  name: string;
  description?: string;
}

export interface RequirementCreate {
  title: string;
  description?: string;
  acceptance_criteria?: string[];
  risks?: string[];
  gaps?: string[];
  ambiguities?: string[];
  status?: RequirementStatus;
  source?: AssetSource;
  doc_ref?: string | null;
}

export interface TestCaseStepCreate {
  step_number: number;
  action: string;
  expected_result?: string;
}

export interface TestCaseCreate {
  title: string;
  case_id?: string | null;
  priority?: TestCasePriority;
  type?: TestCaseType;
  precondition?: string;
  test_data?: Record<string, unknown>;
  expected_result?: string;
  status?: TestCaseStatus;
  source?: AssetSource;
  requirement_id?: number | null;
  steps?: TestCaseStepCreate[];
}

// --- Phase 9: API test cases ---

export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
export type AssertionType = 'status' | 'json_field' | 'response_time' | 'header';

export interface ApiAssertion {
  type: AssertionType;
  expected?: unknown;
  path?: string | null;
  expected_ms?: number | null;
  name?: string | null;
}

export interface ApiTestCase {
  id: number;
  project_id: number;
  requirement_id: number | null;
  name: string;
  method: HttpMethod;
  url: string;
  headers: Record<string, string>;
  body: Record<string, unknown> | null;
  assertions: ApiAssertion[];
  status: 'active' | 'archived';
  created_at: string;
  updated_at: string;
}
