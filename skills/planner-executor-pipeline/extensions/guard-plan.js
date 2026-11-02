// PLAN: read-only. bash is limited to plan-mode's read-only allowlist.
import { createGuard } from "./guard-core.js";

export default createGuard("PLAN", { mode: "read-only" });
