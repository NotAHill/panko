"""Every text file Panko reads or writes says UTF-8. Without it Windows uses its own code page (cp1252), and the
first Arabic word in a preset, a card or a cache crashes the read (CI's Windows install check found the first)."""
import ast
from pathlib import Path

import panko

SRC = Path(panko.__file__).parent
NOT_FILES = {"webbrowser", "os", "Image", "z", "zf", "zipfile", "tarfile"}    # `.open` that isn't a text file


def _missing(path: Path) -> list[str]:
    out = []
    for n in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if not isinstance(n, ast.Call):
            continue
        kw = {k.arg for k in n.keywords}
        if "encoding" in kw or None in kw:
            continue
        f = n.func
        name = f.attr if isinstance(f, ast.Attribute) else f.id if isinstance(f, ast.Name) else ""
        if name in ("read_text", "write_text"):
            out.append(f"{path.relative_to(SRC)}:{n.lineno} {name}")
        elif name in ("open", "fdopen"):
            if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id in NOT_FILES - {"os"}:
                continue
            if isinstance(f, ast.Attribute) and f.attr == "open" and isinstance(f.value, ast.Name) and f.value.id == "os":
                continue                                       # os.open gives a descriptor; its fdopen is checked
            args = n.args[1:] if name == "fdopen" or isinstance(f, ast.Name) else n.args
            mode = args[0] if args else next((k.value for k in n.keywords if k.arg == "mode"), None)
            if isinstance(mode, ast.Constant) and "b" in str(mode.value):
                continue
            if mode is not None and not isinstance(mode, ast.Constant):
                continue                                       # a path or a mode only known when it runs
            out.append(f"{path.relative_to(SRC)}:{n.lineno} {name}")
        elif name == "run" and "text" in kw:
            out.append(f"{path.relative_to(SRC)}:{n.lineno} subprocess text")
    return out


def test_every_text_read_and_write_names_utf8():
    missing = [m for p in sorted(SRC.rglob("*.py")) for m in _missing(p)]
    assert not missing, "add encoding=\"utf-8\":\n" + "\n".join(missing)
