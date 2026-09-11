"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.HuggingFaceCrawler = void 0;
const exceptions_js_1 = require("./exceptions.js");
class HuggingFaceCrawler {
    hfToken;
    constructor(hfToken) {
        this.hfToken = hfToken || process.env.HF_TOKEN;
    }
    async isPlaywrightAvailable() {
        try {
            await import("termux-playwright");
            return true;
        }
        catch {
            try {
                await import("playwright");
                return true;
            }
            catch {
                return false;
            }
        }
    }
    async discover(options = {}) {
        const query = options.query || "gguf";
        const limit = options.limit || 10;
        const deepCrawl = options.deepCrawl ?? false;
        if (deepCrawl) {
            const available = await this.isPlaywrightAvailable();
            if (!available) {
                throw new exceptions_js_1.DependencyMissingError("termux-playwright", "Hugging Face 동적 페이지 렌더링 및 심층 GGUF 파일 크롤링");
            }
            // If available, perform dynamic crawling
        }
        const url = new URL("https://huggingface.co/api/models");
        url.searchParams.set("search", query);
        url.searchParams.set("filter", "gguf");
        url.searchParams.set("sort", "downloads");
        url.searchParams.set("direction", "-1");
        url.searchParams.set("limit", String(limit));
        const headers = {
            "User-Agent": "termux-llamacpp-js/1.0.0"
        };
        if (this.hfToken) {
            headers["Authorization"] = `Bearer ${this.hfToken}`;
        }
        const response = await fetch(url.toString(), { headers });
        if (!response.ok) {
            throw new Error(`Hugging Face API error: ${response.statusText}`);
        }
        const rawData = (await response.json());
        return rawData.map((item) => {
            const repoId = item.id || "";
            const repoName = repoId.split("/").pop() || repoId;
            const recFile = `${repoName}-Q4_K_M.gguf`;
            return {
                repoId,
                name: repoName,
                downloads: item.downloads || 0,
                likes: item.likes || 0,
                recommendedFile: recFile,
                downloadUrl: `https://huggingface.co/${repoId}/resolve/main/${recFile}`
            };
        });
    }
}
exports.HuggingFaceCrawler = HuggingFaceCrawler;
//# sourceMappingURL=crawler.js.map