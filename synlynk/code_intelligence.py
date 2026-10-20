"""Code intelligence framework for synlynk context assembly.

Integrates SCIP, Tree-sitter, and Glean for code intelligence and context assembly.
"""
import json, logging, re, dataclasses
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)

@dataclasses.dataclass
class Symbol:
    name: str
    kind: str
    path: str
    line: int
    col: int
    scope: str = ""
    definition: Optional[str] = None
    docstring: Optional[str] = None
    references: Set[str] = dataclasses.field(default_factory=set)

@dataclasses.dataclass
class SymbolIndex:
    symbols: Dict[str, List[Symbol]] = dataclasses.field(default_factory=dict)
    by_path: Dict[str, List[Symbol]] = dataclasses.field(default_factory=dict)
    graph: Dict[str, Set[str]] = dataclasses.field(default_factory=dict)
    
    def add_symbol(self, sym: Symbol):
        if sym.name not in self.symbols:
            self.symbols[sym.name] = []
        self.symbols[sym.name].append(sym)
        if sym.path not in self.by_path:
            self.by_path[sym.path] = []
        self.by_path[sym.path].append(sym)
    
    def lookup_by_name(self, name: str) -> List[Symbol]:
        return self.symbols.get(name, [])
    
    def lookup_by_path(self, path: str) -> List[Symbol]:
        return self.by_path.get(path, [])
        
    def get_references(self, symbol_name: str) -> Set[str]:
        return self.graph.get(symbol_name, set())
        
    def add_reference(self, from_symbol: str, to_symbol: str) -> None:
        if from_symbol not in self.graph:
            self.graph[from_symbol] = set()
        self.graph[from_symbol].add(to_symbol)

class SCIPIndexer:
    def __init__(self):
        self.index = SymbolIndex()
        self.scip_documents = {}
    
    def parse_scip_document(self, data: str) -> Dict:
        try:
            return json.loads(data)
        except Exception as e:
            logger.error(f"Parse error: {e}")
            return {}
    
    def import_scip_index(self, scip_json: Dict):
        for doc in scip_json.get("documents", []):
            path = doc.get("relative_path", "")
            for sym_info in doc.get("symbols", []):
                symbol_name = sym_info.get("symbol", "")
                if symbol_name:
                    sym = self._parse_scip_symbol(symbol_name, path)
                    if sym:
                        self.index.add_symbol(sym)
    
    def _parse_scip_symbol(self, scip_sym: str, path: str) -> Optional[Symbol]:
        parts = scip_sym.rsplit("#", 1)
        name = parts[-1].split("/")[-1] if parts else ""
        return Symbol(name=name, kind="function", path=path, line=0, col=0) if name else None
        
    def _infer_symbol_kind(self, name: str, scope: str) -> str:
        if scope:
            return "method"
        if name and name.startswith("__"):
            return "dunder"
        if name and name[0].isupper():
            return "class"
        return "function"
        
    def query_symbol(self, name: str, path: Optional[str] = None) -> List[Symbol]:
        symbols = self.index.lookup_by_name(name)
        if path:
            symbols = [s for s in symbols if s.path == path]
        return symbols

class TreesitterExtractor:
    PATTERNS = {".py": [r"^\s*(def|class)\s+(\w+)"]}
    
    def __init__(self):
        self.parsed = {}
        self.index = SymbolIndex()
    
    def extract_symbols(self, path: str, content: str) -> List[Symbol]:
        symbols = []
        ext = "." + path.split(".")[-1] if "." in path else ""
        lines = content.split("\n")
        for line_no, line in enumerate(lines, 1):
            for pat in self.PATTERNS.get(ext, []):
                m = re.search(pat, line)
                if m and len(m.groups()) > 1 and m.group(2):
                    sym = Symbol(name=m.group(2), kind="func", path=path, line=line_no, col=0)
                    symbols.append(sym)
                    self.index.add_symbol(sym)
        self.parsed[path] = symbols
        return symbols
        
    def get_symbols_in_file(self, path: str) -> List[Symbol]:
        return self.parsed.get(path, [])

class CodeKnowledgeGraph:
    def __init__(self):
        self.symbols = {}
        self.relationships = {}
        self.file_imports = {}
    
    def add_symbol(self, sym: Symbol):
        key = f"{sym.path}:{sym.name}"
        self.symbols[key] = sym
        
    def add_relationship(self, from_sym: str, rel_type: str, to_sym: str):
        if from_sym not in self.relationships:
            self.relationships[from_sym] = []
        self.relationships[from_sym].append((from_sym, rel_type, to_sym))
        
    def resolve_symbol_context(self, name: str, path: str) -> Dict:
        key = f"{path}:{name}"
        sym = self.symbols.get(key)
        if not sym:
            return {}
        return {"symbol": name, "kind": sym.kind, "path": path, "line": sym.line}

class ContextResolver:
    def __init__(self):
        self.scip_indexer = SCIPIndexer()
        self.treesitter = TreesitterExtractor()
        self.knowledge_graph = CodeKnowledgeGraph()
    
    def assemble_symbol_context(self, name: str, path: Optional[str] = None) -> Dict:
        scip_results = self.scip_indexer.query_symbol(name, path)
        ts_results = self.treesitter.get_symbols_in_file(path) if path else []
        ts_results = [s for s in ts_results if s.name == name]
        all_syms = scip_results + ts_results
        if not all_syms:
            return {}
        return {"symbol": name, "kind": all_syms[0].kind}
        
    def assemble_file_context(self, path: str, content: str) -> Dict:
        syms = self.treesitter.extract_symbols(path, content)
        return {"file": path, "symbols": [{"name": s.name, "kind": s.kind} for s in syms]}
