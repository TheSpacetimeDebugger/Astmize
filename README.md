<div align="center">

<br/>

```
   █████╗ ███████╗████████╗███╗   ███╗██╗███████╗███████╗
  ██╔══██╗██╔════╝╚══██╔══╝████╗ ████║██║╚══███╔╝██╔════╝
  ███████║███████╗   ██║   ██╔████╔██║██║  ███╔╝ █████╗  
  ██╔══██║╚════██║   ██║   ██║╚██╔╝██║██║ ███╔╝  ██╔══╝  
  ██║  ██║███████║   ██║   ██║ ╚═╝ ██║██║███████╗███████╗
  ╚═╝  ╚═╝╚══════╝   ╚═╝   ╚═╝     ╚═╝╚═╝╚══════╝╚══════╝
```

### ⚡ Python → C++ — AI-Powered Transpiler

[![Live](https://img.shields.io/badge/🌐_Live_Demo-Visit_Now-00e5ff?style=for-the-badge&labelColor=07080c)](https://thespacetimedebugger.github.io/Astmize/)
[![API](https://img.shields.io/badge/API-v2.0.0-9b6dff?style=flat-square&labelColor=07080c)](https://thespacetimedebugger.github.io/Astmize/)
[![License](https://img.shields.io/badge/License-MIT-00ff88?style=flat-square&labelColor=07080c)](LICENSE)
[![Flask](https://img.shields.io/badge/Backend-Flask-lightgrey?style=flat-square&logo=flask&labelColor=07080c)](https://flask.palletsprojects.com)
[![Deploy](https://img.shields.io/badge/Deploy-Render.com-46E3B7?style=flat-square&logo=render&labelColor=07080c)](https://render.com)
[![Bilingual](https://img.shields.io/badge/UI-EN_|_عربي-ffaa00?style=flat-square&labelColor=07080c)](#)

<br/>

> **Write Python. Get C++. Powered by AI.**  
> Astmize uses free AI models in sequence to intelligently translate your Python source into fast, compilable C++ — then runs it live in the browser.

<br/>

</div>

---

## ✨ What Makes Astmize Different

Most transpilers do regex-and-replace. Astmize sends your Python to an AI engine that **understands context, intent, and idiomatic C++** — then lets you run the result instantly without leaving the page.

```python
# ✍️  You write this in Python
def find_max(nums: list[int]) -> int:
    result: int = nums[0]
    for i in range(1, len(nums)):
        if nums[i] > result:
            result = nums[i]
    return result

print(find_max([3, 7, 2, 9, 1]))
```

```cpp
// ⚡  Astmize generates this C++
#include <iostream>
#include <vector>

int find_max(std::vector<int> nums) {
    int result = nums[0];
    for (int i = 1; i < nums.size(); ++i) {
        if (nums[i] > result) {
            result = nums[i];
        }
    }
    return result;
}

int main() {
    std::cout << find_max({3, 7, 2, 9, 1}) << "\n";
    return 0;
}
```

```
▶ Output: 9
```

---

## 🚀 Features

| Feature | Details |
|---|---|
| 🤖 **AI-Powered Translation** | Tries multiple free AI models in sequence for best results |
| ▶ **Live C++ Execution** | Runs compiled C++ in the browser via [Wandbox](https://wandbox.org) (GCC) |
| 🌐 **Bilingual UI** | Full English & Arabic interface with RTL support |
| ⬇️ **Download Output** | Export your generated `.cpp` file instantly |
| 📋 **Copy to Clipboard** | One-click copy of the generated C++ code |
| ⚙️ **Editor Settings** | Font size, editor height, tab size, line numbers — all configurable |
| 🛡️ **Rate Limiting** | 60 requests/min to protect server stability for all users |
| 📱 **Mobile Responsive** | Full tab-switcher layout for small screens |
| 🌑 **Dark Cyber UI** | Built with a dark, minimal, zero-distraction aesthetic |
| ⌨️ **Keyboard Shortcut** | `Ctrl+Enter` / `Cmd+Enter` to transpile instantly |

---

## 🧠 How It Works

```
┌─────────────────┐      POST /convert       ┌──────────────────────┐
│   Your Python   │ ─────────────────────── ▶│   Flask Backend      │
│   (Browser UI)  │                           │                      │
└─────────────────┘                           │  Tries AI Model 1    │
        │                                     │  → Model 2 (if busy) │
        │         C++ + Warnings              │  → Model 3 …         │
        │ ◀────────────────────────────────── │                      │
        ▼                                     └──────────────────────┘
┌─────────────────┐
│  Syntax-colored │      POST to Wandbox      ┌──────────────────────┐
│  C++ output     │ ─────────────────────── ▶│  GCC Compiler (Live) │
│                 │ ◀─────────────────────── │  stdout / stderr      │
│  Console Output │                           └──────────────────────┘
└─────────────────┘
```

1. You paste Python code into the editor
2. Astmize sends it to the Flask backend
3. The backend queries free AI models in sequence until one responds
4. The C++ is returned, syntax-highlighted, and displayed
5. Optionally hit **▶ Run** to compile & execute it live via Wandbox

---

## 🏗️ Architecture

```
astmize/
├── app.py            # Flask API — AI orchestration & transpilation logic
├── requirements.txt  # Production dependencies
├── index.html        # Full frontend (single-file, zero build step)
├── Procfile          # Render/Heroku process definition
├── LICENSE
└── README.md
```

**API Endpoints**

| Method | Route | Description |
|---|---|---|
| `GET` | `/` | Health check — returns service status |
| `POST` | `/convert` | Accepts Python, returns AI-generated C++ |

---

## 📡 API Reference

### `GET /`

```json
{
  "service": "Astmize API",
  "status": "ok",
  "version": "1.4.0"
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

**Success `200`**
```json
{
  "success": true,
  "cpp_code": "#include <iostream>\n#include <string>\n\nvoid greet(std::string name) {\n    std::cout << \"Hello, \" << name << \"!\" << \"\\n\";\n}\n",
  "warnings": [],
  "error": null
}
```

**Error `422`**
```json
{
  "success": false,
  "cpp_code": "",
  "warnings": ["Unsupported construct: lambda with default args"],
  "error": "Translation failed: could not resolve f-string expression"
}
```

**Rate Limited `429`**
```json
{
  "error": "Rate limit exceeded. Please wait before retrying."
}
```

<details>
<summary><b>📬 Test with cURL / Python / Postman</b></summary>

**cURL**
```bash
# Health check
curl https://your-app.onrender.com/

# Transpile
curl -X POST https://your-app.onrender.com/convert \
  -H "Content-Type: application/json" \
  -d '{"python_code": "x: int = 42\nprint(x)"}'
```

**Python**
```python
import requests

resp = requests.post(
    "https://your-app.onrender.com/convert",
    json={"python_code": "for i in range(5):\n    print(i)"},
)
data = resp.json()
if data["success"]:
    print(data["cpp_code"])
```

**Postman**
- Method: `POST`
- URL: `https://your-app.onrender.com/convert`
- Headers: `Content-Type: application/json`
- Body → raw → JSON: `{ "python_code": "..." }`

</details>

---

## 🖥️ Local Development

```bash
# 1. Clone
git clone https://github.com/your-org/astmize.git
cd astmize

# 2. Virtual environment
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate

# 3. Install
pip install -r requirements.txt

# 4. (Optional) environment variables
export API_KEY="sk-your-ai-key"
export FLASK_DEBUG=true

# 5. Run
python app.py
# → http://localhost:5000
```

Then open `index.html` in your browser — no build step needed.

---

## ☁️ Deploy to Render

1. Push to GitHub
2. [render.com](https://render.com) → **New Web Service** → connect repo
3. Configure:

| Field | Value |
|---|---|
| **Environment** | Python 3 |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `gunicorn app:app --workers 4 --bind 0.0.0.0:$PORT` |

4. Add `API_KEY` under **Environment Variables** if needed

> **Cold start note:** Render's free tier spins down after inactivity. The first request may take 30–90 seconds while the server wakes and finds an available AI model — the UI will notify you automatically.

---

## 📋 Changelog

### v2.0.0 — Current
- 🤖 Replaced pure AST engine with AI model orchestration
- 🔁 Multi-model fallback: tries multiple free AI providers in sequence
- 🛡️ Rate limiting (60 req/min) with bilingual error messages
- ▶ Live C++ execution via Wandbox (GCC)
- 📱 Mobile tab-switcher layout
- ⚙️ Editor settings panel (font size, height, tab size, line numbers)
- 🌐 Full Arabic UI with RTL support

### v1.0.0
- Initial release with Python AST engine
- Flask backend, dark cyber frontend

---

## 🤝 Contributing

Contributions, issues, and feature requests are welcome!

1. Fork the repo
2. Create your branch: `git checkout -b feature/my-feature`
3. Commit: `git commit -m 'feat: add my feature'`
4. Push: `git push origin feature/my-feature`
5. Open a Pull Request

Please keep PRs focused and well-described. For major changes, open an issue first to discuss.

---

## 📬 Contact & Support

**Astmize Studio**

📧 [sydbrahim02@gmail.com](mailto:sydbrahim02@gmail.com)

For bugs, feature requests, or general questions — email is the best way to reach us.

---

## 📄 License

MIT © [Astmize Studio](LICENSE)

---

<div align="center">

<br/>

**If Astmize saved you time or impressed you, drop a ⭐ — it means the world and helps others discover the project.**

<br/>

*Built with ⚡ by Astmize Studio*

</div>
