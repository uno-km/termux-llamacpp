import { ModelManager } from "./models.js";
import { ServerManager, ServerInstance, ServerOptions } from "./server.js";
import { HuggingFaceCrawler } from "./crawler.js";

export interface RuntimeOptions {
  preset?: string;
  modelsDir?: string;
  binDir?: string;
}

export class LlamaRuntime {
  public readonly models: ModelManager;
  public readonly crawler: HuggingFaceCrawler;
  public readonly serverManager: ServerManager;

  constructor(options: RuntimeOptions = {}) {
    this.models = new ModelManager(options.modelsDir);
    this.crawler = new HuggingFaceCrawler();
    this.serverManager = new ServerManager();
  }

  public static async install(options: RuntimeOptions = {}): Promise<LlamaRuntime> {
    console.log(`[termux-llamacpp] Initializing runtime preset: ${options.preset || "android-arm64"}...`);
    return new LlamaRuntime(options);
  }

  public async serve(options: ServerOptions): Promise<ServerInstance> {
    const resolvedPath = this.models.get(options.model);
    return this.serverManager.serve(options, resolvedPath);
  }
}
