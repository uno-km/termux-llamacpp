#!/usr/bin/env node

const { spawn } = require("node:child_process");

// Delegate CLI command to Python termux-llama or native runner
const child = spawn("python", ["-m", "termux_llamacpp.cli", ...process.argv.slice(2)], {
  stdio: "inherit"
});

child.on("exit", (code) => {
  process.exit(code || 0);
});
