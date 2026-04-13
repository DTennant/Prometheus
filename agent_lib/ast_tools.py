from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SymbolInfo:
    name: str
    kind: str
    line: int
    end_line: int
    signature: str = ""
    decorators: list[str] = field(default_factory=list)


def find_classes(source: str) -> list[SymbolInfo]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    results: list[SymbolInfo] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            bases = ", ".join(ast.unparse(b) for b in node.bases)
            sig = f"class {node.name}({bases}):" if bases else f"class {node.name}:"
            decos = [ast.unparse(d) for d in node.decorator_list]
            results.append(
                SymbolInfo(
                    name=node.name,
                    kind="class",
                    line=node.lineno,
                    end_line=node.end_lineno or node.lineno,
                    signature=sig,
                    decorators=decos,
                )
            )
    return results


def find_functions(source: str) -> list[SymbolInfo]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    results: list[SymbolInfo] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            sig = f"def {node.name}({ast.unparse(node.args)}):"
            if node.returns:
                sig = f"def {node.name}({ast.unparse(node.args)}) -> {ast.unparse(node.returns)}:"
            decos = [ast.unparse(d) for d in node.decorator_list]
            results.append(
                SymbolInfo(
                    name=node.name,
                    kind="function",
                    line=node.lineno,
                    end_line=node.end_lineno or node.lineno,
                    signature=sig,
                    decorators=decos,
                )
            )
    return results


def find_imports(source: str) -> list[str]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                imports.append(f"{module}.{alias.name}")
    return imports


def get_signatures(source: str) -> str:
    classes = find_classes(source)
    functions = find_functions(source)
    lines: list[str] = []
    for c in classes:
        lines.append(c.signature)
    for f in functions:
        lines.append(f.signature)
    return "\n".join(lines)


def build_skeleton(path: Path) -> str:
    try:
        source = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return ""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return ""
    source_lines = source.splitlines()
    keep: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(
            node,
            (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef),
        ):
            keep.update(range(node.lineno, node.lineno + 2))
            if node.decorator_list:
                first_deco = node.decorator_list[0]
                keep.update(range(first_deco.lineno, node.lineno))
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            keep.add(node.lineno)

    lines: list[str] = []
    elided = False
    for i, line in enumerate(source_lines, 1):
        if i in keep:
            if elided:
                lines.append("    ...")
                elided = False
            lines.append(line)
        elif not elided:
            elided = True
    return "\n".join(lines)
