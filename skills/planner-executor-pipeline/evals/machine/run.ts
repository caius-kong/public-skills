#!/usr/bin/env node
// run CLI：父会话调用机器的唯一入口（确定性，不手模拟状态）。
//   node run.ts init                     → fresh state + 打印 PLAN dispatch
//   node run.ts event < event.json       → 应用事件 + 持久化 + 打印 {dispatch|gateChecklist|error}
//   node run.ts show                     → 打印当前状态
// 状态文件默认 ./state.json（gitignored）；可用 --state <path> 覆盖。
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { boot, step, type Event, type MachineState } from "./machine.ts";

const argv = process.argv.slice(2);
const stateFlagIdx = argv.indexOf("--state");
const statePath = stateFlagIdx >= 0 ? argv[stateFlagIdx + 1] : new URL("./state.json", import.meta.url).pathname;
const cmd = argv[0];

function load(): MachineState {
  if (!existsSync(statePath)) throw new Error(`state 文件不存在：${statePath}（先跑 init）`);
  return JSON.parse(readFileSync(statePath, "utf8")) as MachineState;
}

function save(s: MachineState): void {
  writeFileSync(statePath, JSON.stringify(s, null, 2));
}

if (cmd === "init") {
  const r = boot();
  save(r.state);
  console.log(JSON.stringify({ dispatch: r.dispatch }, null, 2));
} else if (cmd === "event") {
  const raw = readFileSync(0, "utf8");
  const event = JSON.parse(raw) as Event;
  const r = step(load(), event);
  save(r.state);
  console.log(JSON.stringify(r, null, 2));
  if (r.error) process.exitCode = 2;
} else if (cmd === "show") {
  console.log(JSON.stringify(load(), null, 2));
} else {
  console.error("usage: node run.ts init | event < event.json | show [--state path]");
  process.exitCode = 1;
}
