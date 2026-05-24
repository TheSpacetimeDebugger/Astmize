"""
Astmize — Python → C++ AST Transpiler Backend  v1.1.0
Flask API server with baseline AST-driven translation engine.

Fixes in v1.1.0:
  - print() with multiple args now emits correct  std::cout << a << " " << b << "\n";
  - print() with sep/end kwargs is now handled
  - f-strings are partially translated (variables interpolated)
  - List/dict/set comprehensions emit a warning instead of crashing
  - HTML chars in string literals are never injected into the output stream
  - visit_Expr correctly detects a print-call and wraps it as a statement
  - Unsupported expression types no longer silently produce blank lines
  - Added visit_ClassDef stub with a helpful comment
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

API_KEY: str | None = os.getenv("API_KEY")


# ══════════════════════════════════════════════════════════════════════════════
#  AST → C++ translation engine
# ══════════════════════════════════════════════════════════════════════════════

PYTHON_TYPE_MAP: dict[str, str] = {
    "int":   "int",
    "float": "double",
    "str":   "std::string",
    "bool":  "bool",
    "list":  "std::vector<auto>",
    "dict":  "std::map<std::string, auto>",
    "set":   "std::set<auto>",
    "None":  "void",
}

BINOP_MAP: dict[type, str] = {
    ast.Add:      "+",
    ast.Sub:      "-",
    ast.Mult:     "*",
    ast.Div:      "/",
    ast.Mod:      "%",
    ast.Pow:      "pow",   # handled specially
    ast.FloorDiv: "/",
    ast.BitAnd:   "&",
    ast.BitOr:    "|",
    ast.BitXor:   "^",
    ast.LShift:   "<<",
    ast.RShift:   ">>",
    ast.MatMult:  "*",     # best-effort
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
        # Track declared variable names to avoid re-declaring with a type
        self._declared: set[str] = set()

    # ── helpers ────────────────────────────────────────────────────────────────

    def _emit(self, line: str) -> None:
        self._lines.append("    " * self._indent + line)

    def _warn(self, msg: str) -> None:
        self._warnings.append(msg)
        self._emit(f"// [Astmize warning] {msg}")

    def _inc(self) -> None:
        self._indent += 1

    def _dec(self) -> None:
        self._indent = max(0, self._indent - 1)

    def _infer_cpp_type(self, node: ast.expr) -> str:
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
        if isinstance(node, ast.Set):
            self._includes.add("<set>")
            return "std::set<auto>"
        return "auto"

    def _annotation_to_cpp(self, annotation: ast.expr | None) -> str:
        if annotation is None:
            return "auto"
        if isinstance(annotation, ast.Name):
            return PYTHON_TYPE_MAP.get(annotation.id, "auto")
        if isinstance(annotation, ast.Attribute):
            return "auto"
        if isinstance(annotation, ast.Subscript):
            outer = self._annotation_to_cpp(annotation.value)
            inner = self._annotation_to_cpp(annotation.slice)
            if "vector" in outer:
                self._includes.add("<vector>")
                return f"std::vector<{inner}>"
            if "map" in outer:
                self._includes.add("<map>")
                return f"std::map<std::string, {inner}>"
            if "set" in outer:
                self._includes.add("<set>")
                return f"std::set<{inner}>"
            if "optional" in outer.lower():
                self._includes.add("<optional>")
                return f"std::optional<{inner}>"
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
        if isinstance(node, ast.Constant):
            if isinstance(node.value, str):
                # Properly escape the string — never inject raw HTML chars
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
            left = self._expr(node.left)
            right = self._expr(node.right)
            if op_type == ast.Pow:
                self._includes.add("<cmath>")
                return f"std::pow({left}, {right})"
            if op_type == ast.FloorDiv:
                # Integer floor division
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
                    # x in container → std::find(container.begin(), container.end(), x) != container.end()
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
            # f-string: best-effort using std::to_string / concatenation
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
            params = ", ".join(
                f"auto {a.arg}" for a in node.args.args
            )
            body = self._expr(node.body)
            return f"[&]({params}) {{ return {body}; }}"

        if isinstance(node, ast.Starred):
            return f"/* *{self._expr(node.value)} */"

        if isinstance(node, ast.Await):
            return self._expr(node.value)

        self._warn(f"Unsupported expression: {type(node).__name__}")
        return f"/* unsupported: {type(node).__name__} */"

    def _fstring_expr(self, node: ast.JoinedStr) -> str:
        """Translate an f-string to a series of string concatenations."""
        self._includes.add("<string>")
        parts: list[str] = []
        for val in node.values:
            if isinstance(val, ast.Constant):
                escaped = str(val.value).replace("\\", "\\\\").replace('"', '\\"')
                parts.append(f'"{escaped}"')
            elif isinstance(val, ast.FormattedValue):
                inner = self._expr(val.value)
                # Wrap non-string types with std::to_string
                parts.append(f"std::to_string({inner})")
            else:
                parts.append(f'""')
        if not parts:
            return '""'
        return " + ".join(parts)

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
            # Handle sep= and end= kwargs
            sep = '" "'
            end = '"\\n"'
            for kw in node.keywords:
                if kw.arg == "sep":
                    sep = self._expr(kw.value)
                elif kw.arg == "end":
                    end = self._expr(kw.value)

            if not args:
                return f'std::cout << {end}'

            if len(args) == 1:
                return f'std::cout << {args[0]} << {end}'

            # Multiple args — join with sep
            joined = f' << {sep} << '.join(args)
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

        if func_name == "sorted":
            self._includes.add("<algorithm>")
            if args:
                return f"std::sort({args[0]}.begin(), {args[0]}.end()), {args[0]}"
            return "/* sorted() */"

        if func_name == "reversed":
            if args:
                return f"std::reverse({args[0]}.begin(), {args[0]}.end()), {args[0]}"
            return "/* reversed() */"

        if func_name == "enumerate":
            self._warn("enumerate() has no direct C++ equivalent — rewrite as indexed loop")
            return f"/* enumerate({', '.join(args)}) */"

        if func_name == "zip":
            self._warn("zip() has no direct C++ equivalent — use index-based loop")
            return f"/* zip({', '.join(args)}) */"

        if func_name == "input":
            self._includes.add("<iostream>")
            prompt = args[0] if args else '""'
            return f'(std::cout << {prompt}, ({{""}}))[0]'  # placeholder; warn

        # ── method calls ──────────────────────────────────────────────────────
        if isinstance(node.func, ast.Attribute):
            attr = node.func.attr
            obj = self._expr(node.func.value)

            method_map = {
                "append":    f"{obj}.push_back({', '.join(args)})",
                "push_back": f"{obj}.push_back({', '.join(args)})",
                "pop":       f"({obj}.back(), {obj}.pop_back())" if not args else f"{obj}.erase({obj}.begin() + {args[0]})",
                "clear":     f"{obj}.clear()",
                "size":      f"{obj}.size()",
                "empty":     f"{obj}.empty()",
                "find":      f"{obj}.find({', '.join(args)})",
                "insert":    f"{obj}.insert({', '.join(args)})",
                "erase":     f"{obj}.erase({', '.join(args)})",
                "begin":     f"{obj}.begin()",
                "end":       f"{obj}.end()",
                "sort":      (self._includes.add("<algorithm>") or "") + f"std::sort({obj}.begin(), {obj}.end())",
                "reverse":   (self._includes.add("<algorithm>") or "") + f"std::reverse({obj}.begin(), {obj}.end())",
                "count":     f"std::count({obj}.begin(), {obj}.end(), {', '.join(args)})" if args else f"{obj}.count()",
                "keys":      f"/* {obj}.keys() — iterate map directly */",
                "values":    f"/* {obj}.values() — iterate map directly */",
                "items":     f"/* {obj}.items() — iterate map directly */",
                "upper":     f"std::transform({obj}.begin(), {obj}.end(), {obj}.begin(), ::toupper)",
                "lower":     f"std::transform({obj}.begin(), {obj}.end(), {obj}.begin(), ::tolower)",
                "strip":     f"/* strip() — use boost::trim or manual impl */",
                "split":     f"/* split() — use std::istringstream or manual impl */",
                "join":      f"/* join() — use std::ostringstream */",
                "format":    f"/* .format() — use std::format (C++20) or sprintf */",
                "startswith":f"{obj}.substr(0, {args[0]}.size()) == {args[0]}" if args else f"/* startswith() */",
                "endswith":  f"{obj}.substr({obj}.size() - {args[0]}.size()) == {args[0]}" if args else f"/* endswith() */",
            }

            if attr in method_map:
                return method_map[attr]

        return f"{func_name}({', '.join(args)})"

    # ── statement visitors ─────────────────────────────────────────────────────

    def visit_Module(self, node: ast.Module) -> None:
        body_lines: list[str] = []
        saved = self._lines
        self._lines = body_lines
        self.generic_visit(node)
        self._lines = saved

        includes = sorted(self._includes)
        for inc in includes:
            self._emit(f"#include {inc}")
        self._emit("")
        self._lines.extend(body_lines)

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
        # Reset declared-in-scope tracking per function
        outer_declared = self._declared.copy()
        for stmt in node.body:
            self.visit(stmt)
        self._declared = outer_declared
        self._dec()
        self._emit("}")
        self._emit("")

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        bases = ", ".join(self._expr(b) for b in node.bases) if node.bases else ""
        if bases:
            self._emit(f"class {node.name} : public {bases} {{")
        else:
            self._emit(f"class {node.name} {{")
        self._emit("public:")
        self._inc()
        for stmt in node.body:
            self.visit(stmt)
        self._dec()
        self._emit("};")
        self._emit("")

    def visit_Return(self, node: ast.Return) -> None:
        val = self._expr(node.value) if node.value else ""
        self._emit(f"return {val};")

    def visit_Assign(self, node: ast.Assign) -> None:
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            val = self._expr(node.value)
            if name in self._declared:
                # Already declared — just assign
                self._emit(f"{name} = {val};")
            else:
                cpp_type = self._infer_cpp_type(node.value)
                self._emit(f"{cpp_type} {name} = {val};")
                self._declared.add(name)
        else:
            self._warn("Multi-target or complex assignment — partial support")
            val = self._expr(node.value)
            for t in node.targets:
                name_str = self._expr(t)
                self._emit(f"auto {name_str} = {val};")

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        cpp_type = self._annotation_to_cpp(node.annotation)
        name = self._expr(node.target)
        if node.value:
            val = self._expr(node.value)
            self._emit(f"{cpp_type} {name} = {val};")
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
        """
        Expression-statement.  print() calls are the most common here.
        We call _expr() which already builds the full cout expression,
        then just append a semicolon.
        """
        expr_str = self._expr(node.value)
        if expr_str and not expr_str.startswith("/*"):
            self._emit(f"{expr_str};")
        elif expr_str:
            # It's a comment/placeholder — emit without semicolon
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
                self._emit(f"for (int {target} = {range_args[0]}; {target} < {range_args[1]}; ++{target}) {{")
            elif len(range_args) == 3:
                step = range_args[2]
                op = "<" if not step.startswith("-") else ">"
                self._emit(f"for (int {target} = {range_args[0]}; {target} {op} {range_args[1]}; {target} += {step}) {{")
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
            exc_type = "std::exception" if handler.type is None else f"/* {self._expr(handler.type)} */"
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
    return jsonify({"status": "ok", "service": "Astmize API", "version": "1.1.0"})


@app.route("/convert", methods=["POST"])
def convert():
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

    logger.info("Received conversion request (%d chars)", len(python_code))

    transpiler = CppTranspiler()
    result = transpiler.transpile(python_code)
    status_code = 200 if result["success"] else 422
    logger.info("Conversion %s — %d warnings", "OK" if result["success"] else "FAILED", len(result["warnings"]))
    return jsonify(result), status_code


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    logger.info("Starting Astmize API on port %d  (debug=%s)", port, debug)
    app.run(host="0.0.0.0", port=port, debug=debug)

