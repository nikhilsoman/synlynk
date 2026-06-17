# tests/test_static_scan.py
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "bin"))
import synlynk


# --- _extract_symbols ---

def test_extract_python_symbols(tmp_path):
    f = tmp_path / "app.py"
    f.write_text(
        "import os\n"
        "MY_CONST = 1\n"
        "class Foo:\n"
        "    pass\n"
        "def bar():\n"
        "    pass\n"
        "async def baz():\n"
        "    pass\n"
    )
    syms = synlynk._extract_symbols(str(f))
    types = {s["symbol_type"] for s in syms}
    names = {s["symbol"] for s in syms}
    assert "constant" in types
    assert "class" in types
    assert "function" in types
    assert "async_function" in types
    assert "Foo" in names
    assert "bar" in names
    assert "baz" in names
    assert "MY_CONST" in names


def test_extract_typescript_symbols(tmp_path):
    f = tmp_path / "service.ts"
    f.write_text(
        "export class AuthService {}\n"
        "export function verifyToken(t: string) {}\n"
        "export interface TokenPayload {}\n"
        "export type UserId = string;\n"
        "export enum Role { Admin, User }\n"
        "export const DB_URL = '';\n"
    )
    syms = synlynk._extract_symbols(str(f))
    names = {s["symbol"] for s in syms}
    types = {s["symbol_type"] for s in syms}
    assert "AuthService" in names
    assert "verifyToken" in names
    assert "TokenPayload" in names
    assert "UserId" in names
    assert "Role" in names
    assert "DB_URL" in names
    assert "interface" in types
    assert "type" in types
    assert "enum" in types


def test_extract_go_symbols(tmp_path):
    f = tmp_path / "main.go"
    f.write_text(
        "package main\n"
        "func main() {}\n"
        "type Server struct{}\n"
        "type Handler interface{}\n"
    )
    syms = synlynk._extract_symbols(str(f))
    names = {s["symbol"] for s in syms}
    types = {s["symbol_type"] for s in syms}
    assert "main" in names
    assert "Server" in names
    assert "Handler" in names
    assert "function" in types
    assert "struct" in types
    assert "interface" in types


def test_extract_rust_symbols(tmp_path):
    f = tmp_path / "lib.rs"
    f.write_text(
        "pub fn connect() {}\n"
        "pub struct Config {}\n"
        "pub trait Adapter {}\n"
        "pub enum State { Active, Idle }\n"
        "pub type Result<T> = std::result::Result<T, Error>;\n"
    )
    syms = synlynk._extract_symbols(str(f))
    names = {s["symbol"] for s in syms}
    assert "connect" in names
    assert "Config" in names
    assert "Adapter" in names
    assert "State" in names
    assert "Result" in names


def test_extract_shell_symbols(tmp_path):
    f = tmp_path / "deploy.sh"
    f.write_text(
        "#!/bin/bash\n"
        "setup_env() {\n"
        "  echo hi\n"
        "}\n"
        "run_deploy() {}\n"
    )
    syms = synlynk._extract_symbols(str(f))
    names = {s["symbol"] for s in syms}
    assert "setup_env" in names
    assert "run_deploy" in names


def test_extract_generic_returns_empty(tmp_path):
    f = tmp_path / "data.csv"
    f.write_text("col1,col2\n1,2\n")
    syms = synlynk._extract_symbols(str(f))
    assert syms == []


def test_extract_max_300_lines(tmp_path):
    content = "\n".join(f"x = {i}" for i in range(295)) + "\n"
    content += "def visible():\n    pass\n"
    f = tmp_path / "big.py"
    f.write_text(content)
    syms = synlynk._extract_symbols(str(f))
    names = {s["symbol"] for s in syms}
    assert "visible" in names


def test_extract_missing_file_returns_empty():
    syms = synlynk._extract_symbols("/nonexistent/path/file.py")
    assert syms == []


def test_extract_line_numbers(tmp_path):
    f = tmp_path / "mod.py"
    f.write_text("class Alpha:\n    pass\ndef beta():\n    pass\n")
    syms = synlynk._extract_symbols(str(f))
    by_name = {s["symbol"]: s["line"] for s in syms}
    assert by_name["Alpha"] == 1
    assert by_name["beta"] == 3
