"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.LlamaRuntime = void 0;
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
        console.log(`[termux-llamacpp] Initializing runtime preset: ${options.preset || "android-arm64"}...`);
        return new LlamaRuntime(options);
    }
    async serve(options) {
        const resolvedPath = this.models.get(options.model);
        return this.serverManager.serve(options, resolvedPath);
    }
}
exports.LlamaRuntime = LlamaRuntime;
//# sourceMappingURL=runtime.js.map