# pacroots

See what you actually installed on an Arch-based system, and what each thing drags in with it.

On Arch (and CachyOS) every app and library is a package, so a thousand-package system is hard to reason about. pacroots separates **roots** (the packages you explicitly installed) from the **dependencies** that exist only because of them, and shows each root as an expandable dependency tree.

## Features

- **Roots first:** explicit packages, sorted by how much disk they really cost you (their own size plus the dependencies only they need).
- **Real recursive tree:** every package expands into its dependencies, and those into theirs.
- **Exclusive vs shared:** see what removing a root would free, and which libraries are shared with other roots (`shared xN`).
- **Orphans:** dependencies that nothing needs any more.
- **AUR/foreign marker** for packages not in the sync repos.
- **Two front ends:** a terminal browser (works over SSH) and a self-contained HTML page with search.
- **Read-only:** it never modifies your system.

## Requirements

- Python 3.7+ (standard library only)
- An Arch-based system with a pacman database at `/var/lib/pacman/local`

No pip, no virtualenv, no extra packages. It does not use `pyalpm`, so a Python or pacman upgrade cannot break it.

## Usage

```bash
python main.py tui                    # terminal tree browser
python main.py html                   # write a temp HTML file and open it in the browser
python main.py html --no-open         # write it and just print the path (handy over SSH)
python main.py html -o tree.html      # keep a copy somewhere specific
python main.py json > roots.json      # raw data for scripts
```

Run it from the project directory, since the HTML front end uses `template.html`.

### Terminal keys

| Key | Action |
|---|---|
| `j` / `k`, arrows | move |
| `l`, `→`, `Enter` | open |
| `h`, `←` | close, or jump to parent |
| `/` | search (name, description, or anything in the subtree) |
| `Esc` | clear filter |
| `q` | quit |

## Reading the output

- **frees N**: disk space released if you remove that root with `pacman -Rns` (its size plus exclusively owned dependencies).
- **owned**: dependencies only that root needs.
- **shared xN**: needed by N different roots, so it stays if you remove one of them.
- **explicit**: a nested package that is itself one of your roots.
- **↻**: a dependency cycle; the tree stops there instead of looping.

## How it works

1. Reads `/var/lib/pacman/local/*/desc` directly: names, sizes, install reason, dependencies, provides.
2. Resolves each dependency to an installed package, including virtual ones through `provides`.
3. Computes, for every package, how many roots reach it. Exactly one means that root owns it.

## Limitations

- Version constraints and optional dependencies are ignored; this is for browsing, not for resolving installs.
- If a dependency is provided by several installed packages, the first match is used.
- If one root depends on another, the second root's dependencies count as shared. That errs on the safe side: it never claims you'd free more than you would.
- The data is a snapshot taken when you run it, not a live view.

## Project layout

```
main.py         analysis, terminal UI, CLI
template.html   page template for the HTML front end (with its CSS)
```

## Testing without a real system

Point it at a fake database with an environment variable:

```bash
PACROOTS_DB=/path/to/fake/local python main.py json
```