/**
 * termux-llamacpp - JavaScript / TypeScript API Bridge
 */
const { spawn } = require('child_process');

module.exports = {
  packageName: 'termux-llamacpp',
  moduleName: 'termux_llamacpp',
  runCli: function(args = []) {
    const pythonBin = process.env.PYTHON || 'python3';
    return spawn(pythonBin, ['-m', 'termux_llamacpp', ...args], {
      stdio: 'inherit',
      env: process.env
    });
  }
};
