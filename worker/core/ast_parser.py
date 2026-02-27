import ast
from typing import List, Dict, Any

HTTP_METHODS = {'get', 'post', 'put', 'delete', 'patch', 'options', 'head'}

class FastAPIEndpointVisitor(ast.NodeVisitor):
    def __init__(self, source_code: str):
        self.source_code = source_code
        self.endpoints = []

    def _check_node(self, node):
        method, path, guards = None, None, []
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute):
                attr_name = decorator.func.attr.lower()
                if attr_name in HTTP_METHODS:
                    method = attr_name.upper()
                    if decorator.args and isinstance(decorator.args[0], ast.Constant):
                        path = decorator.args[0].value
        if method and path:
            if hasattr(node.args, 'defaults'):
                for d in node.args.defaults:
                    if isinstance(d, ast.Call) and isinstance(d.func, ast.Name) and d.func.id == 'Depends':
                        if d.args and isinstance(d.args[0], ast.Name):
                            guards.append(d.args[0].id)
            self.endpoints.append({
                "function_name": node.name,
                "method": method,
                "path": path,
                "guards": guards,
                "arguments": [a.arg for a in node.args.args],
                "code": ast.get_source_segment(self.source_code, node) or "",
                "is_endpoint": True
            })

    def visit_FunctionDef(self, node): self._check_node(node); self.generic_visit(node)
    def visit_AsyncFunctionDef(self, node): self._check_node(node); self.generic_visit(node)


class AllFunctionVisitor(ast.NodeVisitor):
    """Extracts ALL functions/methods regardless of decorators."""
    def __init__(self, source_code: str, file_path: str = ""):
        self.source_code = source_code
        self.file_path = file_path
        self.functions = []
        self._seen = set()

    def _extract(self, node):
        code = ast.get_source_segment(self.source_code, node) or ""
        # Skip trivially small functions (getters, pass-through, etc.)
        if len(code.strip().splitlines()) < 3:
            return
        key = node.name + code[:40]
        if key in self._seen:
            return
        self._seen.add(key)
        self.functions.append({
            "function_name": node.name,
            "method": "FUNCTION",
            "path": f"[{self.file_path}]",
            "guards": [],
            "arguments": [a.arg for a in node.args.args],
            "code": code,
            "is_endpoint": False
        })

    def visit_FunctionDef(self, node): self._extract(node); self.generic_visit(node)
    def visit_AsyncFunctionDef(self, node): self._extract(node); self.generic_visit(node)


def parse_fastapi_code(source_code: str) -> List[Dict[str, Any]]:
    tree = ast.parse(source_code)
    visitor = FastAPIEndpointVisitor(source_code)
    visitor.visit(tree)
    return visitor.endpoints


def extract_all_functions(source_code: str, file_path: str = "") -> List[Dict[str, Any]]:
    tree = ast.parse(source_code)
    visitor = AllFunctionVisitor(source_code, file_path)
    visitor.visit(tree)
    return visitor.functions
