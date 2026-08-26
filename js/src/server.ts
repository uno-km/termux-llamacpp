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

    console.log("================================================================================");
    console.log(`  [termux-llamacpp] Node.js OpenAI-Compatible Server`);
    console.log("================================================================================");
    console.log(`  Model Path : ${modelName}`);
    console.log(`  Endpoint   : http://${host}:${port}`);
    console.log("================================================================================");

    // Fallback Node HTTP Server
    const server = http.createServer(async (req, res) => {
      res.setHeader("Access-Control-Allow-Origin", "*");
      res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
      res.setHeader("Access-Control-Allow-Headers", "Content-Type, Authorization");

      if (req.method === "OPTIONS") {
        res.writeHead(204);
        res.end();
        return;
      }

      if (req.method === "GET" && req.url === "/health") {
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ status: "ok", service: "termux-llamacpp-js" }));
        return;
      }

      if (req.method === "GET" && (req.url === "/v1/models" || req.url === "/models")) {
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(
          JSON.stringify({
            object: "list",
            data: [{ id: modelName, object: "model", created: Math.floor(Date.now() / 1000), owned_by: "uno-km" }]
          })
        );
        return;
      }

      if (req.method === "POST" && (req.url === "/v1/chat/completions" || req.url === "/chat/completions")) {
        let body = "";
        req.on("data", (chunk) => (body += chunk));
        req.on("end", () => {
          try {
            const data = JSON.parse(body || "{}");
            const messages = data.messages || [];
            const userMsg = messages.filter((m: any) => m.role === "user").pop()?.content || "";
            const reply = `[termux-llamacpp-js] Reply to: "${userMsg.slice(0, 40)}"`;

            const respObj = {
              id: `chatcmpl-${Math.random().toString(36).slice(2, 11)}`,
              object: "chat.completion",
              created: Math.floor(Date.now() / 1000),
              model: modelName,
              choices: [
                {
                  index: 0,
                  message: { role: "assistant", content: reply },
                  finish_reason: "stop"
                }
              ]
            };
            res.writeHead(200, { "Content-Type": "application/json" });
            res.end(JSON.stringify(respObj));
          } catch {
            res.writeHead(400, { "Content-Type": "application/json" });
            res.end(JSON.stringify({ error: "Invalid JSON" }));
          }
        });
        return;
      }

      res.writeHead(404, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: "Not Found" }));
    });

    await new Promise<void>((resolve) => {
      server.listen(port, host, () => {
        resolve();
      });
    });

    return new ServerInstance({ host, port, httpServer: server });
  }
}
