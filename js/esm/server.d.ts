import http from "node:http";
import { ChildProcess } from "node:child_process";
export interface ServerOptions {
    model: string;
    host?: string;
    port?: number;
    ctxSize?: number;
    threads?: number;
}
export declare class ServerInstance {
    readonly endpoint: string;
    readonly host: string;
    readonly port: number;
    private process?;
    private httpServer?;
    constructor(options: {
        host: string;
        port: number;
        process?: ChildProcess;
        httpServer?: http.Server;
    });
    isHealthy(): Promise<boolean>;
    stop(): void;
}
export declare class ServerManager {
    serve(options: ServerOptions, resolvedModelPath: string): Promise<ServerInstance>;
}
//# sourceMappingURL=server.d.ts.map