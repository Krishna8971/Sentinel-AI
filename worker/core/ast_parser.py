import ast
from typing import List, Dict, Any

class FastAPIEndpointVisitor(ast.NodeVisitor):
    def __init__(self, source_code: str):
        self.source_code = source_code
        self.endpoints = []
        self.router_names = set(['app', 'router']) # Default common names

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._check_endpoint(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._check_endpoint(node)
        self.generic_visit(node)

    def _check_endpoint(self, node: ast.AST):
        method = None
        path = None
        guards = []
        
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute):
                # Check for e.g. @app.get('/items') or @router.post('/login')
                caller_name = ""
                if isinstance(decorator.func.value, ast.Name):
                    caller_name = decorator.func.value.id
                
                # Assume anything like router.METHOD is an endpoint
                attr_name = decorator.func.attr.lower()
                http_methods = ['get', 'post', 'put', 'delete', 'patch', 'options', 'head']
                if attr_name in http_methods:
                    method = attr_name.upper()
                    if decorator.args and isinstance(decorator.args[0], ast.Constant):
                        path = decorator.args[0].value
            
        if method and path:
            # Analyze arguments for Depends()
            args = []
            if hasattr(node, 'args'):
                for arg in node.args.args:
                    arg_name = arg.arg
                    arg_deps = []
                    # In python 3.8+ defaults only apply to the last N arguments
                    # We would need to map them properly. For a simple parser, we look for Depends() loosely.
                    args.append(arg_name)
                    
            # For a more thorough extraction, we inspect default values looking for Depends()
            if hasattr(node.args, 'defaults'):
                for d in node.args.defaults:
                    if isinstance(d, ast.Call) and isinstance(d.func, ast.Name) and d.func.id == 'Depends':
                        if d.args and isinstance(d.args[0], ast.Name):
                            guards.append(d.args[0].id)
            
            # Also handle kw_defaults
            if hasattr(node.args, 'kw_defaults'):
                for d in node.args.kw_defaults:
                    if d and isinstance(d, ast.Call) and isinstance(d.func, ast.Name) and d.func.id == 'Depends':
                        if d.args and isinstance(d.args[0], ast.Name):
                            guards.append(d.args[0].id)
                            
            self.endpoints.append({
                "function_name": node.name,
                "method": method,
                "path": path,
                "guards": guards,
                "arguments": args,
                "code": ast.get_source_segment(self.source_code, node) if hasattr(ast, 'get_source_segment') else ""
            })

def parse_fastapi_code(source_code: str) -> List[Dict[str, Any]]:
    tree = ast.parse(source_code)
    visitor = FastAPIEndpointVisitor(source_code)
    visitor.visit(tree)
    return visitor.endpoints
