"""
Astmize — Python → C++ AST Transpiler Backend
Flask API server with baseline AST-driven translation engine.
"""

import ast
import os
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
logger = logging.getLogger(__name__)

# ── App bootstrap ──────────────────────────────────────────────────────────────
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Future AI/LLM integration key — set via Render environment variable
API_KEY: str | None = os.getenv("API_KEY")


# ══════════════════════════════════════════════════════════════════════════════
#  AST → C++ translation engine
# ══════════════════════════════════════════════════════════════════════════════

# Python built-in → C++ type mapping
PYTHON_TYPE_MAP: dict[str, str] = {
    "int":   "int",
    "float": "double",
    "str":   "std::string",
    "bool":  "bool",
    "list":  "std::vector<auto>",
    "dict":  "std::map<std::string, auto>",
    "None":  "void",
}

# Python operator → C++ operator mapping
BINOP_MAP: dict[type, str] = {
    ast.Add:      "+",
    ast.Sub:      "-",
    ast.Mult:     "*",
    ast.Div:      "/",
    ast.Mod:      "%",
    ast.Pow:      "/* pow */ std::pow",
    ast.FloorDiv: "/",
    ast.BitAnd:   "&",
    ast.BitOr:    "|",
    ast.BitXor:   "^",
    ast.LShift:   "<<",
    ast.RShift:   ">>",
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

    Supported constructs
    ────────────────────
    • Module-level variable assignments  (int / double / bool / str)
    • Function definitions with typed / untyped parameters
    • Return statements
    • For-range loops  (for i in range(...))
    • While loops
    • If / elif / else blocks
    • Augmented assignments  (+=, -=, *=, /=)
    • Annotated assignments  (x: int = 5)
    • Print calls → std::cout
    • Basic expressions: BinOp, Compare, BoolOp, UnaryOp, IfExp (ternary)
    """

    def __init__(self) -> None:
        self._lines: list[str] = []
        self._indent: int = 0
        self._includes: set[str] = {"<iostream>", "<string>"}
        self._warnings: list[str] = []

    # ── helpers ────────────────────────────────────────────────────────────────

    def _emit(self, line: str) -> None:
        self._lines.append("    " * self._indent + line)

    def _warn(self, msg: str) -> None:
        self._warnings.append(f"// [Astmize warning] {msg}")

    @property
    def indent(self) -> int:
        return self._indent

    def _inc(self) -> None:
        self._indent += 1

    def _dec(self) -> None:
        self._indent = max(0, self._indent - 1)

    def _infer_cpp_type(self, node: ast.expr) -> str:
        """Infer a C++ type from a value node."""
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
            return "std::vector<auto>"
        if isinstance(node, ast.Dict):
            self._includes.add("<map>")
            return "std::map<std::string, auto>"
        return "auto"

    def _annotation_to_cpp(self, annotation: ast.expr | None) -> str:
        if annotation is None:
            return "auto"
        if isinstance(annotation, ast.Name):
            return PYTHON_TYPE_MAP.get(annotation.id, "auto")
        if isinstance(annotation, ast.Attribute):
            return "auto"
        if isinstance(annotation, ast.Subscript):
            # e.g. list[int] → std::vector<int>
            outer = self._annotation_to_cpp(annotation.value)
            inner = self._annotation_to_cpp(annotation.slice)
            if "vector" in outer:
                self._includes.add("<vector>")
                return f"std::vector<{inner}>"
            if "map" in outer:
                self._includes.add("<map>")
                return f"std::map<std::string, {inner}>"
        return "auto"

    def _return_type(self, func_node: ast.FunctionDef) -> str:
        if func_node.returns:
            t = self._annotation_to_cpp(func_node.returns)
            return t
        # Heuristic: scan body for return statements
        for node in ast.walk(func_node):
            if isinstance(node, ast.Return) and node.value is not None:
                return self._infer_cpp_type(node.value)
        return "void"

    # ── expression emitter ─────────────────────────────────────────────────────

    def _expr(self, node: ast.expr) -> str:  # noqa: C901
        """Recursively render an expression node as a C++ string."""
        if isinstance(node, ast.Constant):
            if isinstance(node.value, str):
                escaped = node.value.replace("\\", "\\\\").replace('"', '\\"')
                return f'"{escaped}"'
            if isinstance(node.value, bool):
                return "true" if node.value else "false"
            if node.value is None:
                return "nullptr"
            return str(node.value)

        if isinstance(node, ast.Name):
            return node.id

        if isinstance(node, ast.BinOp):
            op = BINOP_MAP.get(type(node.op), "?")
            left = self._expr(node.left)
            right = self._expr(node.right)
            if isinstance(node.op, ast.Pow):
                self._includes.add("<cmath>")
                return f"std::pow({left}, {right})"
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
                parts.append(f"{left} {op} {self._expr(comparator)}")
                left = self._expr(comparator)
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

        self._warn(f"Unsupported expression type: {type(node).__name__}")
        return f"/* {type(node).__name__} */"

    def _call_expr(self, node: ast.Call) -> str:
        """Translate a Python call expression."""
        func_name = ""
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = f"{self._expr(node.func.value)}.{node.func.attr}"

        args = [self._expr(a) for a in node.args]

        # ── stdlib mappings ──────────────────────────────────────────────────
        if func_name == "print":
            self._includes.add("<iostream>")
            parts = " << ".join(args)
            return f'std::cout << {parts} << "\\n"'

        if func_name == "len":
            return f"{args[0]}.size()"

        if func_name in ("int", "float", "str", "bool"):
            cpp_cast = PYTHON_TYPE_MAP.get(func_name, func_name)
            return f"static_cast<{cpp_cast}>({args[0]})" if args else f"{cpp_cast}()"

        if func_name == "range":
            # Range itself doesn't emit code; handled in for-loop visitor
            return f"range({', '.join(args)})"

        if func_name in ("abs", "sqrt", "ceil", "floor"):
            self._includes.add("<cmath>")
            return f"std::{func_name}({', '.join(args)})"

        if func_name == "max":
            self._includes.add("<algorithm>")
            return f"std::max({', '.join(args)})"

        if func_name == "min":
            self._includes.add("<algorithm>")
            return f"std::min({', '.join(args)})"

        if func_name == "append" or (isinstance(node.func, ast.Attribute) and node.func.attr == "append"):
            obj = self._expr(node.func.value) if isinstance(node.func, ast.Attribute) else "vec"
            return f"{obj}.push_back({', '.join(args)})"

        return f"{func_name}({', '.join(args)})"

    # ── statement visitors ─────────────────────────────────────────────────────

    def visit_Module(self, node: ast.Module) -> None:
        # Collect body first, then prepend includes
        body_lines: list[str] = []
        saved = self._lines
        self._lines = body_lines
        self.generic_visit(node)
        self._lines = saved

        # Build header
        includes = sorted(self._includes)
        for inc in includes:
            self._emit(f"#include {inc}")
        self._emit("")
        self._lines.extend(body_lines)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        ret_type = self._return_type(node)

        # Build parameter list
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
        for stmt in node.body:
            self.visit(stmt)
        self._dec()
        self._emit("}")
        self._emit("")

    visit_AsyncFunctionDef = visit_FunctionDef  # best-effort

    def visit_Return(self, node: ast.Return) -> None:
        val = self._expr(node.value) if node.value else ""
        self._emit(f"return {val};")

    def visit_Assign(self, node: ast.Assign) -> None:
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            cpp_type = self._infer_cpp_type(node.value)
            val = self._expr(node.value)
            self._emit(f"{cpp_type} {name} = {val};")
        else:
            # Multi-target or complex: emit as comment + raw
            self._warn("Multi-target assignment partially supported")
            val = self._expr(node.value)
            for t in node.targets:
                self._emit(f"auto {self._expr(t)} = {val};")

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        cpp_type = self._annotation_to_cpp(node.annotation)
        name = self._expr(node.target)
        if node.value:
            val = self._expr(node.value)
            self._emit(f"{cpp_type} {name} = {val};")
        else:
            self._emit(f"{cpp_type} {name};")

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        op = BINOP_MAP.get(type(node.op), "?").strip()
        target = self._expr(node.target)
        val = self._expr(node.value)
        self._emit(f"{target} {op}= {val};")

    def visit_Expr(self, node: ast.Expr) -> None:
        expr_str = self._expr(node.value)
        self._emit(f"{expr_str};")

    def visit_If(self, node: ast.If) -> None:
        test = self._expr(node.test)
        self._emit(f"if ({test}) {{")
        self._inc()
        for stmt in node.body:
            self.visit(stmt)
        self._dec()

        # Handle elif / else chains
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

        # Pattern: for i in range(...)
        if (
            isinstance(node.iter, ast.Call)
            and isinstance(node.iter.func, ast.Name)
            and node.iter.func.id == "range"
        ):
            range_args = [self._expr(a) for a in node.iter.args]
            if len(range_args) == 1:
                self._emit(f"for (int {target} = 0; {target} < {range_args[0]}; ++{target}) {{")
            elif len(range_args) == 2:
                self._emit(f"for (int {target} = {range_args[0]}; {target} < {range_args[1]}; ++{target}) {{")
            elif len(range_args) == 3:
                step = range_args[2]
                op = "<" if not step.startswith("-") else ">"
                self._emit(f"for (int {target} = {range_args[0]}; {target} {op} {range_args[1]}; {target} += {step}) {{")
        else:
            # Ranged-for over a container
            iterable = self._expr(node.iter)
            self._emit(f"for (auto& {target} : {iterable}) {{")

        self._inc()
        for stmt in node.body:
            self.visit(stmt)
        self._dec()
        self._emit("}")

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

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self._emit(f"// import {alias.name}  — add the equivalent C++ header manually")

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        names = ", ".join(a.name for a in node.names)
        self._emit(f"// from {node.module} import {names}  — add equivalent C++ header manually")

    # Fallback for unsupported nodes
    def generic_visit(self, node: ast.AST) -> None:
        if isinstance(node, ast.stmt):
            self._warn(f"Statement not fully supported: {type(node).__name__}")
        super().generic_visit(node)

    # ── public API ─────────────────────────────────────────────────────────────

    def transpile(self, source: str) -> dict:
        """
        Parse *source* and return a dict with keys:
            cpp_code  : translated C++ source string
            warnings  : list of warning strings
            success   : bool
            error     : str | None
        """
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            return {
                "cpp_code": "",
                "warnings": [],
                "success": False,
                "error": f"Python SyntaxError at line {exc.lineno}: {exc.msg}",
            }

        self.visit(tree)

        cpp_code = "\n".join(self._lines)
        return {
            "cpp_code": cpp_code,
            "warnings": self._warnings,
            "success": True,
            "error": None,
        }


# ══════════════════════════════════════════════════════════════════════════════
#  Routes
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/", methods=["GET"])
def health_check():
    return jsonify({
        "status": "ok",
        "service": "Astmize API",
        "version": "1.0.0",
    })


@app.route("/convert", methods=["POST"])
def convert():
    """
    POST /convert
    Body  : { "python_code": "<source>" }
    Returns:
    {
        "cpp_code"  : "<translated C++ source>",
        "warnings"  : ["..."],
        "success"   : true | false,
        "error"     : null | "<message>"
    }
    """
    payload = request.get_json(silent=True)

    if not payload or "python_code" not in payload:
        return jsonify({
            "success": False,
            "error": "Request body must be JSON with a 'python_code' key.",
            "cpp_code": "",
            "warnings": [],
        }), 400

    python_code: str = payload["python_code"].strip()

    if not python_code:
        return jsonify({
            "success": False,
            "error": "The 'python_code' field is empty.",
            "cpp_code": "",
            "warnings": [],
        }), 400

    logger.info("Received conversion request (%d chars)", len(python_code))

    # ── Future hook: swap in an LLM call here using API_KEY ──────────────────
    # if API_KEY:
    #     result = llm_transpile(python_code, api_key=API_KEY)
    # else:
    #     result = CppTranspiler().transpile(python_code)
    # ─────────────────────────────────────────────────────────────────────────

    transpiler = CppTranspiler()
    result = transpiler.transpile(python_code)

    status_code = 200 if result["success"] else 422
    logger.info("Conversion %s — %d warnings", "OK" if result["success"] else "FAILED", len(result["warnings"]))

    return jsonify(result), status_code


# ══════════════════════════════════════════════════════════════════════════════
#  Entry point (local dev only — Render uses gunicorn)
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    logger.info("Starting Astmize API on port %d  (debug=%s)", port, debug)
    app.run(host="0.0.0.0", port=port, debug=debug)
