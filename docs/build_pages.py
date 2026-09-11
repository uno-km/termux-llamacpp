#!/usr/bin/env python3
"""Official Documentation Site Generator for termux-llamacpp."""

import os
import sys

DOCS_DIR = os.path.dirname(os.path.abspath(__file__))
SITE_URL = "https://uno-km.github.io/termux-llamacpp"
VERSION = "v1.0.0 (Production Ready)"


def get_header(active_page):
    return """    <header>
        <a href="index.html" class="header-brand">
            <img src="favicon.svg" alt="termux-llamacpp Logo">
            <h1 data-i18n="common.brand">termux-llamacpp</h1>
        </a>
        <div class="header-controls">
            <span class="release-tag">v1.0.0 (GGUF Runtime)</span>
            <div class="lang-selector-wrapper">
                <select class="lang-select" onchange="if(window.i18nManager) window.i18nManager.setLanguage(this.value); else if(window.I18n) window.I18n.setLanguage(this.value)">
                    <option value="en">🇺🇸 English</option>
                    <option value="ko">🇰🇷 한국어</option>
                    <option value="ja">🇯🇵 日本語</option>
                    <option value="zh">🇨🇳 简体中文</option>
                    <option value="es">🇪🇸 Español</option>
                    <option value="de">🇩🇪 Deutsch</option>
                </select>
            </div>
            <a href="https://pypi.org/project/termux-llamacpp/" target="_blank" class="header-btn">PyPI (pip)</a>
            <a href="https://github.com/uno-km/termux-llamacpp" target="_blank" class="header-btn primary">GitHub</a>
        </div>
    </header>"""


def get_sidebar(active_page):
    pages = [
        ("index.html", "Home / Architecture"),
        ("installation.html", "Installation Guide"),
        ("quickstart.html", "Quickstart & Recipes"),
        ("models.html", "Curated Model Registry"),
        ("api-reference.html", "Full API Reference"),
        ("benchmarks.html", "Hardware & Benchmarks"),
        ("versions.html", "Version Archive"),
    ]
    html = """        <nav class="sidebar">
            <h3>Overview</h3>
            <ul>"""
    for href, title in pages[:3]:
        active = ' class="active"' if href == active_page else ""
        html += f'\n                <li><a href="{href}"{active}>{title}</a></li>'
    html += """
            </ul>
            <h3>Official Reference</h3>
            <ul>"""
    for href, title in pages[3:]:
        active = ' class="active"' if href == active_page else ""
        html += f'\n                <li><a href="{href}"{active}>{title}</a></li>'
    html += """
            </ul>
            <h3>AI Agent Protocol &amp; Feeds</h3>
            <ul>
                <li><a href="llms.txt" target="_blank">llms.txt (AI Agent Context)</a></li>
                <li><a href="robots.txt" target="_blank">robots.txt</a></li>
                <li><a href="sitemap.xml" target="_blank">sitemap.xml</a></li>
            </ul>
        </nav>"""
    return html


def get_footer():
    return """    <footer>
        <div style="margin-bottom: 8px;">
            <strong>Disclaimer:</strong> termux-llamacpp is an independent open-source project and is not affiliated with or endorsed by Meta Platforms, Inc. or the Termux project.
        </div>
        <span>&copy; 2026 termux-llamacpp Project (uno-km). Released under Apache License 2.0.</span>
    </footer>"""


def get_head_meta(title, description):
    return f"""    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} | termux-llamacpp</title>
    <meta name="description" content="{description}">
    <link rel="icon" type="image/svg+xml" href="favicon.svg">
    <link rel="stylesheet" href="style.css">
    <script src="i18n-translations.js"></script>
    <script src="i18n.js"></script>"""


def build_index():
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
{get_head_meta("Home / Architecture", "Universal GGUF Runtime, Model Manager & OpenAI Server for Android Termux & ARM64")}
</head>
<body>
{get_header('index.html')}
    <div class="container">
{get_sidebar('index.html')}
        <main class="content">
            <section class="hero-panel">
                <div class="badges-bar" style="display: flex; gap: 8px; margin-bottom: 16px;">
                    <span class="release-tag">Protocol: 1.0 (termux-aichain)</span>
                    <span class="release-tag">License: Apache-2.0</span>
                    <span class="release-tag">Commit: b3900</span>
                </div>
                <h2>termux-llamacpp</h2>
                <p class="subtitle">Universal GGUF Runtime, Model Manager &amp; OpenAI Server for Android Termux &amp; ARM64</p>
            </section>

            <section class="challenge-solution-grid" style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin: 20px 0;">
                <div class="card" style="border-left: 4px solid var(--accent-red, #dc3545);">
                    <h3>The Edge LLM Challenge</h3>
                    <p>Cross-compiling native llama.cpp for mobile ARM64 without SIGILL illegal instruction traps and managing GGUF downloads with hash integrity is difficult and error-prone.</p>
                </div>
                <div class="card" style="border-left: 4px solid var(--accent-green, #28a745);">
                    <h3>The termux-llamacpp Solution</h3>
                    <p>Delivers pinned-commit native toolchains, tiered build presets (baseline, dotprod, native), HTTP Range resume caching with sidecar manifests, and PID-locked OpenAI servers.</p>
                </div>
            </section>

            <h3>Canonical Usage Example</h3>
            <pre><code class="language-python">from termux_llamacpp import LlamaRuntime

# 1. Initialize runtime
runtime = LlamaRuntime.install(preset="android-arm64-baseline")

# 2. Download model with SHA256 validation and manifest
model_path = runtime.models.download("qwen2.5-1.5b-instruct")

# 3. Start OpenAI and termux-aichain compliant server
server = runtime.serve(model="qwen2.5-1.5b-instruct", port=8080)
print(f"Server ready at {{server.endpoint}}")</code></pre>
        </main>
    </div>
{get_footer()}
</body>
</html>"""


def build_installation():
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
{get_head_meta("Installation Guide", "Install termux-llamacpp and compile native llama.cpp")}
</head>
<body>
{get_header('installation.html')}
    <div class="container">
{get_sidebar('installation.html')}
        <main class="content">
            <h2>Installation Guide</h2>
            <p class="subtitle">Quick setup across Python, Node.js, and Android Termux.</p>

            <h3>1. Install SDK &amp; CLI via pip</h3>
            <pre><code class="language-bash">pip install termux-llamacpp</code></pre>

            <h3>2. Compile Native ARM64 llama.cpp Runtime</h3>
            <pre><code class="language-bash"># Standard safe baseline (armv8-a)
termux-llama install --preset android-arm64-baseline

# Hardware accelerated (if device supports DotProd)
termux-llama install --preset android-arm64-dotprod</code></pre>

            <h3>3. Diagnostics</h3>
            <pre><code class="language-bash">termux-llama doctor</code></pre>
        </main>
    </div>
{get_footer()}
</body>
</html>"""


def build_quickstart():
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
{get_head_meta("Quickstart & Recipes", "Quick recipes for termux-llamacpp and termux-aichain")}
</head>
<body>
{get_header('quickstart.html')}
    <div class="container">
{get_sidebar('quickstart.html')}
        <main class="content">
            <h2>Quickstart &amp; Recipes</h2>
            <p class="subtitle">Serve models locally and connect seamlessly with termux-aichain.</p>

            <h3>Recipe 1: Start OpenAI Server via CLI</h3>
            <pre><code class="language-bash">termux-llama download qwen2.5-1.5b-instruct
termux-llama serve qwen2.5-1.5b-instruct --port 8080</code></pre>

            <h3>Recipe 2: Connect from termux-aichain</h3>
            <pre><code class="language-python">from termux_aichain import LocalAgent

agent = LocalAgent.create(
    mode="connect",
    endpoint="http://127.0.0.1:8080"
)

reply = agent.run("Analyze system hardware.")
print(reply)</code></pre>
        </main>
    </div>
{get_footer()}
</body>
</html>"""


def main():
    pages = {
        "index.html": build_index(),
        "installation.html": build_installation(),
        "quickstart.html": build_quickstart(),
    }
    for filename, html in pages.items():
        out_path = os.path.join(DOCS_DIR, filename)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"Generated: {out_path}")
    print("\nDocumentation pages generated successfully!")


if __name__ == "__main__":
    main()
