"""GitHub Pages için tarayıcı sürümünü hazırla."""

from pathlib import Path

from .server import STATIC, prompt_module

DOCS = STATIC.parent.parent / "docs"
STATIC_CONFIG = b'export const staticMode = true;\n'


def site_files():
    files = {path.relative_to(STATIC): path.read_bytes()
             for path in STATIC.rglob("*") if path.is_file()}
    files[Path("config.mjs")] = STATIC_CONFIG
    files[Path("prompt.mjs")] = prompt_module()
    files[Path(".nojekyll")] = b""
    index = Path("index.html")
    files[index] = files[index].replace(
        b'<meta charset="utf-8">',
        b'<meta charset="utf-8">\n'
        b'  <meta http-equiv="Content-Security-Policy" '
        b'content="default-src \'self\'; connect-src \'none\'; '
        b'base-uri \'none\'; form-action \'none\'">',
    )
    return files


def build_site():
    for relative, content in site_files().items():
        path = DOCS / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
