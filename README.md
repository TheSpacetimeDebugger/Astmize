# Astmize ⚡
![API Status](https://img.shields.io/badge/API-v1.4.2-green.svg)
> **Python → C++ AST Transpiler** — instantly translate and optimize your Python source code into fast, syntax-valid C++.
(https://thespacetimedebugger.github.io/Astmize/)
---

## What is Astmize?

Astmize is a high-performance transpilation engine that walks a Python **Abstract Syntax Tree (AST)** and emits semantically equivalent, idiomatic C++ code.

Rather than naive text substitution, Astmize operates at the tree level — understanding the *structure* of your code so it can make intelligent translation decisions:

| Python construct | C++ output |
|---|---|
| `def fn(x: int) -> float` | `double fn(int x)` |
| `for i in range(n)` | `for (int i = 0; i < n; ++i)` |
| `for item in collection` | `for (auto& item : collection)` |
| `print(x, y)` | `std::cout << x << y << "\n"` |
| `x: list[int] = []` | `std::vector<int> x = {}` |
| `x += 1` | `x += 1` |
| `a if cond else b` | `(cond ? a : b)` |

The backend is a pure-Python Flask API — zero external AI dependencies for the core engine. An `API_KEY` environment variable is wired in as a ready hook for future LLM-assisted optimisation.

---

## Architecture

```
astmize/
├── app.py            # Flask API + CppTranspiler (AST engine)
├── requirements.txt  # Production dependencies
├── Astmize.html
├── LICENSE
└── README.md

```

**Key classes / routes**

| Symbol | Role |
|---|---|
| `CppTranspiler` | `ast.NodeVisitor` subclass — the entire translation engine |
| `POST /convert` | Accepts `{ "python_code": "..." }`, returns translated C++ |
| `GET /` | Health-check endpoint |

---

## Local Development

```bash
# 1. Clone & enter the repo
git clone https://github.com/your-org/astmize.git
cd astmize

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. (Optional) Set environment variables
export API_KEY="sk-your-future-llm-key"
export FLASK_DEBUG=true

# 5. Run the development server
python app.py
# → http://localhost:5000
```

---

## API Reference

### `GET /`

Returns service health status.

```json
{ "service": "Astmize API", "status": "ok", "version": "1.0.0" }
```

---

### `POST /convert`

Translate Python source code to C++.

**Request**

```
POST /convert
Content-Type: application/json

{
  "python_code": "<your Python source>"
}
```

**Success response** `200`

```json
{
  "success": true,
  "cpp_code": "#include <iostream>\n...",
  "warnings": [],
  "error": null
}
```

**Error response** `422`

```json
{
  "success": false,
  "cpp_code": "",
  "warnings": [],
  "error": "Python SyntaxError at line 3: invalid syntax"
}
```

---

## Testing the API

### cURL

```bash
# Health check
curl https://your-app.onrender.com/

# Convert a Python snippet
curl -X POST https://your-app.onrender.com/convert \
  -H "Content-Type: application/json" \
  -d '{
    "python_code": "def add(a: int, b: int) -> int:\n    return a + b"
  }'
```

### Postman

1. **Method**: `POST`
2. **URL**: `https://your-app.onrender.com/convert`
3. **Headers**: `Content-Type: application/json`
4. **Body → raw → JSON**:
   ```json
   {
     "python_code": "for i in range(10):\n    print(i)"
   }
   ```

### Python `requests`

```python
import requests, json

resp = requests.post(
    "https://your-app.onrender.com/convert",
    json={"python_code": "x: int = 42\nprint(x)"},
)
data = resp.json()
print(data["cpp_code"])
```

---

## Supported Python Constructs

| Category | Supported |
|---|---|
| Variable assignments (typed & untyped) | ✅ |
| Function definitions with type hints | ✅ |
| `return` statements | ✅ |
| `for i in range(...)` loops | ✅ |
| `for x in iterable` loops | ✅ |
| `while` loops | ✅ |
| `if / elif / else` chains | ✅ |
| Augmented assignments (`+=`, `-=` …) | ✅ |
| Annotated assignments (`x: int = 5`) | ✅ |
| `print()` calls | ✅ |
| Binary & unary expressions | ✅ |
| Comparison & boolean expressions | ✅ |
| Ternary expressions (`a if c else b`) | ✅ |
| `break` / `continue` / `pass` | ✅ |
| `len()`, `abs()`, `max()`, `min()` … | ✅ |
| `list.append()` | ✅ |
| Classes / decorators / generators | 🛠 |
| `async/await` | 🛠 |

---

## Deploying to Render.com

1. Push this repo to GitHub.
2. On [render.com](https://render.com) → **New Web Service** → connect your repo.
3. Set the following in **Settings**:

| Field | Value |
|---|---|
| **Environment** | `Python 3` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `gunicorn app:app --workers 4 --bind 0.0.0.0:$PORT` |

4. (Optional) Add `API_KEY` under **Environment Variables**.

Changelog: 
Fixes v1.3.0
---
## communication:
Our official account [sydbrahim02@gmail.com]
---
## License

MIT © Astmize
