"""
Code Parser Service - Phase 3
Extracts code entities (classes, functions, imports) using tree-sitter
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

try:
    # Try newer API (tree-sitter-languages)
    from tree_sitter_languages import get_language, get_parser
    from tree_sitter import Node  # Node is always from tree_sitter
    USE_NEW_API = True
except ImportError:
    # Fallback to direct imports
    try:
        import tree_sitter_python as tspython
        from tree_sitter import Language, Parser, Node
        USE_NEW_API = False
    except ImportError:
        # Last resort - manual setup
        from tree_sitter import Language, Parser, Node
        USE_NEW_API = False

logger = logging.getLogger(__name__)


@dataclass
class ClassEntity:
    """Represents a class definition"""
    name: str
    file_path: str
    start_line: int
    end_line: int
    docstring: Optional[str] = None
    base_classes: List[str] = None
    methods: List[str] = None

    def __post_init__(self):
        if self.base_classes is None:
            self.base_classes = []
        if self.methods is None:
            self.methods = []


@dataclass
class FunctionEntity:
    """Represents a function or method definition"""
    name: str
    file_path: str
    start_line: int
    end_line: int
    parameters: List[str] = None
    return_type: Optional[str] = None
    docstring: Optional[str] = None
    parent_class: Optional[str] = None
    is_async: bool = False

    def __post_init__(self):
        if self.parameters is None:
            self.parameters = []


@dataclass
class ImportEntity:
    """Represents an import statement"""
    module: str
    names: List[str]
    is_from_import: bool
    file_path: str
    line_number: int


class CodeParserService:
    """
    Service for parsing code and extracting entities using tree-sitter

    Features:
    - Class extraction with inheritance
    - Function/method extraction with signatures
    - Import statement extraction
    - Docstring extraction
    - Multi-language support (Python, JavaScript, Java)
    """

    def __init__(self):
        """Initialize tree-sitter parsers"""
        self.parsers = {}
        self._init_parsers()
        logger.info("Code Parser Service initialized")

    def _init_parsers(self):
        """Initialize language parsers"""
        try:
            if USE_NEW_API:
                # Using tree-sitter-languages package
                self.parsers['python'] = get_parser('python')
                logger.info("Python parser initialized (new API)")
            else:
                # Using direct language bindings
                try:
                    PY_LANGUAGE = Language(tspython.language())
                    python_parser = Parser(PY_LANGUAGE)
                    self.parsers['python'] = python_parser
                    logger.info("Python parser initialized (direct binding)")
                except Exception as e:
                    logger.error(f"Failed to initialize parser with direct binding: {e}")
                    # Try alternative method
                    try:
                        from tree_sitter_python import language
                        PY_LANGUAGE = Language(language())
                        python_parser = Parser(PY_LANGUAGE)
                        self.parsers['python'] = python_parser
                        logger.info("Python parser initialized (alternative method)")
                    except Exception as e2:
                        logger.error(f"All parser initialization methods failed: {e2}")

        except Exception as e:
            logger.error(f"Failed to initialize parsers: {e}")

    def parse_file(self, file_path: str, code: str, language: str = 'python') -> Optional[Any]:
        """
        Parse code file using tree-sitter

        Args:
            file_path: Path to the file
            code: Source code content
            language: Programming language

        Returns:
            Parse tree or None if failed
        """
        try:
            parser = self.parsers.get(language.lower())

            if not parser:
                logger.warning(f"No parser available for language: {language}")
                return None

            # Parse code
            tree = parser.parse(bytes(code, "utf8"))
            return tree

        except Exception as e:
            logger.error(f"Error parsing {file_path}: {e}")
            return None

    def extract_python_entities(
        self,
        file_path: str,
        code: str
    ) -> Dict[str, List]:
        """
        Extract all entities from Python code

        Args:
            file_path: Path to the Python file
            code: Source code content

        Returns:
            Dictionary with classes, functions, and imports
        """
        tree = self.parse_file(file_path, code, 'python')

        if not tree:
            return {"classes": [], "functions": [], "imports": []}

        root_node = tree.root_node

        # Extract entities
        classes = self._extract_classes(root_node, file_path, code)
        functions = self._extract_functions(root_node, file_path, code)
        imports = self._extract_imports(root_node, file_path, code)

        logger.info(f"Extracted from {file_path}: {len(classes)} classes, {len(functions)} functions, {len(imports)} imports")

        return {
            "classes": classes,
            "functions": functions,
            "imports": imports
        }

    def _extract_classes(
        self,
        node: Node,
        file_path: str,
        code: str
    ) -> List[ClassEntity]:
        """Extract class definitions"""
        classes = []

        # Find all class definitions
        class_nodes = self._find_nodes_by_type(node, 'class_definition')

        for class_node in class_nodes:
            try:
                # Class name
                name_node = class_node.child_by_field_name('name')
                class_name = code[name_node.start_byte:name_node.end_byte] if name_node else "Unknown"

                # Line numbers
                start_line = class_node.start_point[0] + 1
                end_line = class_node.end_point[0] + 1

                # Base classes (inheritance)
                base_classes = []
                superclasses_node = class_node.child_by_field_name('superclasses')
                if superclasses_node:
                    for child in superclasses_node.children:
                        if child.type == 'identifier':
                            base_classes.append(code[child.start_byte:child.end_byte])
                        elif child.type == 'attribute':
                            # Handle module.ClassName
                            base_classes.append(code[child.start_byte:child.end_byte])

                # Docstring
                docstring = self._extract_docstring(class_node, code)

                # Methods
                methods = []
                body = class_node.child_by_field_name('body')
                if body:
                    method_nodes = self._find_nodes_by_type(body, 'function_definition')
                    for method_node in method_nodes:
                        method_name_node = method_node.child_by_field_name('name')
                        if method_name_node:
                            method_name = code[method_name_node.start_byte:method_name_node.end_byte]
                            methods.append(method_name)

                classes.append(ClassEntity(
                    name=class_name,
                    file_path=file_path,
                    start_line=start_line,
                    end_line=end_line,
                    docstring=docstring,
                    base_classes=base_classes,
                    methods=methods
                ))

            except Exception as e:
                logger.error(f"Error extracting class: {e}")

        return classes

    def _extract_functions(
        self,
        node: Node,
        file_path: str,
        code: str,
        parent_class: Optional[str] = None
    ) -> List[FunctionEntity]:
        """Extract function/method definitions"""
        functions = []

        # Find function definitions (top-level only if no parent_class)
        if parent_class is None:
            # Only top-level functions
            function_nodes = []
            for child in node.children:
                if child.type == 'function_definition':
                    function_nodes.append(child)
        else:
            # All functions (for class methods)
            function_nodes = self._find_nodes_by_type(node, 'function_definition')

        for func_node in function_nodes:
            try:
                # Function name
                name_node = func_node.child_by_field_name('name')
                func_name = code[name_node.start_byte:name_node.end_byte] if name_node else "Unknown"

                # Skip if it's inside a class and we're looking for top-level functions
                if parent_class is None:
                    # Check if function is inside a class
                    parent = func_node.parent
                    while parent:
                        if parent.type == 'class_definition':
                            # Skip this function, it's a method
                            break
                        parent = parent.parent
                    else:
                        # Not inside a class, it's a top-level function
                        pass

                    if parent and parent.type == 'class_definition':
                        continue

                # Line numbers
                start_line = func_node.start_point[0] + 1
                end_line = func_node.end_point[0] + 1

                # Parameters
                parameters = []
                params_node = func_node.child_by_field_name('parameters')
                if params_node:
                    for child in params_node.children:
                        if child.type == 'identifier':
                            param_name = code[child.start_byte:child.end_byte]
                            if param_name != 'self' and param_name != 'cls':
                                parameters.append(param_name)
                        elif child.type == 'typed_parameter':
                            # Handle type-annotated parameters
                            for subchild in child.children:
                                if subchild.type == 'identifier':
                                    param_name = code[subchild.start_byte:subchild.end_byte]
                                    if param_name != 'self' and param_name != 'cls':
                                        parameters.append(param_name)
                                    break

                # Return type
                return_type = None
                return_type_node = func_node.child_by_field_name('return_type')
                if return_type_node:
                    return_type = code[return_type_node.start_byte:return_type_node.end_byte]

                # Docstring
                docstring = self._extract_docstring(func_node, code)

                # Check if async
                is_async = False
                for child in func_node.children:
                    if child.type == 'async':
                        is_async = True
                        break

                functions.append(FunctionEntity(
                    name=func_name,
                    file_path=file_path,
                    start_line=start_line,
                    end_line=end_line,
                    parameters=parameters,
                    return_type=return_type,
                    docstring=docstring,
                    parent_class=parent_class,
                    is_async=is_async
                ))

            except Exception as e:
                logger.error(f"Error extracting function: {e}")

        return functions

    def _extract_imports(
        self,
        node: Node,
        file_path: str,
        code: str
    ) -> List[ImportEntity]:
        """Extract import statements"""
        imports = []

        # Find import statements
        import_nodes = self._find_nodes_by_type(node, 'import_statement')
        from_import_nodes = self._find_nodes_by_type(node, 'import_from_statement')

        # Regular imports (import x, import y)
        for import_node in import_nodes:
            try:
                line_number = import_node.start_point[0] + 1

                for child in import_node.children:
                    if child.type == 'dotted_name' or child.type == 'identifier':
                        module = code[child.start_byte:child.end_byte]
                        imports.append(ImportEntity(
                            module=module,
                            names=[],
                            is_from_import=False,
                            file_path=file_path,
                            line_number=line_number
                        ))

            except Exception as e:
                logger.error(f"Error extracting import: {e}")

        # From imports (from x import y, z)
        for from_node in from_import_nodes:
            try:
                line_number = from_node.start_point[0] + 1

                # Module name
                module_node = from_node.child_by_field_name('module_name')
                module = code[module_node.start_byte:module_node.end_byte] if module_node else "Unknown"

                # Imported names
                names = []
                for child in from_node.children:
                    if child.type == 'dotted_name' or child.type == 'identifier':
                        # Skip the module name
                        if child == module_node:
                            continue
                        name = code[child.start_byte:child.end_byte]
                        if name not in ['from', 'import']:
                            names.append(name)

                imports.append(ImportEntity(
                    module=module,
                    names=names,
                    is_from_import=True,
                    file_path=file_path,
                    line_number=line_number
                ))

            except Exception as e:
                logger.error(f"Error extracting from import: {e}")

        return imports

    def _extract_docstring(self, node: Node, code: str) -> Optional[str]:
        """Extract docstring from a node"""
        try:
            body = node.child_by_field_name('body')
            if body and len(body.children) > 0:
                first_statement = body.children[0]
                if first_statement.type == 'expression_statement':
                    expr = first_statement.children[0]
                    if expr.type == 'string':
                        docstring = code[expr.start_byte:expr.end_byte]
                        # Remove quotes
                        docstring = docstring.strip('"""').strip("'''").strip('"').strip("'")
                        return docstring.strip()
        except:
            pass
        return None

    def _find_nodes_by_type(self, node: Node, node_type: str) -> List[Node]:
        """Recursively find all nodes of a specific type"""
        results = []

        if node.type == node_type:
            results.append(node)

        for child in node.children:
            results.extend(self._find_nodes_by_type(child, node_type))

        return results


# Singleton instance
code_parser_service = CodeParserService()