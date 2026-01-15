import ast
import os
import sys
from typing import List, Dict, Any, Optional

def get_type_annotation(annotation) -> str:
    """Helper to convert AST annotation to string."""
    if annotation is None:
        return "Any"
    try:
        return ast.unparse(annotation)
    except AttributeError:
        return "ComplexType"

def get_docstring(node) -> str:
    """Extract and clean docstring."""
    doc = ast.get_docstring(node)
    return doc if doc else ""

def analyze_function(node: ast.FunctionDef | ast.AsyncFunctionDef) -> Dict[str, Any]:
    args = []
    # Handle args
    all_args = node.args.posonlyargs + node.args.args + node.args.kwonlyargs
    if node.args.vararg:
        all_args.append(node.args.vararg)
    if node.args.kwarg:
        all_args.append(node.args.kwarg)
        
    for arg in all_args:
        if isinstance(arg, ast.arg):
            arg_str = arg.arg
            if arg.annotation:
                arg_str += f": {get_type_annotation(arg.annotation)}"
            args.append(arg_str)
    
    return_type = get_type_annotation(node.returns) if node.returns else "None"
    
    decorators = []
    for dec in node.decorator_list:
        try:
            decorators.append(f"@{ast.unparse(dec)}")
        except:
            decorators.append("@...")

    return {
        "name": node.name,
        "type": "async function" if isinstance(node, ast.AsyncFunctionDef) else "function",
        "args": args,
        "return_type": return_type,
        "docstring": get_docstring(node),
        "decorators": decorators,
        "lineno": node.lineno
    }

def analyze_class(node: ast.ClassDef) -> Dict[str, Any]:
    bases = [get_type_annotation(b) for b in node.bases]
    methods = []
    fields = []
    
    for item in node.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            method_info = analyze_function(item)
            method_info["type"] = "async method" if isinstance(item, ast.AsyncFunctionDef) else "method"
            methods.append(method_info)
        elif isinstance(item, ast.AnnAssign):
            target = ast.unparse(item.target)
            annotation = get_type_annotation(item.annotation)
            fields.append(f"{target}: {annotation}")
        elif isinstance(item, ast.Assign):
            for target in item.targets:
                try:
                    fields.append(f"{ast.unparse(target)} = ...")
                except:
                    pass

    return {
        "name": node.name,
        "bases": bases,
        "docstring": get_docstring(node),
        "methods": methods,
        "fields": fields,
        "lineno": node.lineno
    }

def analyze_file(file_path: str) -> Dict[str, Any]:
    with open(file_path, "r", encoding="utf-8") as f:
        try:
            tree = ast.parse(f.read(), filename=file_path)
        except SyntaxError as e:
            return {"error": f"SyntaxError: {e}"}

    classes = []
    functions = []
    variables = []
    
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            classes.append(analyze_class(node))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(analyze_function(node))
        elif isinstance(node, ast.AnnAssign):
             target = ast.unparse(node.target)
             annotation = get_type_annotation(node.annotation)
             variables.append(f"{target}: {annotation}")
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                try:
                    if isinstance(target, ast.Name):
                        variables.append(f"{target.id} = ...")
                except:
                    pass

    return {
        "path": file_path,
        "classes": classes,
        "functions": functions,
        "variables": variables
    }

def generate_markdown_report(results: List[Dict[str, Any]]) -> str:
    lines = ["# Codebase Analysis Report", ""]
    
    for result in results:
        rel_path = os.path.relpath(result['path'], os.getcwd())
        if "error" in result:
            lines.append(f"## File: `{rel_path}` (Error)")
            lines.append(f"> {result['error']}")
            lines.append("")
            continue

        if not result["classes"] and not result["functions"] and not result["variables"]:
            continue

        lines.append(f"## File: `{rel_path}`")
        
        if result["variables"]:
            lines.append("### Global Variables")
            for var in result["variables"]:
                lines.append(f"- `{var}`")
            lines.append("")

        if result["functions"]:
            lines.append("### Global Functions")
            for func in result["functions"]:
                args_str = ", ".join(func["args"])
                dec_str = "\n".join(func["decorators"]) + "\n" if func["decorators"] else ""
                lines.append(f"#### Function `{func['name']}`")
                if func["decorators"]:
                    lines.append(f"```python\n{dec_str}```")
                lines.append(f"`def {func['name']}({args_str}) -> {func['return_type']}`")
                if func["docstring"]:
                    lines.append(f"\n> {func['docstring'].replace(chr(10), chr(10)+'> ')}\n")
        
        if result["classes"]:
            lines.append("### Classes")
            for cls in result["classes"]:
                bases_str = f"({', '.join(cls['bases'])})" if cls['bases'] else ""
                lines.append(f"#### Class `{cls['name']}{bases_str}`")
                if cls["docstring"]:
                    lines.append(f"\n> {cls['docstring'].replace(chr(10), chr(10)+'> ')}\n")
                
                if cls["fields"]:
                    lines.append("**Fields**:")
                    for field in cls["fields"]:
                        lines.append(f"- `{field}`")
                
                if cls["methods"]:
                    lines.append(f"\n**Methods**:")
                    for method in cls["methods"]:
                        args_str = ", ".join(method["args"])
                        lines.append(f"- `{method['name']}({args_str}) -> {method['return_type']}`")
                        if method["docstring"]:
                             # Short summary for methods to avoid clutter
                             summary = method["docstring"].splitlines()[0]
                             lines.append(f"  > {summary}")
        
        lines.append("---\n")
        
    return "\n".join(lines)

def main():
    target_dir = "backend/app"
    all_results = []
    
    print(f"Analyzing {target_dir}...")
    for root, _, files in os.walk(target_dir):
        for file in files:
            if file.endswith(".py"):
                full_path = os.path.join(root, file)
                result = analyze_file(full_path)
                all_results.append(result)
    
    report = generate_markdown_report(all_results)
    
    output_file = "CODEBASE_STRUCTURE.md"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(report)
    
    print(f"Analysis complete. Report saved to {output_file}")

if __name__ == "__main__":
    main()
