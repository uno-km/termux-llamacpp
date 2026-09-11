export interface ModelInfo {
    name: string;
    repoId: string;
    filename: string;
    sizeMb: number;
    quantType: string;
    description: string;
}
export declare const CURATED_MODELS: Record<string, ModelInfo>;
export declare class ModelManager {
    readonly modelsDir: string;
    constructor(modelsDir?: string);
    resolveModelPath(modelIdentifier: string): string;
    get(modelIdentifier: string): string;
    download(options: {
        repoId?: string;
        filename?: string;
        alias?: string;
        sha256?: string;
    }): Promise<string>;
    listLocalModels(): Array<{
        filename: string;
        path: string;
        sizeMb: number;
    }>;
}
//# sourceMappingURL=models.d.ts.map