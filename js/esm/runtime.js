"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.LlamaRuntime = void 0;
const node_child_process_1 = require("node:child_process");
const models_js_1 = require("./models.js");
const server_js_1 = require("./server.js");
const crawler_js_1 = require("./crawler.js");
class LlamaRuntime {
    models;
    crawler;
    serverManager;
    constructor(options = {}) {
        this.models = new models_js_1.ModelManager(options.modelsDir);
        this.crawler = new crawler_js_1.HuggingFaceCrawler();
        this.serverManager = new server_js_1.ServerManager();
    }
    static async install(options = {}) {
        const pyCmd = process.env.PYTHON || "python3";
        const args = ["-m", "termux_llamacpp", "install"];
        if (options.preset) {
            args.push("--preset", options.preset);
        }
        console.log(`[termux-llamacpp] Executing runtime installation (preset: ${options.preset || "android-arm64-baseline"})...`);
        await new Promise((resolve, reject) => {
            const child = (0, node_child_process_1.spawn)(pyCmd, args, { stdio: "inherit", env: process.env });
            child.on("error", (err) => reject(err));
            child.on("exit", (code) => {
                if (code === 0)
                    resolve();
                else
                    reject(new Error(`Runtime installation failed with exit code ${code}`));
            });
        });
        return new LlamaRuntime(options);
    }
    async serve(options) {
        const resolvedPath = this.models.get(options.model);
        return this.serverManager.serve(options, resolvedPath);
    }
}
exports.LlamaRuntime = LlamaRuntime;
//# sourceMappingURL=runtime.js.map