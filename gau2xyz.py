import re
import glob
import argparse
from pathlib import Path
from typing import List, Tuple

EXTS_GJF = {".gjf", ".com", ".g03", ".g09", ".g16"}

def parse_args():
    p = argparse.ArgumentParser(
        description="Convert Gaussian .gjf/.com (Cartesian) files to .xyz",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    p.add_argument("-i", "--input", required=True,
                   help="Input .gjf file or directory")
    p.add_argument("-o", "--output",
                   help="Output .xyz file (ignored if input is a directory)")
    p.add_argument("-a", "--all", action="store_true",
                   help="Treat -i as a directory and convert all .gjf/.com files inside")
    p.add_argument("--overwrite", action="store_true",
                   help="Overwrite existing .xyz files")
    return p.parse_args()

def is_route_line(s: str) -> bool:
    return s.lstrip().startswith("#")

def is_blank(s: str) -> bool:
    return len(s.strip()) == 0

def looks_like_cart_line(s: str) -> bool:
    """
    we are looking for an element name and then a bunch of cart. coords;
    element might be an integer though (e.g. C, or 6; below!)
    Accepts: C 0.0 0.1 0.2   or   6 0.0 0.1 0.2
    """
    t = s.split()
    if len(t) < 4:
        return False
    try:
        float(t[-1]); float(t[-2]); float(t[-3])
    except ValueError:
        return False
    return True

def read_gjf_cartesian(gjf_path: Path) -> Tuple[str, List[Tuple[str, float, float, float]]]:
    """
    Returns (title, [(elem, x, y, z), ...])
    Raises ValueError on parse problems.
    """
    with gjf_path.open("r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
        
    i = 0
    n = len(lines)

    while i < n and lines[i].lstrip().startswith("%"):
        i += 1

    if i >= n or not is_route_line(lines[i]):
        raise ValueError("No route section (# ...) found.")
    while i < n and (is_route_line(lines[i]) or is_blank(lines[i])):
        i += 1

    if i >= n:
        raise ValueError("Missing title line.")
    title = lines[i].rstrip("\n")
    i += 1

    # Blank line
    while i < n and not is_blank(lines[i]):
        i += 1
    if i >= n:
        raise ValueError("Missing blank line after title.")

    while i < n and is_blank(lines[i]):
        i += 1

    if i >= n:
        raise ValueError("Missing charge/multiplicity line.")
    chmult_line = lines[i].strip()
    i += 1
    chmult_ok = bool(re.match(r"^\s*-?\d+\s+\d+\s*$", chmult_line))
    if not chmult_ok:
        while i < n and is_blank(lines[i]):
            i += 1
        if i >= n:
            raise ValueError("Could not find charge/multiplicity line.")
        chmult_line2 = lines[i].strip()
        i += 1
        if not re.match(r"^\s*-?\d+\s+\d+\s*$", chmult_line2):
            raise ValueError("Charge/multiplicity line malformed.")

    atoms = []
    while i < n:
        s = lines[i]
        if is_blank(s):
            break
        if not looks_like_cart_line(s):
            break

        t = s.split()
        elem = t[0]

        try:
            x = float(t[-3]); y = float(t[-2]); z = float(t[-1])
        except ValueError:
            break
        atoms.append((elem, x, y, z))
        i += 1

    if not atoms:
        raise ValueError("No Cartesian coordinates found (Z-matrix?); this tool expects Cartesian .gjf.")

    return title if title.strip() else gjf_path.stem, atoms

def write_xyz(xyz_path: Path, title: str, atoms: List[Tuple[str,float,float,float]], overwrite=False):
    if xyz_path.exists() and not overwrite:
        raise FileExistsError(f"{xyz_path} exists. Use --overwrite to replace.")
    with xyz_path.open("w", encoding="utf-8") as f:
        f.write(f"{len(atoms)}\n")
        f.write(f"{title}\n")
        for elem, x, y, z in atoms:
            f.write(f"{elem:<3s} {x: .10f} {y: .10f} {z: .10f}\n")

def convert_one(gjf_file: Path, out_xyz: Path=None, overwrite=False):
    title, atoms = read_gjf_cartesian(gjf_file)
    xyz_path = out_xyz or gjf_file.with_suffix(".xyz")
    write_xyz(xyz_path, title, atoms, overwrite=overwrite)
    print(f"Converted {gjf_file.name}  ->  {xyz_path.name}  (N={len(atoms)})")

def convert_all_in_dir(directory: Path, overwrite=False):
    files = [p for p in directory.iterdir() if p.suffix.lower() in EXTS_GJF]
    if not files:
        print("No Gaussian files found in directory.")
        return
    for p in sorted(files):
        try:
            convert_one(p, overwrite=overwrite)
        except Exception as e:
            print(f"[WARN] Skipped {p.name}: {e}")

def main():
    args = parse_args()
    in_path = Path(args.input)
    if args.all:
        if not in_path.is_dir():
            raise SystemExit("With -a/--all, -i must be a directory.")
        convert_all_in_dir(in_path, overwrite=args.overwrite)
    else:
        if not in_path.exists():
            raise SystemExit(f"Input not found: {in_path}")
        if in_path.is_dir():
            raise SystemExit("Input is a directory. Use -a/--all to batch convert.")
        if args.output:
            out = Path(args.output)
            if out.suffix.lower() != ".xyz":
                out = out.with_suffix(".xyz")
        else:
            out = None
        convert_one(in_path, out_xyz=out, overwrite=args.overwrite)

if __name__ == "__main__":
    main()
