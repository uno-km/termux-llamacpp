import fs from "node:fs";
import path from "node:path";
import os from "node:os";
import { ModelNotFoundError } from "./exceptions.js";

export interface ModelInfo {
  name: string;
  repoId: string;
  filename: string;
  sizeMb: number;
  quantType: string;
  description: string;
}

export const CURATED_MODELS: Record<string, ModelInfo> = {
  "qwen2.5-0.5b-instruct": {
    name: "qwen2.5-0.5b-instruct",
    repoId: "Qwen/Qwen2.5-0.5B-Instruct-GGUF",
    filename: "qwen2.5-0.5b-instruct-q4_k_m.gguf",
    sizeMb: 398.0,
    quantType: "Q4_K_M",
    description: "Ultra-lightweight Qwen 2.5 0.5B model for mobile devices."
  },
  "qwen2.5-1.5b-instruct": {
    name: "qwen2.5-1.5b-instruct",
    repoId: "Qwen/Qwen2.5-1.5B-Instruct-GGUF",
    filename: "qwen2.5-1.5b-instruct-q4_k_m.gguf",
    sizeMb: 986.0,
    quantType: "Q4_K_M",
    description: "Balanced Qwen 2.5 1.5B model for ARM64 edge inference."
  },
  "qwen2.5-3b-instruct": {
    name: "qwen2.5-3b-instruct",
    repoId: "Qwen/Qwen2.5-3B-Instruct-GGUF",
    filename: "qwen2.5-3b-instruct-q4_k_m.gguf",
    sizeMb: 1930.0,
    quantType: "Q4_K_M",
    description: "High-capability Qwen 2.5 3B model."
  },
  "llama-3.2-1b-instruct": {
    name: "llama-3.2-1b-instruct",
    repoId: "bartowski/Llama-3.2-1B-Instruct-GGUF",
    filename: "Llama-3.2-1B-Instruct-Q4_K_M.gguf",
    sizeMb: 881.0,
    quantType: "Q4_K_M",
    description: "Meta Llama 3.2 1B Instruct model."
  },
  "llama-3.2-3b-instruct": {
    name: "llama-3.2-3b-instruct",
    repoId: "bartowski/Llama-3.2-3B-Instruct-GGUF",
    filename: "Llama-3.2-3B-Instruct-Q4_K_M.gguf",
    sizeMb: 2020.0,
    quantType: "Q4_K_M",
    description: "Meta Llama 3.2 3B Instruct model."
  }
};

export class ModelManager {
  public readonly modelsDir: string;

  constructor(modelsDir?: string) {
    const baseDir = process.env.TERMUX_LLAMA_HOME || path.join(os.homedir(), ".termux-llama");
    this.modelsDir = modelsDir || process.env.TERMUX_LLAMA_MODELS_DIR || path.join(baseDir, "models");
    if (!fs.existsSync(this.modelsDir)) {
      fs.mkdirSync(this.modelsDir, { recursive: true });
    }
  }

  public resolveModelPath(modelIdentifier: string): string {
    // 1. Direct path check
    if (fs.existsSync(modelIdentifier) && modelIdentifier.endsWith(".gguf")) {
      return path.resolve(modelIdentifier);
    }

    // 2. Direct filename in modelsDir
    const candidatePath = path.join(this.modelsDir, modelIdentifier);
    if (fs.existsSync(candidatePath)) {
      return candidatePath;
    }
    const candidateWithExt = path.join(this.modelsDir, `${modelIdentifier}.gguf`);
    if (fs.existsSync(candidateWithExt)) {
      return candidateWithExt;
    }

    // 3. Alias check
    const alias = modelIdentifier.trim().toLowerCase();
    if (CURATED_MODELS[alias]) {
      const target = path.join(this.modelsDir, CURATED_MODELS[alias].filename);
      if (fs.existsSync(target)) {
        return target;
      }
    }

    // 4. Model missing: interrupt with exception
    throw new ModelNotFoundError(modelIdentifier, this.modelsDir);
  }

  public get(modelIdentifier: string): string {
    return this.resolveModelPath(modelIdentifier);
  }

  public async download(options: { repoId?: string; filename?: string; alias?: string; sha256?: string }): Promise<string> {
    let repoId = options.repoId || "";
    let filename = options.filename || "";

    if (options.alias && CURATED_MODELS[options.alias.toLowerCase()]) {
      const item = CURATED_MODELS[options.alias.toLowerCase()];
      repoId = item.repoId;
      filename = item.filename;
    }

    if (!repoId || !filename) {
      throw new Error("Both repoId and filename (or a valid alias) are required.");
    }

    const destination = path.join(this.modelsDir, filename);
    if (fs.existsSync(destination)) {
      console.log(`[termux-llamacpp] Model '${filename}' is already downloaded at ${destination}`);
      return destination;
    }

    const downloadUrl = `https://huggingface.co/${repoId}/resolve/main/${filename}`;
    console.log(`[termux-llamacpp] Downloading ${filename} from ${downloadUrl}...`);

    const response = await fetch(downloadUrl);
    if (!response.ok) {
      throw new Error(`Failed to download model from ${downloadUrl}: ${response.statusText}`);
    }

    const buffer = Buffer.from(await response.arrayBuffer());
    fs.writeFileSync(destination, buffer);
    console.log(`[termux-llamacpp] Model saved to ${destination}`);
    return destination;
  }

  public listLocalModels(): Array<{ filename: string; path: string; sizeMb: number }> {
    if (!fs.existsSync(this.modelsDir)) return [];
    return fs
      .readdirSync(this.modelsDir)
      .filter((file) => file.endsWith(".gguf"))
      .map((file) => {
        const full = path.join(this.modelsDir, file);
        const stat = fs.statSync(full);
        return {
          filename: file,
          path: full,
          sizeMb: Number((stat.size / (1024 * 1024)).toFixed(2))
        };
      });
  }
}
