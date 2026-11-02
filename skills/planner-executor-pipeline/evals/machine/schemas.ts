import { z } from "zod";

// ---- Handoff schemas（zod 是 handoff 契约的唯一权威）----

export const TicketSchema = z.object({
  id: z.string().min(1),
  title: z.string().min(1),
  acceptance: z.array(z.string().min(1)).min(1),
  depends_on: z.array(z.string()).default([]),
  files: z.array(z.string()).min(1),
});

export const PlanHandoffSchema = z.object({
  spec: z.string().min(1),
  tickets: z.array(TicketSchema).min(1),
  dag: z.string().default(""),
  allowed_paths: z.array(z.string()).min(1),
  protected_paths: z.array(z.string()).default([]),
  test_command: z.string().min(1),
  ambiguities: z.array(z.string()).default([]),
});

export const TestHandoffSchema = z.object({
  commit: z.string().min(7),
  test_files: z.array(z.string()).min(1),
  red_summary: z.string().min(1),
  green_baseline: z.string().min(1),
  manifest_sha256: z.string().min(1),
});

export const ExecuteHandoffSchema = z.object({
  ticket: z.string().min(1),
  commit: z.string().min(7),
  test_output_summary: z.string().min(1),
  attempts: z.number().int().min(0),
  open_issues: z.array(z.string()),
});

export const GateEvidenceSchema = z.object({
  BASE_SHA: z.string().min(7),
  INTEGRATION_HEAD: z.string().min(7),
  test_command: z.string().min(1),
  test_exit_code: z.number(),
  cumulative_diff_files: z.array(z.string()),
  allowed_paths_violation: z.boolean(),
  protected_paths_violation: z.boolean(),
});

export const VerdictSchema = z.object({
  verdict: z.enum(["PASS", "FIX_EXECUTE", "REPLAN"]),
  reasons: z.array(z.string()),
  findings: z.array(z.string()),
});

export type Ticket = z.infer<typeof TicketSchema>;
export type PlanHandoff = z.infer<typeof PlanHandoffSchema>;
export type TestHandoff = z.infer<typeof TestHandoffSchema>;
export type ExecuteHandoff = z.infer<typeof ExecuteHandoffSchema>;
export type GateEvidence = z.infer<typeof GateEvidenceSchema>;
export type Verdict = z.infer<typeof VerdictSchema>;
