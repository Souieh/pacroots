#!/usr/bin/python
"""pacroots: your explicit packages (roots) and the dependencies each one exclusively owns.

Pure Python stdlib. Reads /var/lib/pacman/local directly: no pyalpm, no pip, no venv.
Usage: pacroots.py tui | html [-o FILE] [--no-open] | json
"""

__version__ = "0.1.0"

import argparse, json, os, re, subprocess, sys, tempfile, webbrowser
from collections import Counter
from pathlib import Path

DB = os.environ.get("PACROOTS_DB", "/var/lib/pacman/local")
VER = re.compile(r"[<>=].*")
HERE = os.path.dirname(os.path.realpath(__file__))
TEMPLATE = os.path.join(HERE, "template.html")


def human(n):
    for u in ("B", "KiB", "MiB", "GiB"):
        if n < 1024 or u == "GiB":
            return f"{n:.0f} B" if u == "B" else f"{n:.1f} {u}"
        n /= 1024


def load():
    pk = {}
    for e in os.listdir(DB):
        f = os.path.join(DB, e, "desc")
        if not os.path.isfile(f):
            continue
        d, k = {}, None
        with open(f, encoding="utf-8", errors="replace") as fh:
            for line in fh.read().splitlines():
                if len(line) > 2 and line[0] == line[-1] == "%":
                    k = line[1:-1]
                    d[k] = []
                elif line and k:
                    d[k].append(line)
        n = d["NAME"][0]
        pk[n] = dict(
            name=n,
            ver=d["VERSION"][0],
            desc=" ".join(d.get("DESC", [])),
            size=int((d.get("SIZE") or d.get("ISIZE") or ["0"])[0]),
            explicit=d.get("REASON", ["0"])[0] != "1",
            date=int((d.get("INSTALLDATE") or ["0"])[0]),
            depends=d.get("DEPENDS", []),
            provides=d.get("PROVIDES", []),
        )
    return pk


def analyze():
    pk = load()
    try:
        foreign = set(
            subprocess.run(
                ["pacman", "-Qmq"], capture_output=True, text=True
            ).stdout.split()
        )
    except OSError:
        foreign = set()
    prov = {}
    for n, p in pk.items():
        for x in [n] + p["provides"]:
            prov.setdefault(VER.sub("", x), []).append(n)

    def res(dep):
        k = VER.sub("", dep)
        return k if k in pk else (prov.get(k) or [None])[0]

    g = {n: {r for r in map(res, p["depends"]) if r and r != n} for n, p in pk.items()}
    roots = [n for n, p in pk.items() if p["explicit"]]
    rs = set(roots)
    clo = {}
    for r in roots:
        seen, st = set(), [r]
        while st:
            for y in g[st.pop()]:
                if y not in seen:
                    seen.add(y)
                    st.append(y)
        seen.discard(r)
        clo[r] = seen
    reach = Counter(x for c in clo.values() for x in c)
    rows = []
    for r in roots:
        p = pk[r]
        own = sorted(
            (x for x in clo[r] if reach[x] == 1 and x not in rs),
            key=lambda x: -pk[x]["size"],
        )
        sh = sorted(x for x in clo[r] if reach[x] > 1 or x in rs)
        rows.append(
            dict(
                name=r,
                ver=p["ver"],
                desc=p["desc"],
                size=p["size"],
                foreign=r in foreign,
                date=p["date"],
                excl=p["size"] + sum(pk[x]["size"] for x in own),
                owned=[
                    dict(name=x, size=pk[x]["size"], desc=pk[x]["desc"]) for x in own
                ],
                shared=sh,
            )
        )
    rows.sort(key=lambda r: -r["excl"])
    orphans = [
        dict(name=n, size=p["size"], desc=p["desc"])
        for n, p in pk.items()
        if not p["explicit"] and not reach[n]
    ]
    graph = {
        n: dict(
            size=p["size"], desc=p["desc"], by=reach[n], root=n in rs, deps=sorted(g[n])
        )
        for n, p in pk.items()
    }
    return dict(
        roots=rows,
        orphans=sorted(orphans, key=lambda o: -o["size"]),
        total=len(pk),
        graph=graph,
    )


def _load_template():
    """Load the HTML template from the adjacent template.html file."""
    with open(TEMPLATE, encoding="utf-8") as f:
        return f.read()


def tui(data):
    import curses

    G = data["graph"]
    opened = set()

    def build(q):
        rows = []

        def add(n, path, extra=""):
            g = G[n]
            cyc = n in path
            kids = [] if cyc else sorted(g["deps"], key=lambda x: -G[x]["size"])
            key = path + (n,)
            tag = (
                ""
                if not path
                else " [explicit]"
                if g["root"]
                else f" [shared x{g['by']}]"
                if g["by"] > 1
                else ""
            )
            mark = ("-" if key in opened else "+") if kids else " "
            rows.append(
                (
                    key,
                    bool(kids),
                    "  " * len(path)
                    + f"{mark} {n}{tag}{' (cycle)' if cyc else ''}  {extra or human(g['size'])}  {g['desc']}",
                )
            )
            if key in opened:
                for k in kids:
                    add(k, key)

        for r in data["roots"]:
            hay = " ".join(
                [r["name"], r["desc"]] + [o["name"] for o in r["owned"]] + r["shared"]
            )
            if not q or q in hay.lower():
                add(
                    r["name"],
                    (),
                    f"frees {human(r['excl'])}, {len(r['owned'])} owned"
                    + (" [AUR]" if r["foreign"] else ""),
                )
        return rows

    def run(s):
        curses.curs_set(0)
        cur = top = 0
        q = ""
        while True:
            rows = build(q)
            h, w = s.getmaxyx()
            cur = max(0, min(cur, len(rows) - 1))
            top = cur if cur < top else (cur - h + 3 if cur >= top + h - 2 else top)
            s.erase()
            for i, (_, _, text) in enumerate(rows[top : top + h - 2]):
                s.addnstr(i, 0, text, w - 1, curses.A_REVERSE if top + i == cur else 0)
            s.addnstr(
                h - 1,
                0,
                f"j/k move  l/enter open  h close  / search  esc clear  q quit | {len(rows)} rows  filter: {q}",
                w - 1,
            )
            ch = s.getch()
            key, kids = (rows[cur][0], rows[cur][1]) if rows else (None, False)
            if ch in (ord("q"), ord("Q")):
                return
            elif ch in (curses.KEY_DOWN, ord("j")):
                cur += 1
            elif ch in (curses.KEY_UP, ord("k")):
                cur -= 1
            elif ch == curses.KEY_NPAGE:
                cur += h - 2
            elif ch == curses.KEY_PPAGE:
                cur -= h - 2
            elif ch == 27:
                q = ""
            elif ch in (curses.KEY_RIGHT, ord("l")) and kids:
                opened.add(key)
            elif ch in (10, 13, 32, curses.KEY_ENTER) and kids:
                opened.symmetric_difference_update({key})
            elif ch in (curses.KEY_LEFT, ord("h")) and key:
                if key in opened:
                    opened.discard(key)
                elif len(key) > 1:
                    cur = next((i for i, x in enumerate(rows) if x[0] == key[:-1]), cur)
            elif ch == ord("/"):
                curses.echo()
                curses.curs_set(1)
                s.addnstr(h - 1, 0, " " * (w - 1), w - 1)
                s.addstr(h - 1, 0, "/")
                q = s.getstr(h - 1, 1, 60).decode(errors="replace").lower()
                curses.noecho()
                curses.curs_set(0)
                cur = top = 0

    curses.wrapper(run)


def main():
    ap = argparse.ArgumentParser(prog="pacroots", description=__doc__)
    ap.add_argument("--version", action="version", version=f"pacroots {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("tui")
    sub.add_parser("json")
    h = sub.add_parser("html")
    h.add_argument("-o", "--out", help="output file (default: a new temp file)")
    h.add_argument("--no-open", action="store_true", help="do not open the browser")
    a = ap.parse_args()
    data = analyze()
    if a.cmd == "tui":
        tui(data)
    elif a.cmd == "json":
        json.dump(data, sys.stdout, indent=1)
    else:
        page = _load_template().replace(
            "__DATA__", json.dumps(data).replace("</", "<\\/")
        )
        f = (
            open(a.out, "w", encoding="utf-8")
            if a.out
            else tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", prefix="pacroots-", suffix=".html", delete=False
            )
        )
        with f:
            f.write(page)
        print(f.name)

        if not a.no_open and not webbrowser.open(Path(f.name).resolve().as_uri()):
            print("Could not open a browser; open the file above manually.")


if __name__ == "__main__":
    main()
