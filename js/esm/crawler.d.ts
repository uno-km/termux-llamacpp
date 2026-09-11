export interface DiscoveredModel {
    repoId: string;
    name: string;
    downloads: number;
    likes: number;
    recommendedFile: string;
    downloadUrl: string;
}
export declare class HuggingFaceCrawler {
    private hfToken?;
    constructor(hfToken?: string);
    isPlaywrightAvailable(): Promise<boolean>;
    discover(options?: {
        query?: string;
        limit?: number;
        deepCrawl?: boolean;
    }): Promise<DiscoveredModel[]>;
}
//# sourceMappingURL=crawler.d.ts.map