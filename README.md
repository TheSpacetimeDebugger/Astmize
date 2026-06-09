<div align="center">

<img src="https://img.shields.io/badge/Astmize-⚡-00d4ff?style=for-the-badge&labelColor=0a0a0a" alt="Astmize"/>

# ⚡ Astmize

### Python → C++ AST Transpiler

**Translate your Python source code into fast, idiomatic C++ — instantly.**

[![API](https://img.shields.io/badge/API-v2.0.0-00d4ff?style=flat-square)](https://thespacetimedebugger.github.io/Astmize/)
[![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8+-blue?style=flat-square&logo=python)](https://python.org)
[![Flask](https://img.shields.io/badge/flask-backend-lightgrey?style=flat-square&logo=flask)](https://flask.palletsprojects.com)
[![Deploy](https://img.shields.io/badge/deploy-Render.com-46E3B7?style=flat-square&logo=render)](https://render.com)

[**🚀 Try It Live**](https://thespacetimedebugger.github.io/Astmize/) · [**📖 API Docs**](#api-reference) · [**🐛 Report Bug**](mailto:sydbrahim02@gmail.com) · [**💡 Request Feature**](mailto:sydbrahim02@gmail.com)

</div>

---

## 🤔 What is Astmize?

Most transpilers do naive text substitution. **Astmize is different.**

It walks your Python source as an **Abstract Syntax Tree (AST)** — understanding the *structure* of your code, not just its text — and emits semantically equivalent, idiomatic C++ on the other side.

```python
# Python in ✨
def compute(items: list[int]) -> int:
    total: int = 0
    for i in range(len(items)):
        total += items[i]
    return total
```

```cpp
// C++ out ⚡
#include <iostream>
#include <vector>

int compute(std::vector<int> items) {
    int total = 0;
    for (int i = 0; i < items.size(); ++i) {
        total += items[i];
    }
    return total;
}
```

> Zero AI dependencies. Zero guessing. Pure AST-level translation.

---

## ✨ Feature Highlights

| Python | C++ Output |
|---|---|
| `def fn(x: int) -> float` | `double fn(int x)` |
| `for i in range(n)` | `for (int i = 0; i < n; ++i)` |
| `for item in collection` | `for (auto& item : collection)` |
| `print(x, y)` | `std::cout << x << y << "\n"` |
| `x: list[int] = []` | `std::vector<int> x = {}` |
| `a if cond else b` | `(cond ? a : b)` |
| `x += 1` | `x += 1` |

---

## 🗺️ Supported Constructs

<details>
<summary><b>Click to expand full support table</b></summary>

| Construct | Status |
|---|---|
| Variable assignments (typed & untyped) | ✅ |
| Function definitions with type hints | ✅ |
| `return` statements | ✅ |
| `for i in range(...)` loops | ✅ |
| `for x in iterable` loops | ✅ |
| `while` loops | ✅ |
| `if / elif / else` chains | ✅ |
| Augmented assignments (`+=`, `-=`, …) | ✅ |
| Annotated assignments (`x: int = 5`) | ✅ |
| `print()` calls | ✅ |
| Binary & unary expressions | ✅ |
| Comparison & boolean expressions | ✅ |
| Ternary expressions (`a if c else b`) | ✅ |
| `break` / `continue` / `pass` | ✅ |
| `len()`, `abs()`, `max()`, `min()`, … | ✅ |
| `list.append()` | ✅ |
| Classes / decorators / generators | 🛠 In progress |
| `async / await` | 🛠 In progress |

</details>

---

## 🏗️ Architecture

```
astmize/
├── app.py            # Flask API + CppTranspiler (AST engine)
├── requirements.txt  # Production dependencies
├── Astmize.html      # Frontend interface
├── Procfile
├── LICENSE
└── README.md
```

| Symbol | Role |
|---|---|
| `CppTranspiler` | `ast.NodeVisitor` subclass — the entire translation engine |
| `POST /convert` | Accepts `{ "python_code": "..." }`, returns translated C++ |
| `GET /` | Health-check / status endpoint |

---

## 🚀 Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/your-org/astmize.git
cd astmize

# 2. Set up a virtual environment
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. (Optional) Set environment variables
export API_KEY="sk-your-future-llm-key"
export FLASK_DEBUG=true

# 5. Run
python app.py
# → http://localhost:5000
```

---

## 📡 API Reference

### `GET /`

Health check.

```json
{ "service": "Astmize API", "status": "ok", "version": "2.0.0" }
```

---

### `POST /convert`

Translate Python source to C++.

**Request**

```http
POST /convert
Content-Type: application/json

{
  "python_code": "def add(a: int, b: int) -> int:\n    return a + b"
}
```

**Success `200`**

```json
{
  "success": true,
  "cpp_code": "#include <iostream>\n\nint add(int a, int b) {\n    return a + b;\n}",
  "warnings": [],
  "error": null
}
```

**Error `422`**

```json
{
  "success": false,
  "cpp_code": "",
  "warnings": [],
  "error": "Python SyntaxError at line 3: invalid syntax"
}
```

---

### Testing

**cURL**

```bash
# Health check
curl https://your-app.onrender.com/

# Convert a snippet
curl -X POST https://your-app.onrender.com/convert \
  -H "Content-Type: application/json" \
  -d '{"python_code": "def add(a: int, b: int) -> int:\n    return a + b"}'
```

**Python**

```python
import requests

resp = requests.post(
    "https://your-app.onrender.com/convert",
    json={"python_code": "x: int = 42\nprint(x)"},
)
print(resp.json()["cpp_code"])
```

---

## ☁️ Deploy to Render

1. Push this repo to GitHub.
2. Go to [render.com](https://render.com) → **New Web Service** → connect your repo.
3. Configure:

| Field | Value |
|---|---|
| **Environment** | Python 3 |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `gunicorn app:app --workers 4 --bind 0.0.0.0:$PORT` |

4. *(Optional)* Add `API_KEY` under **Environment Variables**.

---

## 📋 Changelog

### v2.0.0
- Improved class support
- Security enhancements
- Warnings array in API response

### v1.0.0
- Initial release

---

## 🤝 Contributing

Contributions, issues, and feature requests are welcome!

1. Fork the repo
2. Create your branch: `git checkout -b feature/amazing-feature`
3. Commit: `git commit -m 'Add amazing feature'`
4. Push: `git push origin feature/amazing-feature`
5. Open a Pull Request

---

## 📬 Contact

**Astmize Studio** — [sydbrahim02@gmail.com](mailto:sydbrahim02@gmail.com)

---

## 📄 License

MIT © [Astmize](LICENSE)

---

<div align="center">

If Astmize saved you time, consider giving it a ⭐ — it helps others discover the project!

</div>
