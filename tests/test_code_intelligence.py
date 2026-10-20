"""Tests for code intelligence (SCIP, Tree-sitter, Glean)."""
import pytest
from synlynk.code_intelligence import Symbol, SymbolIndex, SCIPIndexer, TreesitterExtractor, CodeKnowledgeGraph, ContextResolver

class TestSymbolIndex:
    def test_add_and_lookup_by_name(self):
        idx = SymbolIndex()
        sym = Symbol(name="foo", kind="function", path="test.py", line=10, col=0)
        idx.add_symbol(sym)
        assert len(idx.lookup_by_name("foo")) == 1
    
    def test_multiple_symbols(self):
        idx = SymbolIndex()
        idx.add_symbol(Symbol(name="m", kind="method", path="a.py", line=5, col=0))
        idx.add_symbol(Symbol(name="m", kind="method", path="b.py", line=10, col=0))
        assert len(idx.lookup_by_name("m")) == 2
    
    def test_lookup_by_path(self):
        idx = SymbolIndex()
        idx.add_symbol(Symbol(name="foo", kind="function", path="test.py", line=1, col=0))
        idx.add_symbol(Symbol(name="bar", kind="function", path="test.py", line=5, col=0))
        assert len(idx.lookup_by_path("test.py")) == 2
    
    def test_reference_graph(self):
        idx = SymbolIndex()
        idx.add_reference("a", "b")
        idx.add_reference("a", "c")
        assert idx.get_references("a") == {"b", "c"}

class TestSCIPIndexer:
    def test_parse_document(self):
        indexer = SCIPIndexer()
        doc = indexer.parse_scip_document('{"documents": []}')
        assert "documents" in doc
    
    def test_import_symbols(self):
        data = {"documents": [{"relative_path": "m.py", "symbols": [{"symbol": "m/C#method"}]}]}
        indexer = SCIPIndexer()
        indexer.import_scip_index(data)
        assert len(indexer.query_symbol("method")) > 0
    
    def test_symbol_parsing(self):
        indexer = SCIPIndexer()
        sym = indexer._parse_scip_symbol("m/C#method", "test.py")
        assert sym.name == "method"

class TestTreesitterExtractor:
    def test_extract_python(self):
        code = "def f():\n    pass\nclass C:\n    pass"
        e = TreesitterExtractor()
        syms = e.extract_symbols("test.py", code)
        names = {s.name for s in syms}
        assert "f" in names or "C" in names
    
    def test_line_tracking(self):
        code = "def f1():\n    pass\ndef f2():\n    pass"
        e = TreesitterExtractor()
        syms = e.extract_symbols("test.py", code)
        assert all(s.line > 0 for s in syms)

class TestCodeKnowledgeGraph:
    def test_add_symbol(self):
        kg = CodeKnowledgeGraph()
        sym = Symbol(name="f", kind="function", path="test.py", line=10, col=0)
        kg.add_symbol(sym)
        assert "test.py:f" in kg.symbols
    
    def test_relationships(self):
        kg = CodeKnowledgeGraph()
        kg.add_relationship("a", "calls", "b")
        assert len(kg.relationships.get("a", [])) > 0

class TestContextResolver:
    def test_init(self):
        r = ContextResolver()
        assert r.scip_indexer is not None
        assert r.treesitter is not None
        assert r.knowledge_graph is not None
    
    def test_assemble_symbol(self):
        r = ContextResolver()
        r.treesitter.extract_symbols("test.py", "def f():\n    pass")
        ctx = r.assemble_symbol_context("f", "test.py")
        assert "symbol" in ctx
    
    def test_assemble_file(self):
        r = ContextResolver()
        code = "def f1():\n    pass\ndef f2():\n    pass"
        ctx = r.assemble_file_context("test.py", code)
        assert ctx["file"] == "test.py"
        assert "symbols" in ctx

class TestGleanCompatibility:
    def test_symbol_schema(self):
        sym = Symbol(name="x", kind="function", path="e.py", line=10, col=5)
        assert sym.name and sym.kind and sym.path and sym.line >= 0
    
    def test_xref_graph(self):
        idx = SymbolIndex()
        idx.add_symbol(Symbol(name="a", kind="module", path="a.py", line=1, col=0))
        idx.add_symbol(Symbol(name="b", kind="module", path="b.py", line=1, col=0))
        idx.add_reference("a", "b")
        assert "b" in idx.get_references("a")
