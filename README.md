<div align="center">

```
   █████╗ ███████╗████████╗███╗   ███╗██╗███████╗███████╗
  ██╔══██╗██╔════╝╚══██╔══╝████╗ ████║██║╚══███╔╝██╔════╝
  ███████║███████╗   ██║   ██╔████╔██║██║  ███╔╝ █████╗  
  ██╔══██║╚════██║   ██║   ██║╚██╔╝██║██║ ███╔╝  ██╔══╝  
  ██║  ██║███████║   ██║   ██║ ╚═╝ ██║██║███████╗███████╗
  ╚═╝  ╚═╝╚══════╝   ╚═╝   ╚═╝     ╚═╝╚═╝╚══════╝╚══════╝
```

### Python → C++ — AI-Powered Transpiler

[![Live Demo](https://img.shields.io/badge/🌐_Live_Demo-Visit_Now-00e5ff?style=for-the-badge&labelColor=07080c)](https://thespacetimedebugger.github.io/Astmize/)
[![Product Hunt](https://img.shields.io/badge/Product_Hunt-Astmize-ff6154?style=for-the-badge&logo=producthunt&logoColor=white&labelColor=07080c)](https://www.producthunt.com/products/astmize-python-c-transpiler)
[![API](https://img.shields.io/badge/API-v2.1.0-9b6dff?style=flat-square&labelColor=07080c)](https://astmize.onrender.com)
[![License](https://img.shields.io/badge/License-MIT-00ff88?style=flat-square&labelColor=07080c)](LICENSE)
[![Flask](https://img.shields.io/badge/Backend-Flask-lightgrey?style=flat-square&logo=flask&labelColor=07080c)](https://flask.palletsprojects.com)
[![Deploy](https://img.shields.io/badge/Deploy-Render.com-46E3B7?style=flat-square&logo=render&labelColor=07080c)](https://render.com)
[![Bilingual](https://img.shields.io/badge/UI-EN_|_عربي-ffaa00?style=flat-square&labelColor=07080c)](#)

</div>

---

## The Problem

Python is the language developers think in. C++ is the language performance demands.

Rewriting Python to C++ by hand is slow, error-prone, and interrupts creative flow. Existing tools use regex-and-replace — they don't understand context, types, or idiomatic C++.

**Astmize closes that gap.**

> Paste Python. Get production-ready C++. Run it instantly in the browser — no setup, no compiler, no context switching.

---

## What It Does

Astmize sends your Python source through an AI orchestration engine that understands **intent and context** — not just syntax. The output is clean, compilable C++ with proper STL usage, type inference, and optional AI enhancement.

```python
# Input — Python 3.x
def find_max(nums: list[int]) -> int:
    result: int = nums[0]
    for i in range(1, len(nums)):
        if nums[i] > result:
            result = nums[i]
    return result

print(find_max([3, 7, 2, 9, 1]))
```

```cpp
// Output — C++17 (Astmize)
#include <iostream>
#include <vector>

int find_max(std::vector<int> nums) {
    int result = nums[0];
    for (int i = 1; i < (int)nums.size(); ++i) {
        if (nums[i] > result) result = nums[i];
    }
    return result;
}

int main() {
    std::cout << find_max({3, 7, 2, 9, 1}) << "\n";
    return 0;
}
```

```
▶ Output: 9   ✓ Compiled & executed via GCC
```

---

## Supported Versions

| Input | Output |
|---|---|
| Python 3.x (type hints, f-strings, modern syntax) | C++11 / C++17 |

Type annotations are preserved as strongly-typed C++ equivalents. When hints are absent, the AI infers types from context.

---

## Core Features

| Feature | Description |
|---|---|
| 🤖 **AI Orchestration** | 8 free AI models queried in sequence — automatic fallback ensures availability |
| 🔁 **AST Fallback Engine** | If all AI models are unavailable, a pure-Python AST transpiler handles conversion locally |
| ✦ **AI Enhancement** | One-click C++ refactor — AI improves idioms, explains every change |
| ▶ **Live Execution** | Compiles and runs generated C++ in the browser via Wandbox (GCC) |
| ⟳ **Conversion History** | Last 7 sessions stored locally — restore any previous conversion instantly |
| 🌐 **Bilingual UI** | Full English & Arabic interface with RTL support |
| ⬇️ **Multi-Format Export** | Download `.cpp`, copy as Markdown, or plain text |
| 📊 **Complexity Indicator** | Real-time simple / moderate / complex estimate as you type |
| ↔️ **Resizable Panels** | Drag to resize editors — layout ratio saved across sessions |
| ⚙️ **Editor Settings** | Font size, tab size, line numbers — all configurable |
| 🛡️ **Rate Limiting** | 60 req/min on `/convert`, 20 req/min on `/enhance` |
| 📱 **Mobile-First PWA** | Installable, offline-capable — full tab-switcher layout on small screens |
| ⌨️ **Keyboard Shortcuts** | `Ctrl+Enter` to transpile · full shortcut reference in-app |

---

## How It Works

```
┌─────────────────┐    POST /convert     ┌──────────────────────────┐
│   Python Input  │ ──────────────────▶ │     Flask Backend         │
│   (Browser UI)  │                      │                           │
└─────────────────┘                      │  Model 1 (Qwen3 Coder)   │
        │                                │  → Model 2 (DeepSeek)    │
        │    C++ + Warnings              │  → Model 3 … (×8 total)  │
        │ ◀────────────────────────────  │  → AST Fallback Engine   │
        ▼                                └──────────────────────────┘
┌─────────────────┐    POST /enhance     ┌──────────────────────────┐
│  C++ Output     │ ──────────────────▶ │  AI Refactor + Explain   │
│  (Highlighted)  │ ◀────────────────── └──────────────────────────┘
│                 │
│  [ ✦ Enhance ] │    POST → Wandbox    ┌──────────────────────────┐
│  [ ▶ Run     ] │ ──────────────────▶ │  GCC Compiler (Live)     │
│  Console Output │ ◀────────────────── │  stdout / stderr         │
└─────────────────┘                      └──────────────────────────┘
```

**Reliability by design:** No single point of failure. Every conversion attempt cascades through 8 AI models before falling back to the deterministic AST engine — ensuring output is always returned.

---

## Output Reliability

Astmize approaches correctness at multiple layers:

| Layer | Mechanism |
|---|---|
| **Compilation check** | All output is immediately runnable via Wandbox (GCC) — errors surface in the console, not silently |
| **AI fallback chain** | 8 models tried in sequence; the first valid compilable response is used |
| **AST fallback** | Deterministic rule-based transpiler activates when AI is unavailable |
| **Warning system** | Non-fatal translation issues are surfaced as inline warnings, not discarded |
| **Enhancement pass** | Optional AI refactor further improves correctness and C++ idiom compliance |

> **Note:** Astmize targets Python-to-C++ transpilation for prototyping, learning, and performance porting workflows. For safety-critical or production-compiled binaries, human review of the generated output is recommended — as with any code generation tool.

---

## Architecture

```
astmize/
├── app.py            # Flask API — AI orchestration, AST fallback, rate limiting
├── index.html        # Full frontend (single-file, zero build step)
├── requirements.txt  # Production dependencies
├── Procfile          # Process definition (Render / Heroku)
├── LICENSE
└── README.md
```

**API Endpoints**

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Health check — returns service version and status |
| `POST` | `/convert` | Accepts Python source, returns AI-generated C++ |
| `POST` | `/enhance` | Accepts C++, returns AI-refactored version + explanation |

---

## API Reference

### `GET /`

```json
{
  "service": "Astmize API",
  "status": "ok",
  "version": "2.1.0"
}
```

### `POST /convert`

**Request**
```http
POST /convert
Content-Type: application/json

{
  "python_code": "def greet(name: str):\n    print(f'Hello, {name}!')"
}
```

**Response `200`**
```json
{
  "success": true,
  "cpp_code": "#include <iostream>\n#include <string>\n\nvoid greet(std::string name) {\n    std::cout << \"Hello, \" << name << \"!\\n\";\n}\n",
  "warnings": [],
  "error": null
}
```

**Error responses**

| Code | Meaning |
|---|---|
| `429` | Rate limit exceeded |
| `413` | Payload exceeds 64 KB limit |
| `502` | All AI models unavailable (AST fallback also failed) |

### `POST /enhance`

**Request**
```http
POST /enhance
Content-Type: application/json

{
  "cpp_code": "#include <iostream>\n..."
}
```

**Response `200`**
```json
{
  "success": true,
  "enhanced_code": "#include <iostream>\n...",
  "explanation": "Replaced raw loop with std::max_element; renamed variable for clarity.",
  "error": null
}
```

<details>
<summary><b>Test with cURL / Python / Postman</b></summary>

**cURL**
```bash
# Health check
curl https://astmize.onrender.com/

# Transpile
curl -X POST https://astmize.onrender.com/convert \
  -H "Content-Type: application/json" \
  -d '{"python_code": "x: int = 42\nprint(x)"}'

# Enhance
curl -X POST https://astmize.onrender.com/enhance \
  -H "Content-Type: application/json" \
  -d '{"cpp_code": "#include <iostream>\nint main(){std::cout<<42;}"}'
```

**Python**
```python
import requests

resp = requests.post(
    "https://astmize.onrender.com/convert",
    json={"python_code": "for i in range(5):\n    print(i)"},
)
data = resp.json()
if data["success"]:
    print(data["cpp_code"])

resp2 = requests.post(
    "https://astmize.onrender.com/enhance",
    json={"cpp_code": data["cpp_code"]},
)
print(resp2.json()["explanation"])
```

</details>

---

## Local Development

```bash
# 1. Clone
git clone https://github.com/TheSpacetimeDebugger/Astmize.git
cd Astmize

# 2. Virtual environment
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set environment variables
export OPENROUTER_API_KEY="your-openrouter-api-key"
export FLASK_DEBUG=true

# 5. Start server
python app.py
# API available at http://localhost:5000
```

Open `index.html` directly in your browser — no build step required.

> **OpenRouter key:** Free at [openrouter.ai](https://openrouter.ai) — all models Astmize uses are on free tiers.

---

## Deploy to Render

1. Push to GitHub
2. [render.com](https://render.com) → **New Web Service** → connect repo
3. Configure:

| Field | Value |
|---|---|
| Environment | Python 3 |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `gunicorn app:app --workers 4 --bind 0.0.0.0:$PORT` |

4. Add `OPENROUTER_API_KEY` under **Environment Variables**

> **Cold start:** Render's free tier spins down after inactivity. The first request after a sleep period may take 30–90 seconds — the UI notifies users automatically.

---

## Changelog

### v2.1.0 — Current
- 🔁 **AST Fallback Engine** — deterministic transpiler activates when all AI models are unavailable
- 📦 Python 3.x → C++11 / C++17 version matrix documented
- 📊 Complexity Indicator — real-time simple / moderate / complex estimate
- ↔️ Resizable Panels with saved layout ratio
- ⤓ Export Dropdown — `.cpp`, Markdown, plain text
- ❓ Keyboard Shortcuts Modal
- 📲 PWA — installable with offline Service Worker
- 🍪 Privacy Consent Banner

### v2.0.1
- ✦ AI Enhancement — `/enhance` endpoint with refactor + explanation
- ⟳ Conversion History — last 7 sessions in localStorage
- 🔢 Live editor stats (line + character counter)
- 🐛 Fixed `program_message` → `program_output` (Wandbox stdout now displays correctly)

### v2.0.0
- 🤖 Replaced pure AST engine with AI orchestration via OpenRouter
- 🔁 8-model fallback chain
- 🛡️ Rate limiting with bilingual error messages
- ▶ Live C++ execution via Wandbox (GCC)
- 📱 Mobile-first layout with tab switcher
- 🌐 Full Arabic UI with RTL support

### v1.0.0
- Initial release — pure Python AST transpiler engine
- Flask backend, dark cyber frontend

---

## Contributing

Contributions, issues, and feature requests are welcome.

1. Fork the repository
2. Create a branch: `git checkout -b feature/your-feature`
3. Commit: `git commit -m 'feat: describe your change'`
4. Push: `git push origin feature/your-feature`
5. Open a Pull Request

For significant changes, open an issue first to align on approach.

---

## Contact

**Astmize Studio** · Built by [Ibrahim El-Shami](https://www.linkedin.com/in/ibrahim-el-shami-63a960415)

📧 [sydbrahim02@gmail.com](mailto:sydbrahim02@gmail.com) · 🐦 [@AstmizeStudio](https://x.com/AstmizeStudio) · 🚀 [Product Hunt](https://www.producthunt.com/products/astmize-python-c-transpiler)

For bugs or feature requests — open a GitHub issue or send an email.

---

## License

MIT © [Astmize Studio](LICENSE)

---

<div align="center">

*If Astmize saved you time, a ⭐ helps others discover the project.*

*Built with ⚡ by Astmize Studio*

</div>
