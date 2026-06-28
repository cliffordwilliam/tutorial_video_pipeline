# Ported from /home/clif/repositories/ttv/util/highlight.py, which already solved
# real tree-sitter syntax highlighting - trimmed to Python only (this project never
# highlights markdown) and with the Catppuccin Mocha palette resolved to plain hex
# strings instead of depending on the `catppuccin` package for a handful of fixed
# constants.
#
# Highlighting runs in two passes:
#   1. AST query - tree-sitter labels each byte with a capture name via highlights.scm
#      + _CUSTOM_PATTERNS. _PRIORITY controls which label wins when a byte matches
#      multiple captures (later = more specific = wins).
#   2. Builtin upgrade - tokens still labeled "variable" that match _BUILTINS get
#      upgraded to "builtin". Needed because builtins in type annotation position
#      (e.g. `-> list[Foo]`) sit outside call expressions and the query can't reach them.

import importlib.resources

import tree_sitter_python as tspython
from tree_sitter import Language, Parser, Query, QueryCursor

_COLORS: dict[str, str] = {
    "keyword": "#cba6f7",
    "constant.builtin": "#cba6f7",
    "function": "#89b4fa",
    "function.method": "#74c7ec",
    "function.builtin": "#f9e2af",
    "property": "#74c7ec",
    "type": "#f9e2af",
    "constructor": "#f9e2af",
    "constant": "#fab387",
    "builtin": "#f9e2af",
    "module": "#b4befe",
    "parameter": "#eba0ac",
    "string": "#a6e3a1",
    "escape": "#94e2d5",
    "comment": "#7f849c",
    "number": "#fab387",
    "operator": "#cdd6f4",
    "variable": "#cdd6f4",
    "punctuation.special": "#cba6f7",
    "punctuation.delimiter": "#7f849c",
    "string.escape": "#94e2d5",
    "default": "#cdd6f4",
}

# Ordered least -> most specific; later passes overwrite earlier ones
_PRIORITY: list[str] = [
    "variable",
    "number",
    "string",
    "escape",
    "comment",
    "operator",
    "property",
    "parameter",
    "constant.builtin",
    "function",
    "constructor",  # PascalCase overwrites @function for class-like names
    "module",  # lavender for imports beats yellow PascalCase heuristic
    "constant",  # peach ALL_CAPS beats yellow PascalCase heuristic
    "function.method",
    "type",
    "function.builtin",
    "keyword",
    "punctuation.special",
    "punctuation.delimiter",
    "string.escape",
]

_BUILTINS: frozenset[str] = frozenset(
    {
        "abs", "aiter", "all", "anext", "any", "ascii", "bin", "bool", "breakpoint",
        "bytearray", "bytes", "callable", "chr", "classmethod", "compile", "complex",
        "delattr", "dict", "dir", "divmod", "enumerate", "eval", "exec", "filter",
        "float", "format", "frozenset", "getattr", "globals", "hasattr", "hash",
        "help", "hex", "id", "input", "int", "isinstance", "issubclass", "iter",
        "len", "list", "locals", "map", "max", "memoryview", "min", "next", "object",
        "oct", "open", "ord", "pow", "print", "property", "range", "repr", "reversed",
        "round", "set", "setattr", "slice", "sorted", "staticmethod", "str", "sum",
        "super", "tuple", "type", "vars", "zip",
        "ArithmeticError", "AssertionError", "AttributeError", "BaseException",
        "BaseExceptionGroup", "BlockingIOError", "BrokenPipeError", "BufferError",
        "BytesWarning", "ChildProcessError", "ConnectionAbortedError",
        "ConnectionError", "ConnectionRefusedError", "ConnectionResetError",
        "DeprecationWarning", "EOFError", "EnvironmentError", "Exception",
        "ExceptionGroup", "FileExistsError", "FileNotFoundError",
        "FloatingPointError", "FutureWarning", "GeneratorExit", "IOError",
        "ImportError", "ImportWarning", "IndentationError", "IndexError",
        "InterruptedError", "IsADirectoryError", "KeyError", "KeyboardInterrupt",
        "LookupError", "MemoryError", "ModuleNotFoundError", "NameError",
        "NotADirectoryError", "NotImplemented", "NotImplementedError", "OSError",
        "OverflowError", "PendingDeprecationWarning", "PermissionError",
        "ProcessLookupError", "RecursionError", "ReferenceError", "ResourceWarning",
        "RuntimeError", "RuntimeWarning", "StopAsyncIteration", "StopIteration",
        "SyntaxError", "SyntaxWarning", "SystemError", "SystemExit", "TabError",
        "TimeoutError", "TypeError", "UnboundLocalError", "UnicodeDecodeError",
        "UnicodeEncodeError", "UnicodeError", "UnicodeTranslateError",
        "UnicodeWarning", "UserWarning", "ValueError", "Warning", "ZeroDivisionError",
    }
)

_LANG_PACKAGES: dict[str, str] = {"python": "tree_sitter_python"}
_LANG_ALIASES: dict[str, str] = {"py": "python"}

# Extra patterns appended on top of the bundled highlights.scm - only needed
# because the bundled query misses imports/parameters.
_CUSTOM_PATTERNS: dict[str, str] = {
    "python": """
(import_from_statement (dotted_name (identifier) @module))
(import_statement (dotted_name (identifier) @module))

(parameters (identifier) @parameter)
(parameters (typed_parameter (identifier) @parameter))
(parameters (default_parameter name: (identifier) @parameter))
(parameters (typed_default_parameter name: (identifier) @parameter))
(keyword_argument name: (identifier) @parameter)
""",
}

_PY_LANGUAGE = Language(tspython.language())
_LANGUAGES: dict[str, Language] = {"python": _PY_LANGUAGE}
_PARSERS: dict[str, Parser] = {"python": Parser(_PY_LANGUAGE)}

_compiled_queries: dict[str, Query] = {}


def _normalize(lang: str) -> str:
    return _LANG_ALIASES.get(lang, lang)


def supported(lang: str) -> bool:
    return _normalize(lang) in _LANGUAGES


def _load_query(lang: str) -> Query:
    pkg = _LANG_PACKAGES[lang]
    base = importlib.resources.files(pkg).joinpath("queries/highlights.scm").read_text(encoding="utf-8")
    return Query(_LANGUAGES[lang], base + _CUSTOM_PATTERNS.get(lang, ""))


def _get_query(lang: str) -> Query:
    if lang not in _compiled_queries:
        _compiled_queries[lang] = _load_query(lang)
    return _compiled_queries[lang]


def token_color(label: str) -> str:
    return _COLORS.get(label, _COLORS["default"])


def tokenize(code: str, lang: str) -> list[tuple[str, str]]:
    lang = _normalize(lang)
    source = code.encode("utf-8")
    if not source:
        return []

    tree = _PARSERS[lang].parse(source)
    raw_captures: dict[str, list] = QueryCursor(_get_query(lang)).captures(tree.root_node)

    # Paint each byte with a capture name; more specific passes overwrite less specific
    byte_labels: list[str | None] = [None] * len(source)
    for label in _PRIORITY:
        for node in raw_captures.get(label, []):
            s, e = node.start_byte, min(node.end_byte, len(source))
            byte_labels[s:e] = [label] * (e - s)

    # Collapse consecutive same-label runs into (label, text) pairs
    tokens: list[tuple[str, str]] = []
    i = 0
    while i < len(source):
        label = byte_labels[i] or "default"
        j = i + 1
        while j < len(source) and (byte_labels[j] or "default") == label:
            j += 1
        tokens.append((label, source[i:j].decode("utf-8", errors="replace")))
        i = j

    # Upgrade generic variable tokens that are known builtins
    return [
        ("builtin", v) if label == "variable" and v in _BUILTINS else (label, v) for label, v in tokens
    ]
