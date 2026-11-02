// TEST_AUTHOR: writes test assets only, taken from the plan contract's open
// paths, plus its own handoff. Implementation paths stay closed even when the
// contract lists them as allowed (the contract is shared with EXECUTE).
import { createGuard } from "./guard-core.js";

export default createGuard("TEST_AUTHOR", { mode: "test-only" });
