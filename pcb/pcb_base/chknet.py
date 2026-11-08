"""Compare a KiCad netlist export with design.py: every named net must hold exactly the expected pins."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sexp import parse, find, first
import symlib
from design import C

net = parse(open(sys.argv[1]).read())[0]
nets = {}
for n in find(first(net, "nets"), "net"):
    nets[str(first(n, "name")[1]).lstrip("/")] = sorted(f"{first(x, 'ref')[1]}.{first(x, 'pin')[1]}" for x in find(n, "node"))
exp = {}
for c in C:
    for num, name, *_ in symlib.pins(symlib.get(c["lib_id"])):
        nm = c["pins"].get(num, c["pins"].get(name))
        if nm: exp.setdefault(nm, []).append(f"{c['ref']}.{num}")
bad = [nm for nm, nodes in exp.items() if nets.get(nm) != sorted(nodes)]
for nm in bad: print("MISMATCH", nm, sorted(exp[nm])[:8], nets.get(nm, [])[:8])
extra = [k for k in nets if k not in exp and not k.startswith("unconnected")]
print("expected", len(exp), "got", len(nets), "mismatches", len(bad), "extra", extra,
      "unconnected", sum(k.startswith("unconnected") for k in nets))
sys.exit(1 if bad or extra else 0)
