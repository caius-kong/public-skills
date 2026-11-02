// Loaded only by the direct async PLAN agent; the parent and other child runs keep their own defaults.
const PLAN_INTERVIEW_CHANNEL_TIMEOUT_MS = 86_400_000;

export default function planInterviewChannelTimeout() {
  if (process.env.PI_SUBAGENT_CHILD !== "1") {
    throw new Error("The PLAN interview timeout extension requires a detached async child runner.");
  }

  process.env.PI_INTERCOM_ASK_TIMEOUT_MS = String(PLAN_INTERVIEW_CHANNEL_TIMEOUT_MS);
}
