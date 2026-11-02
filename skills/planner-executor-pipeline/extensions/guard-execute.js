// EXECUTE: writes inside allowed_paths only, never inside protected_paths.
import { createGuard } from "./guard-core.js";

export default createGuard("EXECUTE", { mode: "handoff-paths" });
