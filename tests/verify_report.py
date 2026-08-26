import re
import hashlib
from pathlib import Path

report_path = Path("termux-llamacpp-full-source-and-report.md")
content = report_path.read_text(encoding="utf-8")

# Extract fenced code blocks
code_blocks = re.findall(r"```(?:toml|python|bash|json)?\n(.*?)```", content, re.DOTALL)
assert len(code_blocks) > 0, "No code blocks found in report"

REPORT_FORBIDDEN = [
    "&gt;",
    "&lt;",
    "&quot;",
    "&amp;",
    "&#",
    "<a href=",
    "</span>",
    "</div>",
]

for idx, block in enumerate(code_blocks):
    for token in REPORT_FORBIDDEN:
        if token in block:
            raise AssertionError(f"Forbidden token '{token}' detected in code block #{idx+1}!\nSnippet:\n{block[:200]}")

print("Master report code blocks validated: 100% pure raw code, zero HTML entity corruption!")

# Compute and print report hash
hasher = hashlib.sha256()
hasher.update(content.encode("utf-8"))
report_hash = hasher.hexdigest().upper()
print(f"Report SHA-256: {report_hash}")
