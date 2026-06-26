#!/usr/bin/env python3
"""
extract_code_kg.py — Extract a knowledge graph from a Python codebase.

Produces a JSON graph with:
- Nodes: modules, classes, functions, methods, tests, variables, enum_values, exceptions
- Edges: imports, calls, inherits, defines, tests, depends_on, raises, manages_state, has_enum_value, runtime_import
- Behavioral fields: raises, return_conditions, class_attributes, import_convention, full_docstring

Enriched v2: Captures behavioral contracts (exceptions, return conditions,
class attributes, module-level state, enum values, import conventions) that
an implementer needs to write correct code.

Usage:
    python3 extract_code_kg.py <repo-path> [output-path]
"""

import ast
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


# ─── AST Visitor that extracts the KG ───

class CodeKGExtractor(ast.NodeVisitor):
    """Walks a Python AST and collects nodes and edges with behavioral detail."""

    def __init__(self, file_path: str, module_name: str):
        self.file_path = file_path
        self.module_name = module_name
        self.nodes: List[dict] = []
        self.edges: List[dict] = []
        self._current_class: Optional[str] = None
        self._scope_stack: List[str] = []

        # Track all names defined and referenced
        self._defined_names: Set[str] = set()
        self._imported_names: Dict[str, str] = {}  # name -> module

        # Track module-level variables
        self._module_vars: List[dict] = []

        # Track import conventions (runtime imports inside functions)
        self._import_conventions: List[dict] = []

    def _make_node_id(self, name: str, kind: str) -> str:
        """Create a stable node ID."""
        parts = [self.module_name]
        if self._current_class:
            parts.append(self._current_class)
        parts.append(name)
        return "-".join(parts).lower().replace("_", "-")

    def _add_node(self, node_id: str, node_type: str, label: str, **extra):
        """Add a node if not already present."""
        existing = next((n for n in self.nodes if n["id"] == node_id), None)
        if existing:
            existing.update(extra)
            return
        node = {
            "id": node_id,
            "type": node_type,
            "label": label,
            "file": self.file_path,
            "module": self.module_name,
        }
        node.update(extra)
        self.nodes.append(node)

    def _add_edge(self, source: str, target: str, relation: str, **extra):
        """Add an edge."""
        edge = {"source": source, "target": target, "relation": relation}
        edge.update(extra)
        self.edges.append(edge)

    def _get_docstring(self, node: ast.AST) -> Optional[str]:
        """Extract docstring from a node (full, no truncation)."""
        ds = ast.get_docstring(node)
        if ds:
            return ds.strip()  # No truncation — behavioral contracts matter
        return None

    def _get_args(self, node: ast.FunctionDef) -> List[str]:
        """Get argument names from a function def."""
        args = []
        for arg in node.args.args:
            args.append(arg.arg)
        if node.args.vararg:
            args.append(f"*{node.args.vararg.arg}")
        if node.args.kwarg:
            args.append(f"**{node.args.kwarg.arg}")
        return args

    def _get_return_annotation(self, node: ast.FunctionDef) -> Optional[str]:
        """Get return type annotation as string."""
        if node.returns:
            try:
                return ast.unparse(node.returns)
            except:
                return None
        return None

    def _get_arg_types(self, node: ast.FunctionDef) -> Dict[str, str]:
        """Get argument type annotations."""
        types = {}
        for arg in node.args.args:
            if arg.annotation:
                try:
                    types[arg.arg] = ast.unparse(arg.annotation)
                except:
                    pass
        return types

    # ─── Behavioral extraction helpers ───

    def _extract_raises(self, node: ast.FunctionDef) -> List[dict]:
        """Extract raise statements from a function body."""
        raises = []
        for child in ast.walk(node):
            if isinstance(child, ast.Raise) and child.exc:
                exc_info = {"type": "unknown", "condition": None}
                exc = child.exc
                if isinstance(exc, ast.Call) and isinstance(exc.func, ast.Name):
                    exc_info["type"] = exc.func.id
                    if exc.args:
                        try:
                            exc_info["condition"] = ast.unparse(exc.args[0])
                        except:
                            pass
                elif isinstance(exc, ast.Name):
                    exc_info["type"] = exc.id
                elif isinstance(exc, ast.Call) and isinstance(exc.func, ast.Attribute):
                    try:
                        exc_info["type"] = ast.unparse(exc.func)
                    except:
                        pass
                raises.append(exc_info)
        return raises

    def _extract_return_conditions(self, node: ast.FunctionDef) -> List[dict]:
        """Extract return statements with their conditions."""
        conditions = []

        def _walk_returns(n, in_if=None):
            for child in ast.iter_child_nodes(n):
                if isinstance(child, ast.If):
                    cond_str = None
                    try:
                        cond_str = ast.unparse(child.test)
                    except:
                        pass

                    for stmt in child.body:
                        if isinstance(stmt, ast.Return):
                            ret_val = None
                            try:
                                ret_val = ast.unparse(stmt.value) if stmt.value else "None"
                            except:
                                pass
                            conditions.append({
                                "condition": cond_str,
                                "returns": ret_val,
                                "branch": "if_true",
                            })
                        elif isinstance(stmt, (ast.If, ast.For, ast.While, ast.With)):
                            _walk_returns(stmt, in_if=cond_str)

                    for stmt in child.orelse:
                        if isinstance(stmt, ast.Return):
                            ret_val = None
                            try:
                                ret_val = ast.unparse(stmt.value) if stmt.value else "None"
                            except:
                                pass
                            conditions.append({
                                "condition": cond_str,
                                "returns": ret_val,
                                "branch": "if_false",
                            })
                        elif isinstance(stmt, (ast.If, ast.For, ast.While, ast.With)):
                            _walk_returns(stmt, in_if=cond_str)

                elif isinstance(child, ast.Return):
                    ret_val = None
                    try:
                        ret_val = ast.unparse(child.value) if child.value else "None"
                    except:
                        pass
                    conditions.append({
                        "condition": None,
                        "returns": ret_val,
                        "branch": "unconditional",
                    })
                elif isinstance(child, (ast.For, ast.While, ast.With)):
                    _walk_returns(child, in_if=in_if)

        _walk_returns(node)
        return conditions

    def _extract_class_attributes(self, node: ast.ClassDef) -> List[dict]:
        """Extract instance attributes assigned in __init__ and class-level assignments."""
        attrs = []

        # Class-level assignments (class attributes)
        for child in node.body:
            if isinstance(child, ast.Assign):
                for target in child.targets:
                    if isinstance(target, ast.Name):
                        type_hint = None
                        if child.value and isinstance(child.value, ast.Constant):
                            type_hint = type(child.value.value).__name__ if child.value.value is not None else "None"
                        attrs.append({
                            "name": target.id,
                            "kind": "class_attribute",
                            "type_hint": type_hint,
                        })

        # Instance attributes from __init__
        init_method = next((c for c in node.body
                           if isinstance(c, ast.FunctionDef) and c.name == "__init__"), None)
        if init_method:
            for child in ast.walk(init_method):
                if isinstance(child, ast.Assign):
                    for target in child.targets:
                        if (isinstance(target, ast.Attribute) and
                            isinstance(target.value, ast.Name) and
                            target.value.id == "self"):
                            type_hint = None
                            if child.value:
                                try:
                                    if isinstance(child.value, ast.Call):
                                        type_hint = ast.unparse(child.value.func)
                                    elif isinstance(child.value, ast.Constant):
                                        type_hint = type(child.value.value).__name__ if child.value.value is not None else "None"
                                    else:
                                        type_hint = ast.unparse(child.value)
                                except:
                                    pass
                            attrs.append({
                                "name": target.attr,
                                "kind": "instance_attribute",
                                "type_hint": type_hint,
                            })

        return attrs

    def _extract_enum_values(self, node: ast.ClassDef) -> List[dict]:
        """Extract enum members from a class that inherits from Enum."""
        values = []
        is_enum = False
        for base in node.bases:
            try:
                base_name = ast.unparse(base)
                if "Enum" in base_name:
                    is_enum = True
            except:
                pass

        if not is_enum:
            return values

        for child in node.body:
            if isinstance(child, ast.Assign):
                for target in child.targets:
                    if isinstance(target, ast.Name):
                        val = None
                        if child.value:
                            try:
                                val = ast.unparse(child.value)
                            except:
                                pass
                        values.append({
                            "name": target.id,
                            "value": val,
                        })

        return values

    def _extract_module_variables(self, node: ast.Module) -> List[dict]:
        """Extract module-level variable assignments (state like _user_db, _payment_db)."""
        variables = []
        for child in node.body:
            if isinstance(child, ast.Assign):
                for target in child.targets:
                    if isinstance(target, ast.Name):
                        type_hint = None
                        value_repr = None
                        if child.value:
                            try:
                                value_repr = ast.unparse(child.value)
                                if isinstance(child.value, ast.Dict):
                                    type_hint = "Dict"
                                elif isinstance(child.value, ast.List):
                                    type_hint = "List"
                                elif isinstance(child.value, ast.Constant):
                                    type_hint = type(child.value.value).__name__ if child.value.value is not None else "None"
                                elif isinstance(child.value, ast.Call):
                                    type_hint = ast.unparse(child.value.func)
                                else:
                                    type_hint = "any"
                            except:
                                pass

                        variables.append({
                            "name": target.id,
                            "type_hint": type_hint,
                            "value_repr": value_repr,
                        })

            elif isinstance(child, ast.AnnAssign):
                if isinstance(child.target, ast.Name):
                    type_hint = None
                    if child.annotation:
                        try:
                            type_hint = ast.unparse(child.annotation)
                        except:
                            pass
                    variables.append({
                        "name": child.target.id,
                        "type_hint": type_hint,
                        "value_repr": None,
                    })

        return variables

    def _extract_runtime_imports(self, node: ast.FunctionDef) -> List[dict]:
        """Detect runtime import patterns inside functions (like _get_user_service)."""
        runtime_imports = []
        for child in ast.walk(node):
            if isinstance(child, ast.Import):
                for alias in child.names:
                    runtime_imports.append({
                        "module": alias.name,
                        "asname": alias.asname,
                        "inside_function": node.name,
                    })
            elif isinstance(child, ast.ImportFrom):
                mod = child.module or ""
                runtime_imports.append({
                    "module": mod,
                    "inside_function": node.name,
                    "names": [a.name for a in child.names],
                })
        return runtime_imports

    def _make_natural_language(self, node_type: str, name: str, docstring: Optional[str],
                                args: List[str] = None, returns: Optional[str] = None,
                                class_name: Optional[str] = None,
                                raises: List[dict] = None,
                                return_conditions: List[dict] = None,
                                class_attributes: List[dict] = None,
                                enum_values: List[dict] = None,
                                import_convention: str = None) -> str:
        """Generate a rich natural language description of this node."""
        parts = []

        if node_type == "module":
            if docstring:
                parts.append(docstring)
            else:
                parts.append(f"The {name} module.")
            return " ".join(parts)

        if node_type == "class":
            parts.append(f"{name} is a class")
            if docstring:
                parts.append(f"that {docstring.lower().rstrip('.')}")
            if enum_values:
                parts.append(f"It has enum values: {', '.join(v['name'] + '=' + str(v['value']) for v in enum_values)}")
            if class_attributes:
                attr_strs = [f"{a['name']}" for a in class_attributes]
                parts.append(f"with attributes: {', '.join(attr_strs)}")
        elif node_type in ("function", "method"):
            kind_word = "function" if node_type == "function" else "method"
            if class_name:
                parts.append(f"{name} is a {kind_word} on the {class_name} class")
            else:
                parts.append(f"{name} is a {kind_word}")

            if args:
                parts.append(f"that takes parameters: {', '.join(args)}")

            if returns:
                parts.append(f"and returns a {returns}")

            if docstring:
                first_sent = docstring.split(".")[0].strip()
                if first_sent:
                    parts.append(f"It {first_sent.lower().rstrip('.')}")

            # Behavioral contract: raises
            if raises:
                raise_strs = []
                for r in raises:
                    s = r["type"]
                    if r.get("condition"):
                        s += f" (condition: {r['condition']})"
                    raise_strs.append(s)
                parts.append(f"It raises {', '.join(raise_strs)}")

            # Behavioral contract: return conditions
            if return_conditions:
                rc_strs = []
                for rc in return_conditions:
                    if rc["condition"]:
                        rc_strs.append(f"if {rc['condition']} then returns {rc['returns']}")
                    elif rc["branch"] == "unconditional":
                        rc_strs.append(f"returns {rc['returns']}")
                if rc_strs:
                    parts.append(f"Return behavior: {'; '.join(rc_strs)}")

            # Import convention
            if import_convention:
                parts.append(f"It uses the import convention: {import_convention}")

        return ". ".join(parts) + "." if parts else f"The {name} {node_type}."

    def visit_Module(self, node):
        """Extract module-level information."""
        ds = self._get_docstring(node)

        # Collect all top-level definitions first
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._defined_names.add(child.name)
            elif isinstance(child, ast.ClassDef):
                self._defined_names.add(child.name)

        # Extract module-level variables
        self._module_vars = self._extract_module_variables(node)

        # Create module node
        module_id = f"mod-{self.module_name.replace('_', '-').replace('.', '-')}"
        nl = self._make_natural_language("module", self.module_name, ds)

        module_fields = {
            "natural_language": nl,
            "module_variables": self._module_vars,
        }
        if ds:
            module_fields["docstring"] = ds

        top_level_funcs = [c for c in node.body if isinstance(c, (ast.FunctionDef, ast.AsyncFunctionDef))]
        top_level_classes = [c for c in node.body if isinstance(c, ast.ClassDef)]
        module_fields["functions"] = [f.name for f in top_level_funcs]
        module_fields["classes"] = [c.name for c in top_level_classes]

        self._add_node(module_id, "module", self.module_name, **module_fields)

        # Add module variable nodes
        for var in self._module_vars:
            var_id = f"var-{self.module_name.replace('_', '-')}-{var['name'].replace('_', '-')}"
            var_parts = [f"{var['name']} is a module-level variable in {self.module_name}"]
            if var.get("type_hint"):
                var_parts.append(f"of type {var['type_hint']}")
            if var.get("value_repr") and var["value_repr"] != var["name"]:
                var_parts.append(f"initialized as {var['value_repr']}")
            var_nl = ". ".join(var_parts) + "."

            self._add_node(var_id, "variable", var["name"],
                          natural_language=var_nl,
                          type_hint=var.get("type_hint"),
                          value_repr=var.get("value_repr"))
            self._add_edge(module_id, var_id, "MANAGES_STATE",
                          assertion=f"{self.module_name} manages state variable {var['name']}")

        # Visit children
        for child in node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._visit_function(child, parent_module_id=module_id)
            elif isinstance(child, ast.ClassDef):
                self._visit_class(child, parent_module_id=module_id)
            elif isinstance(child, (ast.Import, ast.ImportFrom)):
                self._visit_import(child, source_module_id=module_id)

    def _visit_import(self, node, source_module_id: str):
        """Handle import statements."""
        if isinstance(node, ast.Import):
            for alias in node.names:
                mod_name = alias.name
                if alias.asname:
                    self._imported_names[alias.asname] = mod_name
                else:
                    short = mod_name.split(".")[-1]
                    self._imported_names[short] = mod_name

                ext_id = f"ext-{mod_name.replace('.', '-').replace('_', '-')}"
                self._add_node(ext_id, "external_module", mod_name,
                              natural_language=f"External module: {mod_name}")
                self._add_edge(source_module_id, ext_id, "IMPORTS")

        elif isinstance(node, ast.ImportFrom):
            mod_name = node.module or ""
            for alias in node.names:
                name = alias.name
                if alias.asname:
                    self._imported_names[alias.asname] = mod_name
                else:
                    self._imported_names[name] = mod_name

                ext_id = f"ext-{mod_name.replace('.', '-').replace('_', '-')}" if mod_name else "ext-unknown"
                self._add_node(ext_id, "external_module", mod_name or "unknown",
                              natural_language=f"External module: {mod_name or 'unknown'}")
                self._add_edge(source_module_id, ext_id, "IMPORTS")

                imp_id = f"ext-{mod_name.replace('.', '-').replace('_', '-')}-{name}" if mod_name else f"ext-{name}"
                self._add_node(imp_id, "imported_name", f"{mod_name}.{name}" if mod_name else name,
                              natural_language=f"Imported from {mod_name}: {name}")
                self._add_edge(ext_id, imp_id, "EXPORTS")

    def _visit_class(self, node: ast.ClassDef, parent_module_id: str):
        """Visit a class definition with enriched behavioral extraction."""
        class_id = self._make_node_id(node.name, "class")
        ds = self._get_docstring(node)

        # Handle inheritance
        base_classes = []
        for base in node.bases:
            try:
                base_name = ast.unparse(base)
                base_classes.append(base_name)
            except:
                pass

        # Extract class attributes
        class_attrs = self._extract_class_attributes(node)

        # Extract enum values
        enum_vals = self._extract_enum_values(node)

        nl = self._make_natural_language("class", node.name, ds,
                                          class_attributes=class_attrs,
                                          enum_values=enum_vals)

        class_fields = {
            "natural_language": nl,
            "line": node.lineno,
            "bases": base_classes,
            "class_attributes": class_attrs,
            "enum_values": enum_vals,
        }
        if ds:
            class_fields["docstring"] = ds

        # Count methods
        methods = [c for c in node.body if isinstance(c, (ast.FunctionDef, ast.AsyncFunctionDef))]
        class_fields["methods"] = [m.name for m in methods]

        self._add_node(class_id, "class", node.name, **class_fields)
        self._add_edge(parent_module_id, class_id, "DEFINES_CLASS")

        # Add inheritance edges
        for base in base_classes:
            base_id = self._make_node_id(base, "class")
            self._add_edge(class_id, base_id, "INHERITS_FROM",
                          assertion=f"{node.name} inherits from {base}")

        # Add enum value nodes
        if enum_vals:
            for ev in enum_vals:
                ev_id = f"enum-{node.name.lower()}-{ev['name'].lower()}"
                ev_nl = f"{node.name}.{ev['name']} is an enum value"
                if ev.get("value"):
                    ev_nl += f" with value {ev['value']}"
                self._add_node(ev_id, "enum_value", f"{node.name}.{ev['name']}",
                              natural_language=ev_nl,
                              enum_class=node.name,
                              value=ev.get("value"))
                self._add_edge(class_id, ev_id, "HAS_ENUM_VALUE",
                              assertion=f"{node.name} has enum value {ev['name']}")

        # Visit methods
        prev_class = self._current_class
        self._current_class = node.name
        for child in node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._visit_function(child, parent_module_id=class_id, class_name=node.name)
        self._current_class = prev_class

    def _visit_function(self, node: ast.FunctionDef, parent_module_id: str,
                        class_name: Optional[str] = None):
        """Visit a function or method definition with behavioral extraction."""
        func_id = self._make_node_id(node.name, "function")
        ds = self._get_docstring(node)
        args = self._get_args(node)
        returns = self._get_return_annotation(node)
        arg_types = self._get_arg_types(node)

        # Extract behavioral contracts
        raises = self._extract_raises(node)
        return_conditions = self._extract_return_conditions(node)

        # Extract runtime import conventions
        runtime_imports = self._extract_runtime_imports(node)
        import_convention = None
        if runtime_imports:
            ri = runtime_imports[0]
            if ri.get("asname"):
                import_convention = f"imports {ri['module']} as {ri['asname']} inside {ri['inside_function']}"
            else:
                import_convention = f"imports {ri['module']} inside function {ri['inside_function']}"
            self._import_conventions.extend(runtime_imports)

        # Determine if method
        is_method = class_name is not None
        node_type = "method" if is_method else "function"

        nl = self._make_natural_language(node_type, node.name, ds, args, returns, class_name,
                                          raises=raises,
                                          return_conditions=return_conditions,
                                          import_convention=import_convention)

        func_fields = {
            "natural_language": nl,
            "line": node.lineno,
            "args": args,
            "arg_types": arg_types,
            "raises": raises,
            "return_conditions": return_conditions,
        }
        if returns:
            func_fields["returns"] = returns
        if ds:
            func_fields["docstring"] = ds
        if is_method:
            func_fields["class"] = class_name
        if import_convention:
            func_fields["import_convention"] = import_convention
        func_fields["is_method"] = is_method

        self._add_node(func_id, node_type, node.name, **func_fields)
        self._add_edge(parent_module_id, func_id, "DEFINES_FUNCTION")

        # Add RAISES edges
        for r in raises:
            raise_node_id = f"raise-{self.module_name.replace('_', '-')}-{r['type'].lower()}"
            self._add_node(raise_node_id, "exception", r["type"],
                          natural_language=f"Exception: {r['type']}")
            edge_extra = {"assertion": f"{node.name} raises {r['type']}"}
            if r.get("condition"):
                edge_extra["condition"] = r["condition"]
            self._add_edge(func_id, raise_node_id, "RAISES", **edge_extra)

        # Visit the function body to collect calls
        self._scope_stack.append(node.name)
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                self._record_call(child, caller_id=func_id)
        self._scope_stack.pop()

    def _record_call(self, node: ast.Call, caller_id: str):
        """Record a function call as an edge."""
        func_name = None
        try:
            func_name = ast.unparse(node.func)
        except:
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                func_name = node.func.attr

        if not func_name:
            return

        # Check if it's an imported function
        if func_name in self._imported_names:
            mod = self._imported_names[func_name]
            target_id = f"ext-{mod.replace('.', '-').replace('_', '-')}-{func_name}"
            self._add_edge(caller_id, target_id, "CALLS_EXTERNAL",
                          assertion=f"calls {mod}.{func_name}")
            return

        # Check if it's a local function/method
        local_target = self._make_node_id(func_name, "function")

        if "." in func_name:
            parts = func_name.split(".")
            if parts[0] == "self" and self._current_class:
                method_name = parts[-1]
                local_target = self._make_node_id(method_name, "function")
                self._add_edge(caller_id, local_target, "CALLS",
                              assertion=f"calls self.{method_name}()")
                return

        base_name = func_name.split(".")[-1]
        if base_name in self._defined_names:
            self._add_edge(caller_id, local_target, "CALLS",
                          assertion=f"calls {base_name}()")
        else:
            ext_id = f"call-{func_name.replace('.', '-').replace('_', '-').lower()}"
            self._add_node(ext_id, "external_call", func_name,
                          natural_language=f"External call: {func_name}")
            self._add_edge(caller_id, ext_id, "CALLS_EXTERNAL",
                          assertion=f"calls {func_name}")


# ─── Test extractor ───

class TestKGExtractor(ast.NodeVisitor):
    """Extract test-to-function mappings from test files."""

    def __init__(self, file_path: str, module_name: str):
        self.file_path = file_path
        self.module_name = module_name
        self.nodes: List[dict] = []
        self.edges: List[dict] = []

    def visit_Module(self, node):
        ds = ast.get_docstring(node)
        module_id = f"test-mod-{self.module_name.replace('_', '-').replace('.', '-')}"

        self.nodes.append({
            "id": module_id,
            "type": "test_module",
            "label": self.module_name,
            "file": self.file_path,
            "natural_language": f"Test module {self.module_name}" + (f": {ds}" if ds else ""),
        })

        for child in node.body:
            if isinstance(child, ast.ClassDef):
                self._visit_test_class(child, module_id)

    def _visit_test_class(self, node: ast.ClassDef, parent_id: str):
        class_id = f"test-{node.name.lower().replace('_', '-')}"
        ds = ast.get_docstring(node)

        self.nodes.append({
            "id": class_id,
            "type": "test_class",
            "label": node.name,
            "file": self.file_path,
            "natural_language": f"Test class {node.name}" + (f" — {ds}" if ds else ""),
        })
        self.edges.append({"source": parent_id, "target": class_id, "relation": "CONTAINS"})

        for child in node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._visit_test_method(child, class_id)

    def _visit_test_method(self, node: ast.FunctionDef, parent_id: str):
        method_id = f"{parent_id}-{node.name.lower().replace('_', '-')}"
        ds = ast.get_docstring(node)

        tested_func = None
        name = node.name
        if name.startswith("test_"):
            tested_func = name[5:]

        self.nodes.append({
            "id": method_id,
            "type": "test_method",
            "label": node.name,
            "file": self.file_path,
            "line": node.lineno,
            "tests_function": tested_func,
            "natural_language": f"Test method {node.name}" +
                (f" — tests {tested_func}" if tested_func else "") +
                (f". {ds}" if ds else ""),
        })
        self.edges.append({"source": parent_id, "target": method_id, "relation": "CONTAINS"})

        if tested_func:
            self.edges.append({
                "source": method_id,
                "target": f"__lookup__:{tested_func}",
                "relation": "TESTS",
                "assertion": f"tests {tested_func}",
            })

        for child in ast.walk(node):
            if isinstance(child, ast.Assert):
                self.edges.append({
                    "source": method_id,
                    "target": method_id,
                    "relation": "HAS_ASSERTION",
                    "assertion": "contains an assert statement",
                })


# ─── Main extraction logic ───

def extract_kg(repo_path: str) -> dict:
    """Extract knowledge graph from a Python repository."""
    repo = Path(repo_path)
    all_nodes: List[dict] = []
    all_edges: List[dict] = []

    src_dir = repo / "src"
    test_dir = repo / "tests"

    src_files = list(src_dir.glob("*.py")) if src_dir.exists() else []
    test_files = list(test_dir.glob("*.py")) if test_dir.exists() else []

    # First pass: extract all source modules
    module_exports: Dict[str, List[str]] = {}

    for pyfile in src_files:
        if pyfile.name == "__init__.py":
            continue
        module_name = pyfile.stem
        try:
            tree = ast.parse(pyfile.read_text(), filename=str(pyfile))
        except SyntaxError as e:
            print(f"  ⚠ Parse error in {pyfile}: {e}", file=sys.stderr)
            continue

        extractor = CodeKGExtractor(str(pyfile), module_name)
        extractor.visit(tree)
        all_nodes.extend(extractor.nodes)
        all_edges.extend(extractor.edges)

        exports = [n["label"] for n in extractor.nodes if n["type"] in ("function", "class")]
        module_exports[module_name] = exports

    # Second pass: extract test modules
    for pyfile in test_files:
        if pyfile.name == "__init__.py":
            continue
        module_name = pyfile.stem
        try:
            tree = ast.parse(pyfile.read_text(), filename=str(pyfile))
        except SyntaxError as e:
            print(f"  ⚠ Parse error in {pyfile}: {e}", file=sys.stderr)
            continue

        test_extractor = TestKGExtractor(str(pyfile), module_name)
        test_extractor.visit(tree)
        all_nodes.extend(test_extractor.nodes)
        all_edges.extend(test_extractor.edges)

    # Third pass: resolve test edges
    name_to_id: Dict[str, str] = {}
    for n in all_nodes:
        if n["type"] in ("function", "method", "class"):
            name_to_id[n["label"]] = n["id"]
            name_to_id[n["label"].replace("_", "-")] = n["id"]

    resolved_edges = []
    for e in all_edges:
        if e["target"].startswith("__lookup__:"):
            func_name = e["target"].replace("__lookup__:", "")
            target_id = name_to_id.get(func_name)
            if not target_id:
                target_id = name_to_id.get(func_name.replace("_", "-"))
            if target_id:
                e["target"] = target_id
                resolved_edges.append(e)
        else:
            resolved_edges.append(e)
    all_edges = resolved_edges

    # Detect runtime import conventions and add cross-module edges
    for src_file in src_files:
        if src_file.name == "__init__.py":
            continue
        module_name = src_file.stem
        try:
            tree = ast.parse(src_file.read_text())
        except SyntaxError:
            continue

        # Find runtime imports inside functions
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for child in ast.walk(node):
                    if isinstance(child, ast.Import):
                        for alias in child.names:
                            if alias.name in module_exports:
                                src_func_id = f"{module_name.replace('_', '-')}-{node.name}".lower().replace('_', '-')
                                tgt_mod_id = f"mod-{alias.name.replace('_', '-')}"
                                exists = any(
                                    e["source"] == src_func_id and e["target"] == tgt_mod_id
                                    and e["relation"] == "RUNTIME_IMPORT"
                                    for e in all_edges
                                )
                                if not exists:
                                    all_edges.append({
                                        "source": src_func_id,
                                        "target": tgt_mod_id,
                                        "relation": "RUNTIME_IMPORT",
                                        "assertion": f"{node.name} imports {alias.name} at runtime",
                                        "bridge": f"The {node.name} function in {module_name} imports {alias.name} inside the function body (lazy import pattern). This means cross-module calls go through: {module_name}.{node.name}() → import {alias.name} → {alias.name}.<function>(). Use this pattern when calling {alias.name} functions from {module_name}."
                                    })

        # Also detect regular top-level imports of sibling modules
        for tlnode in ast.walk(tree):
            if isinstance(tlnode, ast.Import):
                for alias in tlnode.names:
                    if alias.name in module_exports:
                        src_mod_id = f"mod-{module_name.replace('_', '-')}"
                        tgt_mod_id = f"mod-{alias.name.replace('_', '-')}"
                        exists = any(
                            e["source"] == src_mod_id and e["target"] == tgt_mod_id
                            and e["relation"] == "DEPENDS_ON"
                            for e in all_edges
                        )
                        if not exists:
                            all_edges.append({
                                "source": src_mod_id,
                                "target": tgt_mod_id,
                                "relation": "DEPENDS_ON",
                                "assertion": f"{module_name} depends on {alias.name}",
                                "bridge": f"The {module_name} module imports {alias.name} at runtime to access its functions. This means {module_name} cannot operate independently — it needs {alias.name} to be available."
                            })

    # Add domain grouping
    for n in all_nodes:
        if n["type"] in ("module", "function", "class", "method", "variable", "enum_value"):
            if "test" in n.get("file", ""):
                n["domain"] = "tests"
            elif "user" in n.get("label", "").lower() or "auth" in n.get("label", "").lower() or "password" in n.get("label", "").lower():
                n["domain"] = "user_management"
            elif "payment" in n.get("label", "").lower() or "billing" in n.get("label", "").lower() or "subscription" in n.get("label", "").lower() or "refund" in n.get("label", "").lower():
                n["domain"] = "payments"
            elif "notif" in n.get("label", "").lower() or "email" in n.get("label", "").lower():
                n["domain"] = "notifications"
            else:
                n["domain"] = "core"

    # Add bridge sentences on key cross-domain edges
    for e in all_edges:
        if e["relation"] == "CALLS" and "process_payment" in e.get("assertion", ""):
            e["bridge"] = "The payments module calls process_payment which depends on user_service.get_user_profile to validate the user exists before charging. This cross-module dependency means payment failures can stem from user lookup issues."
        elif e["relation"] == "DEPENDS_ON" and "payments" in e.get("assertion", ""):
            if not e.get("bridge"):
                e["bridge"] = f"{e['assertion']}. This means the dependent module needs the dependency at runtime."

    # ─── Extract convention/pattern nodes from RAISES patterns ───
    # A convention node captures a shared behavioral pattern across functions
    # in the same module. For example, if multiple functions raise ValueError
    # for user validation, we create a convention node:
    #   "User validation pattern: raise ValueError with 'not found' message"
    # This gives the model DIRECTION, not just facts.
    conventions = extract_conventions(all_nodes, all_edges)
    all_nodes.extend(conventions["nodes"])
    all_edges.extend(conventions["edges"])

    return {"nodes": all_nodes, "edges": all_edges, "metadata": {
        "source_files": [f.name for f in src_files if f.name != "__init__.py"],
        "test_files": [f.name for f in test_files if f.name != "__init__.py"],
        "module_exports": module_exports,
        "conventions": [c["label"] for c in conventions["nodes"]],
    }}


# ─── Convention extraction ───

def extract_conventions(nodes: List[dict], edges: List[dict]) -> dict:
    """Extract convention/pattern nodes from the graph.
    
    A convention captures a shared behavioral pattern that gives DIRECTION
    to an implementer, not just facts. For example:
    - User validation pattern: raise ValueError with 'not found' message
    - State transition pattern: use enum constants for status changes
    - Cross-module access pattern: use _get_user_service() for user_service calls
    
    These are deterministic patterns detected from the graph structure.
    """
    conv_nodes = []
    conv_edges = []
    
    # Group functions by module that raise the same exception type
    module_raises = {}  # {module: {exception_type: [(func_node, raise_info)]}}
    for n in nodes:
        if n.get("type") in ("function", "method") and n.get("raises"):
            mod = n.get("module", "")
            for r in n["raises"]:
                exc_type = r["type"]
                key = (mod, exc_type)
                module_raises.setdefault(key, []).append((n, r))
    
    # Create convention nodes for patterns shared across 2+ functions
    for (module, exc_type), func_raises in module_raises.items():
        if len(func_raises) < 2:
            # Single function — still create a convention if it's a user-facing function
            # (functions with 'user' or 'payment' in the name that take user_id)
            first_func = func_raises[0][0]
            if not any(kw in first_func.get("label", "").lower() 
                       for kw in ["user", "payment", "register", "process", "cancel"]):
                continue
        
        # Build the convention description
        # Deduplicate by function name (a function may raise the same exception in multiple places)
        seen_funcs = set()
        unique_raises = []
        for fr_node, r_info in func_raises:
            if fr_node["label"] not in seen_funcs:
                seen_funcs.add(fr_node["label"])
                unique_raises.append((fr_node, r_info))
        func_names = [fr[0]["label"] for fr in unique_raises]
        conditions = [fr[1].get("condition", "") for fr in unique_raises]
        
        # Detect the pattern type
        pattern_desc = None
        pattern_id = f"convention-{module.replace('_', '-')}-{exc_type.lower()}"
        
        if exc_type == "ValueError":
            # Check if this is user validation
            user_funcs = [fn for fn, cond in zip(func_names, conditions) 
                         if any(kw in fn.lower() or kw in cond.lower() 
                                for kw in ["user", "not found", "exists", "email"])]
            
            # Issue 2: Distinguish validation functions (raise) from lookup functions (return None/False)
            # Check return conditions of the functions to identify lookup-style functions
            lookup_funcs = []
            validation_funcs = []
            for fr_node, _ in unique_raises:
                return_conds = fr_node.get("return_conditions", [])
                returns_none = any(rc.get("returns") in ("None", "False", "None\n", "False\n") 
                                   for rc in return_conds if rc.get("branch") == "unconditional")
                if returns_none and not any(kw in fr_node.get("label", "").lower() 
                                           for kw in ["validate", "process", "register"]):
                    lookup_funcs.append(fr_node["label"])
                else:
                    validation_funcs.append(fr_node["label"])
            
            if user_funcs:
                pattern_desc = (
                    f"User validation convention in {module}: functions that validate user existence "
                    f"raise ValueError when the user is not found. "
                    f"Pattern: check if user exists, if not raise ValueError with a descriptive message "
                    f"containing 'not found'. "
                    f"Followed by: {', '.join(func_names)}. "
                    f"When implementing new functions that VALIDATE users in {module}, "
                    f"use this same pattern: raise ValueError for nonexistent users. "
                )
                if lookup_funcs:
                    pattern_desc += (
                        f"IMPORTANT: Functions that LOOK UP data (like getting a profile or fetching a payment) "
                        f"should return None for missing entries, NOT raise ValueError. "
                        f"Only functions that VALIDATE or PROCESS (like process_payment, register_user) "
                        f"should raise ValueError. Do not apply this convention to data aggregation or lookup tasks."
                    )
            else:
                # Generic ValueError convention
                pattern_desc = (
                    f"ValueError convention in {module}: multiple functions raise ValueError "
                    f"for invalid input. Pattern: validate input, raise ValueError with descriptive message. "
                    f"Followed by: {', '.join(func_names)}. "
                    f"When implementing new functions in {module}, raise ValueError for invalid inputs "
                    f"following the same message style."
                )
        elif exc_type == "RuntimeError":
            pattern_desc = (
                f"State transition convention in {module}: functions raise RuntimeError "
                f"when an operation is attempted in an invalid state. "
                f"Followed by: {', '.join(func_names)}. "
                f"When implementing new functions that change state, check the current state first "
                f"and raise RuntimeError if the state doesn't allow the operation."
            )
        else:
            pattern_desc = (
                f"{exc_type} convention in {module}: functions raise {exc_type} for error conditions. "
                f"Followed by: {', '.join(func_names)}."
            )
        
        conv_node = {
            "id": pattern_id,
            "type": "convention",
            "label": f"{module}.{exc_type} convention",
            "natural_language": pattern_desc,
            "module": module,
            "exception_type": exc_type,
            "functions": func_names,
            "conditions": conditions,
            "domain": "conventions",
        }
        conv_nodes.append(conv_node)
        
        # Link convention to the module
        mod_id = f"mod-{module.replace('_', '-')}"
        conv_edges.append({
            "source": mod_id,
            "target": pattern_id,
            "relation": "FOLLOWS_CONVENTION",
            "assertion": f"{module} follows a {exc_type} convention for error handling",
        })
        
        # Link convention to each function that follows it
        for fr_node, _ in unique_raises:
            conv_edges.append({
                "source": pattern_id,
                "target": fr_node["id"],
                "relation": "EXEMPLIFIES",
                "assertion": f"{fr_node['label']} exemplifies this {exc_type} convention",
            })
    
    # Extract cross-module access conventions from RUNTIME_IMPORT edges
    for e in edges:
        if e.get("relation") == "RUNTIME_IMPORT" and e.get("bridge"):
            # Create a cross-module access convention
            src_parts = e["source"].split("-")
            src_module = src_parts[0] if src_parts else ""
            tgt_module = e["target"].replace("mod-", "")
            
            access_id = f"convention-cross-module-{src_module}-{tgt_module}"
            # Don't duplicate
            if any(n["id"] == access_id for n in conv_nodes):
                continue
            
            # Normalize module name for function reference (user-service -> user_service)
            tgt_mod_norm = tgt_module.replace('-', '_')
            src_mod_norm = src_module.replace('-', '_')
            access_conv = {
                "id": access_id,
                "type": "convention",
                "label": f"{src_mod_norm} → {tgt_mod_norm} access convention",
                "natural_language": (
                    f"Cross-module access convention: {src_mod_norm} accesses {tgt_mod_norm} functions "
                    f"via a lazy import pattern. Use _get_{tgt_mod_norm}() (returns the module) to access "
                    f"{tgt_mod_norm} functions from {src_mod_norm}. Do NOT import {tgt_mod_norm} directly at the top level. "
                    f"Do NOT redefine {tgt_mod_norm} functions. Example: svc = _get_{tgt_mod_norm}(); svc.some_function(args)."
                ),
                "module": src_module,
                "domain": "conventions",
            }
            conv_nodes.append(access_conv)
            conv_edges.append({
                "source": e["source"],
                "target": access_id,
                "relation": "FOLLOWS_CONVENTION",
                "assertion": f"{src_module} uses lazy import to access {tgt_module}",
            })
    
    return {"nodes": conv_nodes, "edges": conv_edges}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 extract_code_kg.py <repo-path> [output-path]", file=sys.stderr)
        sys.exit(1)

    repo_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None

    kg = extract_kg(repo_path)

    # Deduplicate nodes and edges
    seen_node_ids = set()
    unique_nodes = []
    for n in kg["nodes"]:
        if n["id"] not in seen_node_ids:
            seen_node_ids.add(n["id"])
            unique_nodes.append(n)
    kg["nodes"] = unique_nodes

    json_str = json.dumps(kg, indent=2)

    if output_path:
        Path(output_path).write_text(json_str)
        print(f"✓ Extracted {len(kg['nodes'])} nodes, {len(kg['edges'])} edges → {output_path}", file=sys.stderr)
    else:
        print(json_str)