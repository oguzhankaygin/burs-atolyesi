"""GitHub Pages için tarayıcı sürümünü hazırla."""

import json
from pathlib import Path

from .server import STATIC, prompt_module

DOCS = STATIC.parent.parent / "docs"
SW_TEMPLATE = """"use strict";

// Ağ öncelikli önbellek: çevrimiçiyken güncel dosya, bağlantı yokken son kopya.
const CACHE = "burs-atolyesi-v1";
const DOSYALAR = __DOSYALAR__;

self.addEventListener("install", event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(DOSYALAR)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", event => {
  event.waitUntil(caches.keys()
    .then(keys => Promise.all(keys.filter(key => key.startsWith("burs-atolyesi-") && key !== CACHE)
      .map(key => caches.delete(key))))
    .then(() => self.clients.claim()));
});

self.addEventListener("fetch", event => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || url.origin !== self.location.origin) return;
  event.respondWith((async () => {
    const cache = await caches.open(CACHE);
    try {
      const yanit = await fetch(event.request);
      if (yanit.ok) cache.put(event.request, yanit.clone()).catch(() => {});
      return yanit;
    } catch {
      return (await cache.match(event.request, { ignoreSearch: true })) || Response.error();
    }
  })());
});
"""
STATIC_CONFIG = b'export const staticMode = true;\n'


def site_files():
    files = {path.relative_to(STATIC): path.read_bytes()
             for path in STATIC.rglob("*") if path.is_file()}
    files[Path("config.mjs")] = STATIC_CONFIG
    files[Path("prompt.mjs")] = prompt_module()
    files[Path(".nojekyll")] = b""
    onbellek = ["./"] + sorted(f"./{yol.as_posix()}" for yol in files if yol.name != ".nojekyll")
    files[Path("sw.js")] = SW_TEMPLATE.replace("__DOSYALAR__", json.dumps(onbellek)).encode()
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
