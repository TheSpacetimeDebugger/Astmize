"""
Astmize — Python → C++ AI Transpiler Backend  v2.0.0
Flask API server. Conversion is now fully AI-powered via OpenRouter (Qwen3 Coder).

Changes in v2.0.0:
  - CORE CHANGE: /convert now uses the OpenRouter AI model directly instead of the
    AST engine.  The response shape is unchanged: { success, cpp_code, warnings, error }
    so the frontend requires zero modifications.
  - The old CppTranspiler class is retained in this file for reference but is no
    longer called by any route.
  - /enhance route is unchanged.
  - Timeout for /convert increased to 60 s (AI inference takes longer than AST).
"""

import ast
import os
import re
import json
import logging
import requests as http_requests
from flask import Flask, request, jsonify
from flask_cors import CORS

# ── Optional rate-limiter (install flask-limiter to enable) ────────────────────
try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    _LIMITER_AVAILABLE = True
except ImportError:                          # pragma: no cover
    _LIMITER_AVAILABLE = False

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
logger = logging.getLogger(__name__)

# ── App bootstrap ──────────────────────────────────────────────────────────────
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# ── API Keys ───────────────────────────────────────────────────────────────────
# Set these as Environment Variables in Render — never hardcode them here.
API_KEY: str | None        = os.getenv("API_KEY")         # general auth key (optional)
GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY")  # OpenRouter API key

if not GEMINI_API_KEY:
    logger.warning(
        "GEMINI_API_KEY is not set. "
        "Add it as an Environment Variable in your Render dashboard."
    )

# ── Rate limiter ───────────────────────────────────────────────────────────────
if _LIMITER_AVAILABLE:
    limiter = Limiter(
        key_func=get_remote_address,
        app=app,
        default_limits=[],                   # no global limit; only route-level
        storage_uri="memory://",
    )
    logger.info("Rate limiting enabled (flask-limiter).")
else:
    limiter = None                           # type: ignore[assignment]
    logger.warning(
        "flask-limiter not installed — rate limiting disabled. "
        "Run: pip install flask-limiter"
    )


def rate_limit(limit_string: str):
    """Decorator factory that applies a rate limit when limiter is available."""
    def decorator(fn):
        if limiter is not None:
            return limiter.limit(limit_string)(fn)
        return fn
    return decorator


# ══════════════════════════════════════════════════════════════════════════════
#  AST → C++ translation engine
# ══════════════════════════════════════════════════════════════════════════════

PYTHON_TYPE_MAP: dict[str, str] = {
    "int":   "int",
    "float": "double",
    "str":   "std::string",
    "bool":  "bool",
    "list":  "std::vector<int>",
    "List":  "std::vector<int>",
    "dict":  "std::map<std::string, int>",
    "Dict":  "std::map<std::string, int>",
    "set":   "std::set<int>",
    "Set":   "std::set<int>",
    "None":  "void",
    "Any":   "auto",
}

BINOP_MAP: dict[type, str] = {
    ast.Add:      "+",
    ast.Sub:      "-",
    ast.Mult:     "*",
    ast.Div:      "/",
    ast.Mod:      "%",
    ast.Pow:      "pow",
    ast.FloorDiv: "/",
    ast.BitAnd:   "&",
    ast.BitOr:    "|",
    ast.BitXor:   "^",
    ast.LShift:   "<<",
    ast.RShift:   ">>",
    ast.MatMult:  "*",
}

CMPOP_MAP: dict[type, str] = {
    ast.Eq:    "==",
    ast.NotEq: "!=",
    ast.Lt:    "<",
    ast.LtE:   "<=",
    ast.Gt:    ">",
    ast.GtE:   ">=",
}

BOOLOP_MAP: dict[type, str] = {
    ast.And: "&&",
    ast.Or:  "||",
}

UNARYOP_MAP: dict[type, str] = {
    ast.USub:   "-",
    ast.UAdd:   "+",
    ast.Not:    "!",
    ast.Invert: "~",
}


class CppTranspiler(ast.NodeVisitor):
    """
    Walks a Python AST and emits equivalent C++ source code.
    """

    def __init__(self) -> None:
        self._lines: list[str] = []
        self._indent: int = 0
        self._includes: set[str] = {"<iostream>", "<string>"}
        self._warnings: list[str] = []
        self._warned_set: set[str] = set()   # dedup guard
        self._declared: set[str] = set()

    # ── helpers ────────────────────────────────────────────────────────────────

    def _emit(self, line: str) -> None:
        self._lines.append("    " * self._indent + line)

    def _warn(self, msg: str) -> None:
        if msg not in self._warned_set:
            self._warned_set.add(msg)
            self._warnings.append(msg)
        self._emit(f"// [Astmize warning] {msg}")

    def _inc(self) -> None:
        self._indent += 1

    def _dec(self) -> None:
        self._indent = max(0, self._indent - 1)

    def _infer_cpp_type(self, node: ast.expr) -> str:
        """
        Infer a concrete C++ type from an AST expression node.
        Containers recurse into their elements so we never produce illegal `auto`
        as a template argument.
        """
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool):
                return "bool"
            if isinstance(node.value, int):
                return "int"
            if isinstance(node.value, float):
                return "double"
            if isinstance(node.value, str):
                self._includes.add("<string>")
                return "std::string"
        if isinstance(node, ast.List):
            self._includes.add("<vector>")
            if node.elts:
                elem_type = self._infer_cpp_type(node.elts[0])
                return f"std::vector<{elem_type}>"
            return "std::vector<int>"
        if isinstance(node, ast.Dict):
            self._includes.add("<map>")
            if node.keys and node.keys[0] is not None:
                key_type = self._infer_cpp_type(node.keys[0])
                val_type = self._infer_cpp_type(node.values[0]) if node.values else "int"
                return f"std::map<{key_type}, {val_type}>"
            return "std::map<std::string, int>"
        if isinstance(node, ast.Set):
            self._includes.add("<set>")
            if node.elts:
                elem_type = self._infer_cpp_type(node.elts[0])
                return f"std::set<{elem_type}>"
            return "std::set<int>"
        return "auto"

    # ── Keyword sets for name-based type inference ─────────────────────────────
    _STRING_KEYWORDS: frozenset[str] = frozenset({
        "name", "title", "text", "label", "message", "msg", "description",
        "desc", "info", "tag", "key", "value", "url", "path", "filename",
        "file", "content", "body", "subject", "prefix", "suffix", "token",
        "word", "line", "output", "input", "result", "response", "query",
        "email", "address", "city", "country", "language", "lang", "color",
        "colour", "type", "kind", "category", "status", "state", "mode",
        "format", "encoding", "charset", "symbol", "alias", "username",
        "password", "secret", "comment", "note", "summary", "header",
    })

    _INT_KEYWORDS: frozenset[str] = frozenset({
        "speed", "damage", "ammo", "battery", "score", "count", "age",
        "level", "rank", "index", "id", "num", "number", "total", "size",
        "length", "width", "height", "weight", "capacity", "limit", "max",
        "min", "offset", "step", "distance", "health", "mana", "stamina",
        "experience", "exp", "power", "strength", "defense", "armor",
        "quantity", "amount", "duration", "timeout", "port", "priority",
        "version", "code", "error", "flag", "tick", "frame", "pixel",
        "row", "col", "column", "page", "cursor", "position", "pos",
        "order", "depth", "degree", "generation", "iteration", "attempt",
        "retry", "threshold", "interval", "delay", "timeout", "pid",
    })

    _FLOAT_KEYWORDS: frozenset[str] = frozenset({
        "rate", "ratio", "factor", "scale", "weight", "score", "probability",
        "prob", "density", "pressure", "temperature", "temp", "angle",
        "rotation", "velocity", "acceleration", "force", "energy", "mass",
        "gravity", "friction", "opacity", "alpha", "beta", "gamma",
        "latitude", "longitude", "lat", "lon", "lng", "radius", "diameter",
        "percent", "percentage", "average", "avg", "mean", "variance",
        "deviation", "std", "precision", "tolerance", "epsilon",
    })

    _BOOL_KEYWORDS: frozenset[str] = frozenset({
        "is_", "has_", "can_", "should_", "was_", "will_", "enable",
        "enabled", "disable", "disabled", "active", "inactive", "visible",
        "hidden", "open", "closed", "locked", "unlocked", "paused",
        "running", "stopped", "ready", "done", "finished", "started",
        "loading", "loaded", "valid", "invalid", "success", "failed",
        "error", "alive", "dead", "online", "offline", "connected",
        "authenticated", "authorized", "muted", "debug", "verbose",
    })

    def _infer_member_type(self, attr_name: str, value_node: ast.expr | None) -> str:
        """
        Smart type inference for class member variables (self.x assignments).

        Priority order:
          1. If the value node has a concrete type (Constant / container), use it.
          2. If the attribute name contains a recognised keyword, use the mapped type.
          3. Fall back to `int` (safe, always accepted by C++ as a non-static data member).

        Never returns `auto` — that is illegal for non-static data members in C++.
        """
        # ── 1. Value-based inference ───────────────────────────────────────────
        if value_node is not None:
            inferred = self._infer_cpp_type(value_node)
            if inferred != "auto":
                return inferred

        # ── 2. Name-based inference ────────────────────────────────────────────
        name_lower = attr_name.lower()

        # Bool: check prefix patterns first (is_active, has_ammo, …)
        for prefix in ("is_", "has_", "can_", "should_", "was_", "will_"):
            if name_lower.startswith(prefix):
                return "bool"

        # Exact or substring match against keyword sets
        # Split on underscores so "player_speed" matches "speed"
        parts = set(name_lower.split("_")) | {name_lower}

        for part in parts:
            if part in self._BOOL_KEYWORDS:
                return "bool"
        for part in parts:
            if part in self._STRING_KEYWORDS:
                self._includes.add("<string>")
                return "std::string"
        for part in parts:
            if part in self._FLOAT_KEYWORDS:
                return "double"
        for part in parts:
            if part in self._INT_KEYWORDS:
                return "int"

        # ── 3. Safe fallback — never `auto` ───────────────────────────────────
        return "int"

    def _annotation_to_cpp(self, annotation: ast.expr | None) -> str:
        """Convert a Python type annotation node to its C++ equivalent."""
        if annotation is None:
            return "auto"

        if isinstance(annotation, ast.Constant):
            if annotation.value is None:
                return "void"
            if isinstance(annotation.value, str):
                return annotation.value
            return "auto"

        if isinstance(annotation, ast.Name):
            cpp_type = PYTHON_TYPE_MAP.get(annotation.id, annotation.id)
            if "vector" in cpp_type:
                self._includes.add("<vector>")
            if "map" in cpp_type:
                self._includes.add("<map>")
            if "set" in cpp_type and "unordered" not in cpp_type:
                self._includes.add("<set>")
            if "string" in cpp_type:
                self._includes.add("<string>")
            return cpp_type

        if isinstance(annotation, ast.Attribute):
            return self._annotation_to_cpp(ast.Name(id=annotation.attr, ctx=ast.Load()))

        if isinstance(annotation, ast.Tuple):
            parts = [self._annotation_to_cpp(e) for e in annotation.elts]
            return ", ".join(parts)

        if isinstance(annotation, ast.Subscript):
            outer_node = annotation.value
            outer_name = ""
            if isinstance(outer_node, ast.Name):
                outer_name = outer_node.id
            elif isinstance(outer_node, ast.Attribute):
                outer_name = outer_node.attr

            if outer_name in ("list", "List"):
                self._includes.add("<vector>")
                inner = self._annotation_to_cpp(annotation.slice)
                return f"std::vector<{inner}>"

            if outer_name in ("dict", "Dict"):
                self._includes.add("<map>")
                slice_node = annotation.slice
                if isinstance(slice_node, ast.Tuple) and len(slice_node.elts) >= 2:
                    key_t = self._annotation_to_cpp(slice_node.elts[0])
                    val_t = self._annotation_to_cpp(slice_node.elts[1])
                    return f"std::map<{key_t}, {val_t}>"
                inner = self._annotation_to_cpp(slice_node)
                return f"std::map<std::string, {inner}>"

            if outer_name in ("set", "Set", "FrozenSet", "frozenset"):
                self._includes.add("<set>")
                inner = self._annotation_to_cpp(annotation.slice)
                return f"std::set<{inner}>"

            if outer_name in ("Optional", "optional"):
                self._includes.add("<optional>")
                inner = self._annotation_to_cpp(annotation.slice)
                return f"std::optional<{inner}>"

            if outer_name in ("Tuple", "tuple"):
                self._includes.add("<tuple>")
                slice_node = annotation.slice
                if isinstance(slice_node, ast.Tuple):
                    types = ", ".join(self._annotation_to_cpp(e) for e in slice_node.elts)
                    return f"std::tuple<{types}>"
                inner = self._annotation_to_cpp(slice_node)
                return f"std::tuple<{inner}>"

            if outer_name == "Union":
                slice_node = annotation.slice
                if isinstance(slice_node, ast.Tuple) and slice_node.elts:
                    return self._annotation_to_cpp(slice_node.elts[0])

            if outer_name in ("Deque", "deque"):
                self._includes.add("<deque>")
                inner = self._annotation_to_cpp(annotation.slice)
                return f"std::deque<{inner}>"

            outer_cpp = self._annotation_to_cpp(outer_node)
            inner_cpp = self._annotation_to_cpp(annotation.slice)
            return f"{outer_cpp}<{inner_cpp}>"

        return "auto"

    def _return_type(self, func_node: ast.FunctionDef) -> str:
        if func_node.returns:
            return self._annotation_to_cpp(func_node.returns)
        for node in ast.walk(func_node):
            if isinstance(node, ast.Return) and node.value is not None:
                return self._infer_cpp_type(node.value)
        return "void"

    # ── expression emitter ─────────────────────────────────────────────────────

    def _expr(self, node: ast.expr) -> str:
        try:
            return self._expr_inner(node)
        except Exception as exc:
            node_name = type(node).__name__
            self._warn(f"Could not translate expression {node_name}: {exc}")
            return f"/* unsupported: {node_name} */"

    def _expr_inner(self, node: ast.expr) -> str:   # noqa: C901 (long but flat)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, str):
                escaped = (
                    node.value
                    .replace("\\", "\\\\")
                    .replace('"', '\\"')
                    .replace("\n", "\\n")
                    .replace("\t", "\\t")
                    .replace("\r", "\\r")
                )
                return f'"{escaped}"'
            if isinstance(node.value, bool):
                return "true" if node.value else "false"
            if node.value is None:
                return "nullptr"
            return str(node.value)

        if isinstance(node, ast.Name):
            return node.id

        if isinstance(node, ast.BinOp):
            op_type = type(node.op)
            # ── special case: str * int  →  std::string(n, c) ────────────────
            if op_type == ast.Mult:
                left_is_str  = isinstance(node.left,  ast.Constant) and isinstance(node.left.value,  str)
                right_is_str = isinstance(node.right, ast.Constant) and isinstance(node.right.value, str)
                left_is_int  = isinstance(node.left,  ast.Constant) and isinstance(node.left.value,  int)
                right_is_int = isinstance(node.right, ast.Constant) and isinstance(node.right.value, int)
                if left_is_str and right_is_int:
                    self._includes.add("<string>")
                    s = node.left.value
                    n = node.right.value
                    if len(s) == 1:
                        return f"std::string({n}, '{s}')"
                    return f"std::string({n}, '?') /* repeated: \"{s}\" */"
                if right_is_str and left_is_int:
                    self._includes.add("<string>")
                    s = node.right.value
                    n = node.left.value
                    if len(s) == 1:
                        return f"std::string({n}, '{s}')"
                    return f"std::string({n}, '?') /* repeated: \"{s}\" */"
            # ── string + string  →  keep as + (std::string supports it) ──────
            left = self._expr(node.left)
            right = self._expr(node.right)
            if op_type == ast.Pow:
                self._includes.add("<cmath>")
                return f"std::pow({left}, {right})"
            if op_type == ast.FloorDiv:
                return f"({left} / {right})"
            op = BINOP_MAP.get(op_type, "?")
            return f"({left} {op} {right})"

        if isinstance(node, ast.UnaryOp):
            op = UNARYOP_MAP.get(type(node.op), "?")
            operand = self._expr(node.operand)
            return f"({op}{operand})"

        if isinstance(node, ast.BoolOp):
            op = BOOLOP_MAP.get(type(node.op), "&&")
            parts = [self._expr(v) for v in node.values]
            return f" {op} ".join(f"({p})" for p in parts)

        if isinstance(node, ast.Compare):
            left = self._expr(node.left)
            parts = []
            for op_node, comparator in zip(node.ops, node.comparators):
                op = CMPOP_MAP.get(type(op_node), "==")
                right = self._expr(comparator)
                if isinstance(op_node, ast.In):
                    self._includes.add("<algorithm>")
                    parts.append(
                        f"std::find({right}.begin(), {right}.end(), {left}) != {right}.end()"
                    )
                elif isinstance(op_node, ast.NotIn):
                    self._includes.add("<algorithm>")
                    parts.append(
                        f"std::find({right}.begin(), {right}.end(), {left}) == {right}.end()"
                    )
                elif isinstance(op_node, ast.Is):
                    parts.append(f"{left} == {right}")
                elif isinstance(op_node, ast.IsNot):
                    parts.append(f"{left} != {right}")
                else:
                    parts.append(f"{left} {op} {right}")
                left = right
            return " && ".join(parts)

        if isinstance(node, ast.IfExp):
            test = self._expr(node.test)
            body = self._expr(node.body)
            orelse = self._expr(node.orelse)
            return f"({test} ? {body} : {orelse})"

        if isinstance(node, ast.Call):
            return self._call_expr(node)

        if isinstance(node, ast.Attribute):
            return f"{self._expr(node.value)}.{node.attr}"

        if isinstance(node, ast.Subscript):
            return f"{self._expr(node.value)}[{self._expr(node.slice)}]"

        if isinstance(node, ast.List):
            self._includes.add("<vector>")
            elems = ", ".join(self._expr(e) for e in node.elts)
            return f"{{{elems}}}"

        if isinstance(node, ast.Tuple):
            self._includes.add("<tuple>")
            elems = ", ".join(self._expr(e) for e in node.elts)
            return f"std::make_tuple({elems})"

        if isinstance(node, ast.Set):
            self._includes.add("<set>")
            elems = ", ".join(self._expr(e) for e in node.elts)
            return f"{{{elems}}}"

        if isinstance(node, ast.Dict):
            self._includes.add("<map>")
            if not node.keys:
                return "{}"
            pairs = ", ".join(
                f"{{{self._expr(k)}, {self._expr(v)}}}"
                for k, v in zip(node.keys, node.values)
                if k is not None
            )
            return f"{{{pairs}}}"

        if isinstance(node, ast.JoinedStr):
            return self._fstring_expr(node)

        if isinstance(node, ast.ListComp):
            self._warn("List comprehensions require manual rewrite as a loop in C++")
            return "/* list-comprehension — rewrite as loop */"

        if isinstance(node, ast.DictComp):
            self._warn("Dict comprehensions require manual rewrite as a loop in C++")
            return "/* dict-comprehension — rewrite as loop */"

        if isinstance(node, ast.SetComp):
            self._warn("Set comprehensions require manual rewrite as a loop in C++")
            return "/* set-comprehension — rewrite as loop */"

        if isinstance(node, ast.GeneratorExp):
            self._warn("Generator expressions require manual rewrite in C++")
            return "/* generator-expression — rewrite as loop */"

        if isinstance(node, ast.Lambda):
            params = ", ".join(f"auto {a.arg}" for a in node.args.args)
            body = self._expr(node.body)
            return f"[&]({params}) {{ return {body}; }}"

        if isinstance(node, ast.Starred):
            return f"/* *{self._expr(node.value)} */"

        if isinstance(node, ast.Await):
            return self._expr(node.value)

        self._warn(f"Unsupported expression: {type(node).__name__}")
        return f"/* unsupported: {type(node).__name__} */"

    def _fstring_parts(self, node: ast.JoinedStr) -> list[str]:
        """Return the list of << operands for an f-string."""
        parts: list[str] = []
        for val in node.values:
            if isinstance(val, ast.Constant):
                escaped = str(val.value).replace("\\", "\\\\").replace('"', '\\"')
                parts.append(f'"{escaped}"')
            elif isinstance(val, ast.FormattedValue):
                parts.append(self._expr(val.value))
            else:
                parts.append('""')
        return parts or ['""']

    def _fstring_expr(self, node: ast.JoinedStr) -> str:
        """
        Translate an f-string.
        When used in print() directly, _call_expr inlines it as << chain.
        When used as a value (assignment, return, etc.) we need a string,
        so we use a compact std::ostringstream lambda.
        """
        self._includes.add("<sstream>")
        self._includes.add("<string>")
        parts = self._fstring_parts(node)
        stream_ops = " << ".join(parts)
        return f'([&](){{ std::ostringstream _oss; _oss << {stream_ops}; return _oss.str(); }}())'

    def _call_expr(self, node: ast.Call) -> str:
        """Translate a Python call expression to C++."""
        func_name = ""
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = f"{self._expr(node.func.value)}.{node.func.attr}"

        args = [self._expr(a) for a in node.args]

        # ── print() ──────────────────────────────────────────────────────────
        if func_name == "print":
            self._includes.add("<iostream>")
            sep = '" "'
            end = '"\\n"'
            for kw in node.keywords:
                if kw.arg == "sep":
                    sep = self._expr(kw.value)
                elif kw.arg == "end":
                    end = self._expr(kw.value)

            # Expand each argument: f-strings become << chains directly
            def _expand(arg_node: ast.expr) -> str:
                if isinstance(arg_node, ast.JoinedStr):
                    return " << ".join(self._fstring_parts(arg_node))
                return self._expr(arg_node)

            expanded = [_expand(a) for a in node.args]

            if not expanded:
                return f'std::cout << {end}'
            if len(expanded) == 1:
                return f'std::cout << {expanded[0]} << {end}'
            joined = f' << {sep} << '.join(expanded)
            return f'std::cout << {joined} << {end}'

        # ── len() ─────────────────────────────────────────────────────────────
        if func_name == "len":
            if args:
                return f"{args[0]}.size()"
            return "0"

        # ── type casts ────────────────────────────────────────────────────────
        if func_name in ("int", "float", "str", "bool"):
            cpp_cast = PYTHON_TYPE_MAP.get(func_name, func_name)
            if args:
                return f"static_cast<{cpp_cast}>({args[0]})"
            return f"{cpp_cast}()"

        # ── range() ───────────────────────────────────────────────────────────
        if func_name == "range":
            return f"range({', '.join(args)})"

        # ── math functions ────────────────────────────────────────────────────
        if func_name in ("abs", "sqrt", "ceil", "floor", "round", "pow",
                         "log", "log2", "log10", "exp", "sin", "cos", "tan"):
            self._includes.add("<cmath>")
            return f"std::{func_name}({', '.join(args)})"

        if func_name == "max":
            self._includes.add("<algorithm>")
            return f"std::max({', '.join(args)})"

        if func_name == "min":
            self._includes.add("<algorithm>")
            return f"std::min({', '.join(args)})"

        # ── sorted() ─────────────────────────────────────────────────────────
        if func_name == "sorted":
            self._includes.add("<algorithm>")
            if args:
                self._warn(
                    "sorted() returns a sorted copy; the original container is NOT mutated."
                )
                src = args[0]
                return (
                    f"([&](){{ auto _tmp = {src}; "
                    f"std::sort(_tmp.begin(), _tmp.end()); return _tmp; }}())"
                )
            return "/* sorted() — no argument */"

        # ── reversed() ───────────────────────────────────────────────────────
        if func_name == "reversed":
            self._includes.add("<algorithm>")
            if args:
                self._warn(
                    "reversed() returns a reversed copy; the original container is NOT mutated."
                )
                src = args[0]
                return (
                    f"([&](){{ auto _tmp = {src}; "
                    f"std::reverse(_tmp.begin(), _tmp.end()); return _tmp; }}())"
                )
            return "/* reversed() — no argument */"

        if func_name == "enumerate":
            self._warn("enumerate() has no direct C++ equivalent — rewrite as indexed loop")
            return f"/* enumerate({', '.join(args)}) */"

        if func_name == "zip":
            self._warn("zip() has no direct C++ equivalent — use index-based loop")
            return f"/* zip({', '.join(args)}) */"

        # ── input() ──────────────────────────────────────────────────────────
        if func_name == "input":
            self._includes.add("<iostream>")
            self._includes.add("<string>")
            if args:
                prompt = args[0]
                return (
                    f"([&](){{ std::string _s; "
                    f"std::cout << {prompt}; "
                    f"std::getline(std::cin, _s); return _s; }}())"
                )
            return (
                "([&](){ std::string _s; std::getline(std::cin, _s); return _s; }())"
            )

        # ── method calls ──────────────────────────────────────────────────────
        if isinstance(node.func, ast.Attribute):
            attr = node.func.attr
            obj = self._expr(node.func.value)

            if attr == "pop":
                if not args:
                    return (
                        f"([&](){{ auto _v = {obj}.back(); {obj}.pop_back(); return _v; }}())"
                    )
                else:
                    idx = args[0]
                    return (
                        f"([&](){{ auto _v = {obj}[{idx}]; "
                        f"{obj}.erase({obj}.begin() + {idx}); return _v; }}())"
                    )

            if attr == "sort":
                self._includes.add("<algorithm>")
                return f"std::sort({obj}.begin(), {obj}.end())"

            if attr == "reverse":
                self._includes.add("<algorithm>")
                return f"std::reverse({obj}.begin(), {obj}.end())"

            method_map = {
                "append":     f"{obj}.push_back({', '.join(args)})",
                "push_back":  f"{obj}.push_back({', '.join(args)})",
                "clear":      f"{obj}.clear()",
                "size":       f"{obj}.size()",
                "empty":      f"{obj}.empty()",
                "find":       f"{obj}.find({', '.join(args)})",
                "insert":     f"{obj}.insert({', '.join(args)})",
                "erase":      f"{obj}.erase({', '.join(args)})",
                "begin":      f"{obj}.begin()",
                "end":        f"{obj}.end()",
                "count":      (
                    f"std::count({obj}.begin(), {obj}.end(), {', '.join(args)})"
                    if args else f"{obj}.count()"
                ),
                "keys":       f"/* {obj}.keys() — iterate map directly */",
                "values":     f"/* {obj}.values() — iterate map directly */",
                "items":      f"/* {obj}.items() — iterate map directly */",
                "upper":      (
                    f"(std::transform({obj}.begin(), {obj}.end(), {obj}.begin(), ::toupper), {obj})"
                ),
                "lower":      (
                    f"(std::transform({obj}.begin(), {obj}.end(), {obj}.begin(), ::tolower), {obj})"
                ),
                "strip":      f"/* strip() — use boost::trim or manual impl */",
                "split":      f"/* split() — use std::istringstream or manual impl */",
                "join":       f"/* join() — use std::ostringstream */",
                "format":     f"/* .format() — use std::format (C++20) or sprintf */",
                "startswith": (
                    f"{obj}.substr(0, {args[0]}.size()) == {args[0]}"
                    if args else f"/* startswith() */"
                ),
                "endswith":   (
                    f"{obj}.substr({obj}.size() - {args[0]}.size()) == {args[0]}"
                    if args else f"/* endswith() */"
                ),
            }

            if attr in method_map:
                return method_map[attr]

        return f"{func_name}({', '.join(args)})"

    # ── statement visitors ─────────────────────────────────────────────────────

    def visit_Module(self, node: ast.Module) -> None:
        DEFINITION_TYPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        top_defs  = [c for c in node.body if     isinstance(c, DEFINITION_TYPES)]
        top_stmts = [c for c in node.body if not isinstance(c, DEFINITION_TYPES)]

        saved_lines  = self._lines
        saved_indent = self._indent

        # 1. Render function / class definitions at indent 0
        def_lines: list[str] = []
        self._lines  = def_lines
        self._indent = 0
        for child in top_defs:
            self.visit(child)

        # 2. Render top-level statements at indent 1 (inside main)
        stmt_lines: list[str] = []
        if top_stmts:
            outer_declared = self._declared.copy()
            self._lines  = stmt_lines
            self._indent = 1
            for child in top_stmts:
                self.visit(child)
            self._declared = outer_declared

        self._lines  = saved_lines
        self._indent = saved_indent

        # 3. Emit #includes
        for inc in sorted(self._includes):
            self._emit(f"#include {inc}")
        self._emit("")

        # 4. Emit function / class bodies at file scope
        self._lines.extend(def_lines)

        # 5. Wrap executable statements in int main() if any exist.
        if top_stmts:
            self._emit("int main() {")
            self._lines.extend(stmt_lines)
            self._emit("    return 0;")
            self._emit("}")
        elif any(isinstance(c, ast.ClassDef) for c in top_defs):
            self._emit("int main() {")
            self._emit("    // Auto-generated stub — add your own logic here")
            for cls in top_defs:
                if not isinstance(cls, ast.ClassDef):
                    continue
                cls_name = cls.name
                init_node = next(
                    (m for m in cls.body
                     if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
                     and m.name == "__init__"),
                    None
                )
                params = [a for a in init_node.args.args if a.arg != "self"] if init_node else []

                def _default_for(arg: ast.arg) -> str:
                    inferred = self._infer_member_type(arg.arg, None)
                    if inferred == "std::string":
                        return f'"{arg.arg}"'
                    if inferred == "bool":
                        return "true"
                    if inferred == "double":
                        return "0.0"
                    return "0"

                if not params:
                    self._emit(f"    {cls_name} obj;")
                else:
                    defaults = ", ".join(_default_for(p) for p in params)
                    self._emit(f"    {cls_name} obj({defaults});")
                    self._emit(f"    (void)obj;")
            self._emit("    return 0;")
            self._emit("}")

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        ret_type = self._return_type(node)
        params: list[str] = []
        args = node.args
        defaults_offset = len(args.args) - len(args.defaults)
        for i, arg in enumerate(args.args):
            cpp_type = self._annotation_to_cpp(arg.annotation) if arg.annotation else "auto"
            default_idx = i - defaults_offset
            if default_idx >= 0:
                default_val = self._expr(args.defaults[default_idx])
                params.append(f"{cpp_type} {arg.arg} = {default_val}")
            else:
                params.append(f"{cpp_type} {arg.arg}")

        param_str = ", ".join(params)
        self._emit(f"{ret_type} {node.name}({param_str}) {{")
        self._inc()
        outer_declared = self._declared.copy()
        for stmt in node.body:
            self.visit(stmt)
        self._declared = outer_declared
        self._dec()
        self._emit("}")
        self._emit("")

    visit_AsyncFunctionDef = visit_FunctionDef

    # ── NEW v1.4.0: Full class support ─────────────────────────────────────────

    def _collect_self_attrs(self, init_node: ast.FunctionDef) -> list[tuple[str, str]]:
        seen: set[str] = set()
        attrs: list[tuple[str, str]] = []
        for stmt in ast.walk(init_node):
            if not isinstance(stmt, (ast.Assign, ast.AnnAssign)):
                continue
            if isinstance(stmt, ast.Assign):
                for tgt in stmt.targets:
                    if (
                        isinstance(tgt, ast.Attribute)
                        and isinstance(tgt.value, ast.Name)
                        and tgt.value.id == "self"
                        and tgt.attr not in seen
                    ):
                        seen.add(tgt.attr)
                        cpp_type = self._infer_member_type(tgt.attr, stmt.value)
                        attrs.append((tgt.attr, cpp_type))
            elif isinstance(stmt, ast.AnnAssign):
                tgt = stmt.target
                if (
                    isinstance(tgt, ast.Attribute)
                    and isinstance(tgt.value, ast.Name)
                    and tgt.value.id == "self"
                    and tgt.attr not in seen
                ):
                    seen.add(tgt.attr)
                    cpp_type = self._annotation_to_cpp(stmt.annotation)
                    if cpp_type == "auto":
                        cpp_type = self._infer_member_type(tgt.attr, stmt.value)
                    attrs.append((tgt.attr, cpp_type))
        return attrs

    def _emit_constructor(self, class_name: str, init_node: ast.FunctionDef) -> None:
        args = init_node.args
        params: list[str] = []
        defaults_offset = len(args.args) - len(args.defaults)

        for i, arg in enumerate(args.args):
            if arg.arg == "self":
                continue
            if arg.annotation:
                cpp_type = self._annotation_to_cpp(arg.annotation)
            else:
                default_idx_tmp = i - defaults_offset
                default_node = args.defaults[default_idx_tmp] if 0 <= default_idx_tmp < len(args.defaults) else None
                cpp_type = self._infer_member_type(arg.arg, default_node)
            default_idx = i - defaults_offset
            if 0 <= default_idx < len(args.defaults):
                default_val = self._expr(args.defaults[default_idx])
                params.append(f"{cpp_type} {arg.arg} = {default_val}")
            else:
                params.append(f"{cpp_type} {arg.arg}")

        param_str = ", ".join(params)
        self._emit(f"{class_name}({param_str}) {{")
        self._inc()

        outer_declared = self._declared.copy()
        for stmt in init_node.body:
            if (
                isinstance(stmt, ast.Assign)
                and len(stmt.targets) == 1
                and isinstance(stmt.targets[0], ast.Attribute)
                and isinstance(stmt.targets[0].value, ast.Name)
                and stmt.targets[0].value.id == "self"
            ):
                attr = stmt.targets[0].attr
                val  = self._expr(stmt.value)
                self._emit(f"this->{attr} = {val};")
            elif (
                isinstance(stmt, ast.AnnAssign)
                and isinstance(stmt.target, ast.Attribute)
                and isinstance(stmt.target.value, ast.Name)
                and stmt.target.value.id == "self"
            ):
                attr = stmt.target.attr
                if stmt.value:
                    val = self._expr(stmt.value)
                    self._emit(f"this->{attr} = {val};")
            else:
                self.visit(stmt)

        self._declared = outer_declared
        self._dec()
        self._emit("}")
        self._emit("")

    def _emit_method(self, node: ast.FunctionDef) -> None:
        ret_type = self._return_type(node)
        args = node.args
        params: list[str] = []
        defaults_offset = len(args.args) - len(args.defaults)

        for i, arg in enumerate(args.args):
            if arg.arg == "self":
                continue
            if arg.annotation:
                cpp_type = self._annotation_to_cpp(arg.annotation)
            else:
                default_idx_tmp = i - defaults_offset
                default_node = args.defaults[default_idx_tmp] if 0 <= default_idx_tmp < len(args.defaults) else None
                cpp_type = self._infer_member_type(arg.arg, default_node)
            default_idx = i - defaults_offset
            if 0 <= default_idx < len(args.defaults):
                default_val = self._expr(args.defaults[default_idx])
                params.append(f"{cpp_type} {arg.arg} = {default_val}")
            else:
                params.append(f"{cpp_type} {arg.arg}")

        param_str = ", ".join(params)
        self._emit(f"{ret_type} {node.name}({param_str}) {{")
        self._inc()

        outer_declared = self._declared.copy()
        for stmt in node.body:
            self.visit(stmt)
        self._declared = outer_declared

        self._dec()
        self._emit("}")
        self._emit("")

    def visit_ClassDef(self, node: ast.ClassDef) -> None:   # noqa: C901
        if node.bases:
            base_list = ", ".join(f"public {self._expr(b)}" for b in node.bases)
            self._emit(f"class {node.name} : {base_list} {{")
        else:
            self._emit(f"class {node.name} {{")

        self._emit("public:")
        self._inc()

        init_node: ast.FunctionDef | None = None
        other_methods: list[ast.FunctionDef] = []
        other_stmts: list[ast.stmt] = []

        for stmt in node.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if stmt.name == "__init__":
                    init_node = stmt
                else:
                    other_methods.append(stmt)
            elif isinstance(stmt, ast.Pass):
                pass  # skip — empty body placeholder
            else:
                other_stmts.append(stmt)

        if init_node:
            attrs = self._collect_self_attrs(init_node)
            if attrs:
                self._emit("// --- member variables ---")
                for attr_name, cpp_type in attrs:
                    self._emit(f"{cpp_type} {attr_name};")
                self._emit("")

        for stmt in other_stmts:
            self._warn(
                f"Class-level statement '{type(stmt).__name__}' has no direct C++ "
                f"equivalent as a class member — moved to comment."
            )
            self._emit(f"// [unsupported class-level stmt: {type(stmt).__name__}]")

        if init_node:
            self._emit("// --- constructor ---")
            self._emit_constructor(node.name, init_node)

        if other_methods:
            self._emit("// --- methods ---")
        for method in other_methods:
            _SelfRewriter().visit(method)
            self._emit_method(method)

        self._dec()
        self._emit("};")
        self._emit("")

    def visit_Return(self, node: ast.Return) -> None:
        val = self._expr(node.value) if node.value else ""
        self._emit(f"return {val};")

    def visit_Assign(self, node: ast.Assign) -> None:
        def _assign_single(target: ast.expr, val_expr: str) -> None:
            if isinstance(target, ast.Name):
                name = target.id
                if name.startswith("this->"):
                    self._emit(f"{name} = {val_expr};")
                elif name in self._declared:
                    self._emit(f"{name} = {val_expr};")
                else:
                    cpp_type = self._infer_cpp_type(node.value)
                    self._emit(f"{cpp_type} {name} = {val_expr};")
                    self._declared.add(name)
            elif isinstance(target, (ast.Subscript, ast.Attribute)):
                self._emit(f"{self._expr(target)} = {val_expr};")
            else:
                self._warn(f"Unsupported assignment target: {type(target).__name__}")
                self._emit(f"/* {self._expr(target)} = {val_expr}; */")

        if (
            len(node.targets) == 1
            and isinstance(node.targets[0], ast.Tuple)
        ):
            lhs_elts = node.targets[0].elts

            if isinstance(node.value, ast.Tuple) and len(node.value.elts) == len(lhs_elts):
                rhs_elts = node.value.elts

                if len(lhs_elts) == 2:
                    l0 = self._expr(lhs_elts[0])
                    l1 = self._expr(lhs_elts[1])
                    r0 = self._expr(rhs_elts[0])
                    r1 = self._expr(rhs_elts[1])
                    if l0 == r1 and l1 == r0:
                        self._includes.add("<algorithm>")
                        self._emit(f"std::swap({l0}, {l1});")
                        return

                tmp_names: list[str] = []
                for i, rhs_elt in enumerate(rhs_elts):
                    tmp = f"_t{i}_"
                    self._emit(f"auto {tmp} = {self._expr(rhs_elt)};")
                    tmp_names.append(tmp)
                for lhs_elt, tmp in zip(lhs_elts, tmp_names):
                    if isinstance(lhs_elt, ast.Name):
                        name = lhs_elt.id
                        if name in self._declared:
                            self._emit(f"{name} = {tmp};")
                        else:
                            self._emit(f"auto {name} = {tmp};")
                            self._declared.add(name)
                    else:
                        self._emit(f"{self._expr(lhs_elt)} = {tmp};")
                return

            val_str = self._expr(node.value)
            self._warn("Tuple unpacking from non-tuple RHS — partial support")
            for i, lhs_elt in enumerate(lhs_elts):
                if isinstance(lhs_elt, ast.Name):
                    name = lhs_elt.id
                    if name not in self._declared:
                        self._emit(f"auto {name} = std::get<{i}>({val_str});")
                        self._declared.add(name)
                    else:
                        self._emit(f"{name} = std::get<{i}>({val_str});")
                else:
                    self._emit(f"{self._expr(lhs_elt)} = std::get<{i}>({val_str});")
            return

        if len(node.targets) > 1:
            val_str = self._expr(node.value)
            for t in node.targets:
                _assign_single(t, val_str)
            return

        _assign_single(node.targets[0], self._expr(node.value))

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        cpp_type = self._annotation_to_cpp(node.annotation)
        name = self._expr(node.target)
        if name.startswith("this->"):
            if node.value:
                val = self._expr(node.value)
                self._emit(f"{name} = {val};")
        elif node.value:
            val = self._expr(node.value)
            self._emit(f"{cpp_type} {name} = {val};")
            if isinstance(node.target, ast.Name):
                self._declared.add(node.target.id)
        else:
            self._emit(f"{cpp_type} {name};")
            if isinstance(node.target, ast.Name):
                self._declared.add(node.target.id)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        op_type = type(node.op)
        target = self._expr(node.target)
        val = self._expr(node.value)
        if op_type == ast.Pow:
            self._includes.add("<cmath>")
            self._emit(f"{target} = std::pow({target}, {val});")
        else:
            op = BINOP_MAP.get(op_type, "?")
            self._emit(f"{target} {op}= {val};")

    def visit_Expr(self, node: ast.Expr) -> None:
        expr_str = self._expr(node.value)
        if expr_str and not expr_str.startswith("/*"):
            self._emit(f"{expr_str};")
        elif expr_str:
            self._emit(expr_str)

    def visit_If(self, node: ast.If) -> None:
        test = self._expr(node.test)
        self._emit(f"if ({test}) {{")
        self._inc()
        for stmt in node.body:
            self.visit(stmt)
        self._dec()

        orelse = node.orelse
        while orelse:
            if len(orelse) == 1 and isinstance(orelse[0], ast.If):
                inner = orelse[0]
                test = self._expr(inner.test)
                self._emit(f"}} else if ({test}) {{")
                self._inc()
                for stmt in inner.body:
                    self.visit(stmt)
                self._dec()
                orelse = inner.orelse
            else:
                self._emit("} else {")
                self._inc()
                for stmt in orelse:
                    self.visit(stmt)
                self._dec()
                orelse = []
        self._emit("}")

    def visit_For(self, node: ast.For) -> None:
        target = self._expr(node.target)

        if (
            isinstance(node.iter, ast.Call)
            and isinstance(node.iter.func, ast.Name)
            and node.iter.func.id == "range"
        ):
            range_args = [self._expr(a) for a in node.iter.args]
            if len(range_args) == 1:
                self._emit(f"for (int {target} = 0; {target} < {range_args[0]}; ++{target}) {{")
            elif len(range_args) == 2:
                self._emit(
                    f"for (int {target} = {range_args[0]}; "
                    f"{target} < {range_args[1]}; ++{target}) {{"
                )
            elif len(range_args) == 3:
                step = range_args[2]
                op = "<" if not step.startswith("-") else ">"
                self._emit(
                    f"for (int {target} = {range_args[0]}; "
                    f"{target} {op} {range_args[1]}; {target} += {step}) {{"
                )
        else:
            iterable = self._expr(node.iter)
            self._emit(f"for (auto& {target} : {iterable}) {{")

        self._inc()
        for stmt in node.body:
            self.visit(stmt)
        self._dec()
        self._emit("}")
        if node.orelse:
            self._warn("for-else is not natively supported in C++")

    def visit_While(self, node: ast.While) -> None:
        test = self._expr(node.test)
        self._emit(f"while ({test}) {{")
        self._inc()
        for stmt in node.body:
            self.visit(stmt)
        self._dec()
        self._emit("}")

    def visit_Break(self, node: ast.Break) -> None:
        self._emit("break;")

    def visit_Continue(self, node: ast.Continue) -> None:
        self._emit("continue;")

    def visit_Pass(self, node: ast.Pass) -> None:
        self._emit("// pass")

    def visit_Delete(self, node: ast.Delete) -> None:
        for t in node.targets:
            self._emit(f"// del {self._expr(t)}")

    def visit_Global(self, node: ast.Global) -> None:
        for name in node.names:
            self._emit(f"// global {name}  (use extern in C++)")

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        for name in node.names:
            self._emit(f"// nonlocal {name}  (capture by reference in lambda)")

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self._emit(f"// import {alias.name}  — add the equivalent C++ header manually")

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        names = ", ".join(a.name for a in node.names)
        self._emit(f"// from {node.module} import {names}  — add equivalent C++ header manually")

    def visit_Assert(self, node: ast.Assert) -> None:
        self._includes.add("<cassert>")
        test = self._expr(node.test)
        self._emit(f"assert({test});")

    def visit_Raise(self, node: ast.Raise) -> None:
        self._includes.add("<stdexcept>")
        if node.exc:
            exc = self._expr(node.exc)
            self._emit(f"throw std::runtime_error({exc});")
        else:
            self._emit("throw;")

    def visit_Try(self, node: ast.Try) -> None:
        self._includes.add("<stdexcept>")
        self._emit("try {")
        self._inc()
        for stmt in node.body:
            self.visit(stmt)
        self._dec()
        for handler in node.handlers:
            exc_type = (
                "std::exception"
                if handler.type is None
                else f"/* {self._expr(handler.type)} */"
            )
            var = f" const& {handler.name}" if handler.name else ""
            self._emit(f"}} catch ({exc_type}{var}) {{")
            self._inc()
            for stmt in handler.body:
                self.visit(stmt)
            self._dec()
        if node.finalbody:
            self._emit("}")
            self._emit("// finally {")
            self._inc()
            for stmt in node.finalbody:
                self.visit(stmt)
            self._dec()
            self._emit("// }")
        else:
            self._emit("}")

    def visit_With(self, node: ast.With) -> None:
        self._warn("with-statement has no direct C++ equivalent — consider RAII")
        self._emit("{  // with-block")
        self._inc()
        for stmt in node.body:
            self.visit(stmt)
        self._dec()
        self._emit("}")

    def generic_visit(self, node: ast.AST) -> None:
        if isinstance(node, ast.stmt):
            self._warn(f"Statement not fully supported: {type(node).__name__}")
        super().generic_visit(node)

    # ── public API ─────────────────────────────────────────────────────────────

    def transpile(self, source: str) -> dict:
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            return {
                "cpp_code": "",
                "warnings": [],
                "success": False,
                "error": f"Python SyntaxError at line {exc.lineno}: {exc.msg}",
            }

        try:
            self.visit(tree)
        except Exception as exc:           # safety net — should never trigger
            logger.exception("Unexpected error during AST traversal")
            return {
                "cpp_code": "\n".join(self._lines),
                "warnings": self._warnings,
                "success": False,
                "error": f"Internal transpiler error: {exc}",
            }

        cpp_code = "\n".join(self._lines)
        return {
            "cpp_code": cpp_code,
            "warnings": self._warnings,
            "success": True,
            "error": None,
        }


# ══════════════════════════════════════════════════════════════════════════════
#  AST helper: rewrite self.attr → this->attr inside method bodies
# ══════════════════════════════════════════════════════════════════════════════

class _SelfRewriter(ast.NodeTransformer):
    """
    Transforms `self.attr` accesses into a synthetic Name node whose id is
    `this->attr` so that _expr() can render it verbatim.
    """

    def visit_Attribute(self, node: ast.Attribute) -> ast.AST:
        if (
            isinstance(node.value, ast.Name)
            and node.value.id == "self"
        ):
            new_node = ast.Name(id=f"this->{node.attr}", ctx=node.ctx)
            return ast.copy_location(new_node, node)
        return self.generic_visit(node)


# ══════════════════════════════════════════════════════════════════════════════
#  Routes
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/", methods=["GET"])
def health_check():
    return jsonify({"status": "ok", "service": "Astmize API", "version": "2.0.0", "engine": "AI (OpenRouter)"})


@app.route("/convert", methods=["POST"])
@rate_limit("60 per minute")
def convert():
    """
    AI-powered Python → C++ conversion via Qwen3 Coder (OpenRouter).

    Accepts:  { "python_code": "..." }
    Returns:  { "success": bool, "cpp_code": str, "warnings": [], "error": str|null }

    The response shape is identical to the old AST route so the frontend
    requires zero changes.
    """
    if not GEMINI_API_KEY:
        return jsonify({
            "success": False,
            "cpp_code": "",
            "warnings": [],
            "error": (
                "GEMINI_API_KEY is not configured. "
                "Add it as an Environment Variable in your Render dashboard."
            ),
        }), 503

    payload = request.get_json(silent=True)
    if not payload or "python_code" not in payload:
        return jsonify({
            "success": False,
            "error": "Request body must be JSON with a 'python_code' key.",
            "cpp_code": "", "warnings": [],
        }), 400

    python_code: str = payload["python_code"].strip()
    if not python_code:
        return jsonify({
            "success": False,
            "error": "The 'python_code' field is empty.",
            "cpp_code": "", "warnings": [],
        }), 400

    if len(python_code) > 100_000:
        return jsonify({
            "success": False,
            "error": "Code payload exceeds the 100 KB limit.",
            "cpp_code": "", "warnings": [],
        }), 413

    logger.info("Received AI conversion request (%d chars)", len(python_code))

    prompt = f"""You are an expert C++ developer and Python expert. Convert the following Python code to clean, idiomatic C++17.

Rules:
- Output ONLY a JSON object, no markdown, no backticks, no preamble.
- The JSON must have exactly these keys:
    "cpp_code"  : the full, compilable C++ source as a single string
    "warnings"  : a JSON array of strings for any translation caveats (empty array if none)
- Include all necessary #include headers at the top.
- Use std::string, std::vector, std::map, std::cout, etc. as appropriate.
- Replace print() with std::cout.
- Preserve all logic exactly — do NOT add extra features.
- If any construct cannot be translated cleanly, add a brief comment in the C++ code explaining why.

Python code to convert:
{python_code}"""

    # ── Model fallback chain ────────────────────────────────────────────────────
    # Try each free model in order; skip to the next on 429 (rate-limit).
    MODELS = [
        "qwen/qwen3-coder:free",
        "deepseek/deepseek-chat-v3-0324:free",
        "meta-llama/llama-3.3-70b-instruct:free",
    ]

    response = None
    last_error: str = ""

    for model in MODELS:
        try:
            logger.info("Trying model: %s", model)
            resp = http_requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {GEMINI_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://astmize.onrender.com",
                    "X-Title": "Astmize",
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                },
                timeout=60,
            )

            if resp.status_code == 429:
                logger.warning("Model %s returned 429 — trying next model", model)
                last_error = f"Model {model} rate-limited (429)"
                continue  # try next model

            resp.raise_for_status()
            response = resp
            logger.info("Model %s accepted the request", model)
            break  # success

        except http_requests.exceptions.Timeout:
            logger.error("Model %s timed out — trying next", model)
            last_error = f"Model {model} timed out"
            continue
        except http_requests.exceptions.RequestException as exc:
            logger.error("Model %s request error: %s", model, exc)
            last_error = str(exc)
            break  # non-429 network error

    if response is None:
        return jsonify({
            "success": False,
            "cpp_code": "",
            "warnings": [],
            "error": (
                "All AI models are currently rate-limited or unavailable. "
                "Please wait a moment and try again. "
                f"(Last error: {last_error})"
            ),
        }), 502

    try:
        raw_text = response.json()["choices"][0]["message"]["content"]

        # Strip <think>...</think> blocks emitted by reasoning models
        clean = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL).strip()

        # Strip any residual markdown fences
        clean = re.sub(r"^```(?:json)?\s*", "", clean, flags=re.IGNORECASE)
        clean = re.sub(r"\s*```$", "", clean).strip()

        parsed = json.loads(clean)
        cpp_code = parsed.get("cpp_code", "").strip()
        warnings = parsed.get("warnings", [])

        if not isinstance(warnings, list):
            warnings = [str(warnings)] if warnings else []
        else:
            warnings = [str(w) for w in warnings]

        if not cpp_code:
            raise ValueError("Model returned an empty cpp_code field.")

    except (json.JSONDecodeError, ValueError, KeyError, IndexError) as exc:
        logger.error("Failed to parse AI convert response: %s | raw: %.300s", exc, raw_text)
        return jsonify({
            "success": False,
            "cpp_code": "",
            "warnings": [],
            "error": "Failed to parse AI response. Please try again.",
        }), 500

    logger.info("AI conversion successful (%d chars output, %d warnings)", len(cpp_code), len(warnings))
    return jsonify({
        "success": True,
        "cpp_code": cpp_code,
        "warnings": warnings,
        "error": None,
    }), 200


# ══════════════════════════════════════════════════════════════════════════════
#  /enhance  — AI-powered C++ improvement via Qwen3 Coder (OpenRouter)
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/enhance", methods=["POST"])
@rate_limit("20 per minute")
def enhance():
    """
    Accepts transpiled C++ code and returns an AI-improved version via Qwen3 Coder.

    Request body (JSON):
        { "cpp_code": "..." }

    Response (JSON):
        {
            "success": true,
            "enhanced_code": "...",
            "explanation": "...",
            "error": null
        }
    """
    if not GEMINI_API_KEY:
        return jsonify({
            "success": False,
            "enhanced_code": "",
            "explanation": "",
            "error": "GEMINI_API_KEY is not configured. Add it in your Render environment variables.",
        }), 503

    payload = request.get_json(silent=True)
    if not payload or "cpp_code" not in payload:
        return jsonify({
            "success": False,
            "enhanced_code": "",
            "explanation": "",
            "error": "Request body must be JSON with a 'cpp_code' key.",
        }), 400

    cpp_code: str = payload["cpp_code"].strip()
    if not cpp_code:
        return jsonify({
            "success": False,
            "enhanced_code": "",
            "explanation": "",
            "error": "The 'cpp_code' field is empty.",
        }), 400

    if len(cpp_code) > 50_000:
        return jsonify({
            "success": False,
            "enhanced_code": "",
            "explanation": "",
            "error": "Code payload exceeds the 50 KB limit.",
        }), 413

    prompt = f"""You are an expert C++ developer. The following C++ code was automatically transpiled from Python.
Your job is to improve it: fix any issues, use idiomatic modern C++17, improve variable names if needed, and remove redundant comments.

Return ONLY a JSON object in this exact format (no markdown, no backticks):
{{
  "enhanced_code": "<the full improved C++ code here>",
  "explanation": "<a short explanation in 2-3 sentences of what you improved>"
}}

C++ code to improve:
{cpp_code}"""

    logger.info("Sending enhance request to OpenRouter (%d chars)", len(cpp_code))

    try:
        response = http_requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GEMINI_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://astmize.onrender.com",
                "X-Title": "Astmize",
            },
            json={
                "model": "qwen/qwen3-coder:free",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
            },
            timeout=30,
        )
        response.raise_for_status()
    except http_requests.exceptions.Timeout:
        logger.error("OpenRouter request timed out")
        return jsonify({
            "success": False,
            "enhanced_code": "",
            "explanation": "",
            "error": "AI service timed out. Please try again.",
        }), 504
    except http_requests.exceptions.RequestException as exc:
        logger.error("OpenRouter request failed: %s", exc)
        return jsonify({
            "success": False,
            "enhanced_code": "",
            "explanation": "",
            "error": f"AI service unavailable: {exc}",
        }), 502

    try:
        raw_text = response.json()["choices"][0]["message"]["content"]
        # Strip <think>...</think> blocks emitted by reasoning models (e.g. Qwen3)
        clean = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL).strip()
        # Strip any residual markdown fences
        clean = clean.lstrip("```json").lstrip("```").rstrip("```").strip()
        parsed = json.loads(clean)
        enhanced_code = parsed.get("enhanced_code", "")
        explanation   = parsed.get("explanation", "")
    except Exception as exc:
        logger.error("Failed to parse model response: %s", exc)
        return jsonify({
            "success": False,
            "enhanced_code": "",
            "explanation": "",
            "error": "Failed to parse AI response. Please try again.",
        }), 500

    logger.info("Enhancement successful (%d chars output)", len(enhanced_code))
    return jsonify({
        "success": True,
        "enhanced_code": enhanced_code,
        "explanation": explanation,
        "error": None,
    }), 200


# ── Rate-limit error handler ───────────────────────────────────────────────────
if _LIMITER_AVAILABLE:
    from flask_limiter.errors import RateLimitExceeded

    @app.errorhandler(RateLimitExceeded)
    def handle_rate_limit(e):
        logger.warning("Rate limit exceeded from %s", request.remote_addr)
        return jsonify({
            "success": False,
            "error": "Too many requests — you are sending more than 60 requests per minute. "
                     "Please slow down.",
            "cpp_code": "",
            "warnings": [],
        }), 429


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    logger.info("Starting Astmize API on port %d  (debug=%s)", port, debug)
    app.run(host="0.0.0.0", port=port, debug=debug)
