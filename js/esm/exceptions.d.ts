export declare class TermuxLlamaError extends Error {
    constructor(message: string);
}
export declare class ModelNotFoundError extends TermuxLlamaError {
    readonly modelIdentifier: string;
    readonly searchPath: string;
    constructor(modelIdentifier: string, searchPath?: string);
}
export declare class DependencyMissingError extends TermuxLlamaError {
    readonly packageName: string;
    readonly reason: string;
    constructor(packageName?: string, reason?: string);
}
//# sourceMappingURL=exceptions.d.ts.map