import http from "node:http";
import { ChildProcess, spawn } from "node:child_process";
import path from "node:path";

export interface ServerOptions {
  model: string;
  host?: string;
  port?: number;
  ctxSize?: number;
  threads?: number;
}

export class ServerInstance {
  public readonly endpoint: string;
  public readonly host: string;
  public readonly port: number;
  private process?: ChildProcess;
  private httpServer?: http.Server;

  constructor(options: { host: string; port: number; process?: ChildProcess; httpServer?: http.Server }) {
    this.host = options.host;
    this.port = options.port;
    this.process = options.process;
    this.httpServer = options.httpServer;
    this.endpoint = `http://${this.host}:${this.port}`;
  }

  public async isHealthy(): Promise<boolean> {
    try {
      const res = await fetch(`${this.endpoint}/health`);
      return res.status === 200 || res.status === 503;
    } catch {
      return false;
    }
  }

  public stop(): void {
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

export class ServerManager {
  public async serve(options: ServerOptions, resolvedModelPath: string): Promise<ServerInstance> {
    const host = options.host || "127.0.0.1";
    const port = options.port || 8080;
    const modelName = path.basename(resolvedModelPath);
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

    const proc = spawn(pyCmd, args, {
      stdio: ["ignore", "pipe", "pipe"],
      env: process.env,
    });

    const instance = new ServerInstance({ host, port, process: proc });

    // Wait up to 30s for server readiness
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
