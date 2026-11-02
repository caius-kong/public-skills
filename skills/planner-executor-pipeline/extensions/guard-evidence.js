// EVIDENCE: writes only under the evidence directory; no contract files.
import { createGuard } from "./guard-core.js";

export default createGuard("EVIDENCE", { mode: "fixed-paths", allow: ["handoffs/research"] });
