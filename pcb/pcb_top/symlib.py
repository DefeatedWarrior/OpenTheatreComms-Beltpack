"""Load KiCad library symbols, flatten 'extends', and report pin connection points."""
import copy, os
from sexp import parse, find, first, Q
LIBDIR = "/usr/share/kicad/symbols"
_cache = {}
def _lib(lib):
    if lib not in _cache:
        _cache[lib] = {e[1]: e for e in parse(open(os.path.join(LIBDIR, lib + ".kicad_sym")).read())[0] if isinstance(e, list) and e[0] == "symbol"}
    return _cache[lib]
def get(lib_id):
    lib, name = lib_id.split(":")
    syms = _lib(lib); s = copy.deepcopy(syms[name])
    ext = first(s, "extends")
    if ext:
        parent = copy.deepcopy(syms[ext[1]])
        props = find(s, "property")
        body = [e for e in parent[2:] if not (isinstance(e, list) and e[0] == "property")]
        for e in body:
            if isinstance(e, list) and e[0] == "symbol":
                e[1] = Q(e[1].replace(ext[1], name, 1))
        s = ["symbol", Q(name)] + props + body
    out = copy.deepcopy(s); out[1] = Q(lib_id)
    return out
def pins(sym):
    """[(number, name, x, y, angle, type)] for unit 1 / common unit, body style 1."""
    name = sym[1].split(":")[-1]; res = []
    for sub in find(sym, "symbol"):
        parts = sub[1].rsplit("_", 2)
        unit, conv = int(parts[-2]), int(parts[-1])
        if unit not in (0, 1) or conv not in (0, 1): continue
        for p in find(sub, "pin"):
            at = first(p, "at"); nm = first(p, "name"); nb = first(p, "number")
            res.append((str(nb[1]), str(nm[1]), float(at[1]), float(at[2]), float(at[3]) if len(at) > 3 else 0.0, p[1]))
    return res
