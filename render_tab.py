"""Wrap a tuttut 6-line ASCII tab into readable systems of N measures.

Usage: python render_tab.py <tab.txt> [measures_per_line=4] [first_measure=0] [count=all]
"""
import sys
from pathlib import Path

src = Path(sys.argv[1]); per = int(sys.argv[2]) if len(sys.argv) > 2 else 4
start = int(sys.argv[3]) if len(sys.argv) > 3 else 0
count = int(sys.argv[4]) if len(sys.argv) > 4 else 10**9
lines = [l.rstrip("\n") for l in src.read_text().splitlines() if l.strip()]
# tuttut lines look like "E ||--0--|--2--|": drop the string label and the outer bar lines
bars = [l.split("||", 1)[-1].strip("|").split("|") for l in lines]  # bars[string][measure]
n = min(len(b) for b in bars)
sel = range(start, min(n, start + count))
out = []
for i in range(sel.start, sel.stop, per):
    for s, name in enumerate("eBGDAE"):
        out.append(f"{name}|" + "|".join(bars[s][j] for j in range(i, min(i + per, sel.stop))) + "|")
    out.append(f"   ^ measures {i}-{min(i+per, sel.stop)-1}")
    out.append("")
print("\n".join(out))
