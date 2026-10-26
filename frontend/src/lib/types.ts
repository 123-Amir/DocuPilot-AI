export type Severity = "high" | "medium" | "low" | "info";
export type CaseStatus = "needs_review" | "no_mismatch" | "failed";
export type ReviewStatus =
  | "pending_review"
  | "in_review"
  | "reviewed_ok"
  | "needs_vendor_contact"
  | "rejected";
export type ExtractionMode = "model" | "fixture" | "unavailable";

export interface FieldEvidence {
  field: string;
  snippet: string | null;
  page: number | null;
  source: "invoice_text" | "invoice_image" | "po_record" | "computed";
}

export interface LineItem {
  description: string;
  sku: string | null;
  quantity: string | null;
  unit_price: string | null;
  line_total: string | null;
  line_total_source: "extracted" | "computed" | null;
  evidence: FieldEvidence | null;
}

export interface ExtractedInvoice {
  vendor_name: string | null;
  invoice_number: string | null;
  invoice_date: string | null;
  currency: string | null;
  po_number: string | null;
  subtotal: string | null;
  tax_amount: string | null;
  total_amount: string | null;
  line_items: LineItem[];
  evidence: FieldEvidence[];
}

export interface PurchaseOrderLine {
  sku: string | null;
  description: string;
  quantity: string;
  unit_price: string;
  line_total: string;
}

export interface PurchaseOrder {
  po_number: string;
  vendor_name: string;
  issue_date: string;
  currency: string;
  total_amount: string;
  line_items: PurchaseOrderLine[];
}

export interface Flag {
  id: string;
  code: string;
  severity: Severity;
  title: string;
  field: string | null;
  invoice_value: string | null;
  po_value: string | null;
  delta: string | null;
  rule: string;
  detail: string;
  evidence: FieldEvidence[];
}

export interface Check {
  name: string;
  status: "pass" | "fail" | "info";
  detail: string;
}

export interface MatchResult {
  purchase_order: PurchaseOrder | null;
  po_match_method: "po_number" | "vendor" | "none";
  flags: Flag[];
  checks: Check[];
  computed_line_sum: string | null;
  printed_total: string | null;
  arithmetic_delta: string | null;
  vendor_similarity: number | null;
}

export interface Review {
  status: ReviewStatus;
  note: string | null;
  reviewer: string | null;
  updated_at: string | null;
}

export interface ModelInfo {
  provider: string;
  model: string | null;
  mode: ExtractionMode;
  elapsed_ms: number | null;
  note: string | null;
}

export interface CaseSummary {
  id: string;
  created_at: string;
  filename: string;
  status: CaseStatus;
  source: "demo" | "upload";
  vendor_name: string | null;
  invoice_number: string | null;
  invoice_date: string | null;
  currency: string | null;
  total_amount: string | null;
  po_number: string | null;
  flag_count: number;
  high_flag_count: number;
  review_status: ReviewStatus;
  extraction_mode: ExtractionMode;
  error: string | null;
}

export interface CaseDetail extends CaseSummary {
  invoice: ExtractedInvoice | null;
  purchase_order: PurchaseOrder | null;
  match: MatchResult | null;
  review: Review;
  model: ModelInfo;
  document_url: string | null;
  chat_message_count: number;
}

export interface ChatMessage {
  id: string;
  case_id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
  citations: string[];
  follow_ups: string[];
  source: string | null;
}

export interface ChatResponse {
  message: ChatMessage;
  citations: string[];
  follow_ups: string[];
  source: string;
}

export interface AlanInvestigation {
  execution_id: string;
  case_id: string | null;
  workflow_id: string;
  status: string;
  question: string;
  output: string | null;
  error: string | null;
  started_at: string;
  updated_at: string;
  url: string | null;
  polls: number;
}

export interface Health {
  status: string;
  version: string;
  model_configured: boolean;
  model_name: string;
  alan_workflow_configured: boolean;
  alan_missing: string[];
  demo_mode: boolean;
  warning: string;
}

export interface FlagCount {
  code: string;
  label: string;
  count: number;
}

export interface DashboardStats {
  total_documents: number;
  needs_review: number;
  no_mismatch: number;
  failed: number;
  high_flags: number;
  reviewed: number;
  model_configured: boolean;
  alan_workflow_configured: boolean;
}

export interface Dashboard {
  stats: DashboardStats;
  flag_counts: FlagCount[];
  recent: CaseSummary[];
}