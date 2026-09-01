#!/usr/bin/env node

/**
 * termux-llamacpp CLI Entrypoint for Node.js / npm
 * Bridges command line arguments to Python termux_llamacpp or native runtime.
 */

import { spawn } from 'child_process';

const args = process.argv.slice(2);

function runPythonCLI() {
  const pyCmd = process.env.PYTHON || 'python3';
  const child = spawn(pyCmd, ['-m', 'termux_llamacpp', ...args], {
    stdio: 'inherit',
    env: process.env,
  });

  child.on('error', (err) => {
    if (err.code === 'ENOENT') {
      console.error('[termux-llama error] python3 is required to run the termux-llama runtime.');
      console.error('Please install python in Termux: pkg install python');
    } else {
      console.error(`[termux-llama error] Execution failed: ${err.message}`);
    }
    process.exit(1);
  });

  child.on('exit', (code) => {
    process.exit(code || 0);
  });
}

runPythonCLI();