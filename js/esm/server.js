"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.ServerManager = exports.ServerInstance = void 0;
const node_child_process_1 = require("node:child_process");
const node_path_1 = __importDefault(require("node:path"));
class ServerInstance {
    endpoint;
    host;
    port;
    process;
    httpServer;
    constructor(options) {
        this.host = options.host;
        this.port = options.port;
        this.process = options.process;
        this.httpServer = options.httpServer;
        this.endpoint = `http://${this.host}:${this.port}`;
    }
    async isHealthy() {
        try {
            const res = await fetch(`${this.endpoint}/health`);
            return res.status === 200 || res.status === 503;
        }
        catch {
            return false;
        }
    }
    stop() {
        if (this.process) {
            this.process.kill("SIGTERM");
            this.process = undefined;
        }
        if (this.httpServer) {
            this.httpServer.close();
            this.httpServer = undefined;
        }
        console.log(`[termux-llamacpp] Server on ${this.endpoint} stopped.`);
    }
}
exports.ServerInstance = ServerInstance;
class ServerManager {
    async serve(options, resolvedModelPath) {
        const host = options.host || "127.0.0.1";
        const port = options.port || 8080;
        const modelName = node_path_1.default.basename(resolvedModelPath);
        const pyCmd = process.env.PYTHON || "python3";
        console.log("================================================================================");
        console.log(`  [termux-llamacpp] Node.js Native Runtime Bridge`);
        console.log("================================================================================");
        console.log(`  Model Path : ${modelName}`);
        console.log(`  Endpoint   : http://${host}:${port}`);
        console.log("================================================================================");
        const args = [
            "-m",
            "termux_llamacpp",
            "serve",
            resolvedModelPath,
            "--host",
            host,
            "--port",
            port.toString(),
            "--ctx",
            (options.ctxSize || 2048).toString(),
        ];
        if (options.threads) {
            args.push("--threads", options.threads.toString());
        }
        const proc = (0, node_child_process_1.spawn)(pyCmd, args, {
            stdio: ["ignore", "pipe", "pipe"],
            env: process.env,
        });
        const instance = new ServerInstance({ host, port, process: proc });
        const deadline = Date.now() + 30000;
        let ready = false;
        while (Date.now() < deadline) {
            if (await instance.isHealthy()) {
                ready = true;
                break;
            }
            if (proc.exitCode !== null) {
                throw new Error(`Runtime process exited prematurely with code ${proc.exitCode}`);
            }
            await new Promise((r) => setTimeout(r, 500));
        }
        if (!ready) {
            instance.stop();
            throw new Error(`Server failed to become ready on http://${host}:${port} within 30 seconds.`);
        }
        return instance;
    }
}
exports.ServerManager = ServerManager;
//# sourceMappingURL=server.js.map