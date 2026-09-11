import { spawn } from "node:child_process";
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
    const pyCmd = process.env.PYTHON || "python3";
    const args = ["-m", "termux_llamacpp", "install"];
    if (options.preset) {
      args.push("--preset", options.preset);
    }
    console.log(`[termux-llamacpp] Executing runtime installation (preset: ${options.preset || "android-arm64-baseline"})...`);

    await new Promise<void>((resolve, reject) => {
      const child = spawn(pyCmd, args, { stdio: "inherit", env: process.env });
      child.on("error", (err) => reject(err));
      child.on("exit", (code) => {
        if (code === 0) resolve();
        else reject(new Error(`Runtime installation failed with exit code ${code}`));
      });
    });

    return new LlamaRuntime(options);
  }

  public async serve(options: ServerOptions): Promise<ServerInstance> {
    const resolvedPath = this.models.get(options.model);
    return this.serverManager.serve(options, resolvedPath);
  }
}
