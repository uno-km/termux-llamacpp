#!/usr/bin/env node

const { spawn } = require("node:child_process");
const path = require("node:path");
const fs = require("node:fs");

const args = process.argv.slice(2);
const isInstall = args[0] === "install";

// Try python module first
const pyCmd = process.platform === "win32" ? "py" : "python3";
const pyArgs = process.platform === "win32" ? ["-3", "-m", "termux_llamacpp.cli", ...args] : ["-m", "termux_llamacpp.cli", ...args];

const child = spawn(pyCmd, pyArgs, { stdio: "inherit" });

child.on("error", () => {
  // If python fails and command is install, run bash install.sh directly
  if (isInstall) {
    const installScript = path.join(__dirname, "..", "scripts", "install.sh");
    if (fs.existsSync(installScript)) {
      const sh = spawn("bash", [installScript, ...args.slice(1)], { stdio: "inherit" });
      sh.on("exit", (code) => process.exit(code || 0));
      return;
    }
  }
  console.error("[Error] termux-llamacpp requires Python 3.9+ or bash in PATH.");
  process.exit(1);
});

child.on("exit", (code) => {
  process.exit(code || 0);
});
