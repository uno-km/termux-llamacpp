export class TermuxLlamaError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "TermuxLlamaError";
  }
}

export class ModelNotFoundError extends TermuxLlamaError {
  public readonly modelIdentifier: string;
  public readonly searchPath: string;

  constructor(modelIdentifier: string, searchPath: string = "") {
    const msg =
      `\n================================================================================\n` +
      `[termux-llamacpp] MODEL NOT FOUND: '${modelIdentifier}'\n` +
      `================================================================================\n` +
      `지정된 GGUF 모델을 로컬 디렉터리에서 찾을 수 없습니다.\n` +
      `검색 경로: ${searchPath || "~/.termux-llama/models/"}\n\n` +
      `해결 방법:\n` +
      `  1. 사전 큐레이션 모델 다운로드:\n` +
      `     termux-llama download qwen2.5-1.5b-instruct\n\n` +
      `  2. Hugging Face에서 직접 다운로드:\n` +
      `     termux-llama download <repo_id> <filename>\n\n` +
      `  3. 로컬 모델 목록 확인:\n` +
      `     termux-llama list\n` +
      `================================================================================`;
    super(msg);
    this.name = "ModelNotFoundError";
    this.modelIdentifier = modelIdentifier;
    this.searchPath = searchPath;
  }
}

export class DependencyMissingError extends TermuxLlamaError {
  public readonly packageName: string;
  public readonly reason: string;

  constructor(packageName: string = "termux-playwright", reason: string = "") {
    const msg =
      `\n================================================================================\n` +
      `[termux-llamacpp] DEPENDENCY MISSING: '${packageName}' is not installed!\n` +
      `================================================================================\n` +
      `${reason || "Hugging Face 동적 페이지 렌더링 및 심층 GGUF 파일 크롤링"}을(를) 수행하려면 '${packageName}' 패키지가 필요합니다.\n\n` +
      `다음 명령어를 실행하여 설치를 진행하십시오:\n` +
      `  - Python 환경:  pip install ${packageName}\n` +
      `  - Node.js 환경: npm install ${packageName}\n\n` +
      `참고: 기본 REST API 기반 검색 모드를 사용하려면 deepCrawl: false 로 호출하십시오.\n` +
      `================================================================================`;
    super(msg);
    this.name = "DependencyMissingError";
    this.packageName = packageName;
    this.reason = reason;
  }
}
