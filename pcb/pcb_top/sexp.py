"""Tiny S-expression reader/writer for KiCad files."""
import re
class Q(str):
    """A quoted string atom."""
def parse(text):
    toks = re.findall(r'\(|\)|"(?:\\.|[^"\\])*"|[^\s()]+', text)
    stack = [[]]
    for t in toks:
        if t == "(":
            stack.append([])
        elif t == ")":
            top = stack.pop(); stack[-1].append(top)
        elif t.startswith('"'):
            stack[-1].append(Q(t[1:-1].replace('\\"', '"').replace("\\\\", "\\")))
        else:
            stack[-1].append(t)
    return stack[0]
def esc(s): return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'
def dump(x, ind=0):
    if isinstance(x, list):
        simple = all(not isinstance(e, list) for e in x)
        if simple:
            return "(" + " ".join(dump(e) for e in x) + ")"
        out = "(" + " ".join(dump(e) for e in x[:1])
        for e in x[1:]:
            out += ("\n" + "  " * (ind + 1) + dump(e, ind + 1)) if isinstance(e, list) else " " + dump(e)
        return out + ")"
    if isinstance(x, Q): return esc(x)
    if isinstance(x, float): return f"{x:.4f}".rstrip("0").rstrip(".")
    return str(x)
def find(lst, key):
    return [e for e in lst if isinstance(e, list) and e and e[0] == key]
def first(lst, key):
    r = find(lst, key); return r[0] if r else None
