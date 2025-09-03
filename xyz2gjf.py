
#!/usr/bin/env python3
import os
import glob
import argparse
import textwrap
from pathlib import Path

"""
xyz2gjf
Convert XYZ files to Gaussian .gjf inputs.

Examples:
  python xyz2gjf.py -i myfile.xyz -o myfile.gjf
  python xyz2gjf.py -i myfile.xyz -o myfile.gjf -cpu 4 -mem 8GB
  python xyz2gjf.py -i ./inputs -all -m "B3LYP/def2-SVP opt freq" -cpu 2 -mem 8GB
  python xyz2gjf.py -i mol.xyz -o mol.gjf -b "EmpiricalDispersion=GD3BJ, SCF=Tight"
"""

def parse_args():
    parser = argparse.ArgumentParser(
        description="Convert .xyz files to Gaussian .gjf format.",
        epilog=textwrap.dedent("""\
            Examples:
              python xyz2gjf.py -i myfile.xyz -o myfile.gjf
              python xyz2gjf.py -i myfile.xyz -o myfile.gjf -cpu 4 -mem 8GB
              python xyz2gjf.py -i ./inputs -all -m "B3LYP/def2-SVP opt" -cpu 2 -mem 8GB
              python xyz2gjf.py -i mol.xyz -o mol.gjf -b "EmpiricalDispersion=GD3BJ, SCF=Tight"
        """),
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument("-i", "--input", help="Input .xyz file or directory.")
    parser.add_argument("-n", "--name", help="Job name / title (defaults to output or xyz stem).")
    parser.add_argument("-o", "--output", help="Output .gjf file (ignored if -all is used).")
    parser.add_argument("-m", "--method", default="B3LYP/def2-SVP", help='Gaussian route section method/basis and options, e.g. "B3LYP/def2-SVP opt freq".')
    parser.add_argument("-c", "--charge_mult", default="0 1", help='Charge and multiplicity, e.g., "0 1" (default).')
    parser.add_argument("-cpu", type=int, default=4, metavar="N", help="Number of CPU cores for %%nprocshared (default 4).")
    parser.add_argument("-mem", type=str, default="4GB", help="Memory for %%mem (e.g., 4GB). Use GB (recommended) or MB (Gaussian accepts both).")
    parser.add_argument("-all", action="store_true", help="Process all .xyz files in a directory (use -i DIR).")

    args = parser.parse_args()

    if not args.all and (not args.input or not args.output):
        parser.error("Either use -all to process all .xyz files in a folder, or provide both -i and -o.")
        
    # validate the memory part; we want GB or MB, not W or MW
    m = args.mem.strip().lower()
    if not (m.endswith("gb") or m.endswith("mb")):
        parser.error('Memory must end with "GB" or "MB", e.g., -mem 8GB or -mem 8000MB')
    return args

def read_xyz_xyzblock(xyz_path: Path):
    """
    Return list of (sym, x, y, z) as strings; ignores the first two header lines.
    """
    lines = xyz_path.read_text().splitlines()
    if len(lines) < 3:
        raise ValueError(f"I don't think {xyz_path} looks like a valid XYZ file.")
    coords = []
    for line in lines[2:]:
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) < 4:
            continue
        sym = parts[0]
        x, y, z = parts[1:4]
        coords.append((sym, x, y, z))
    if not coords:
        raise ValueError(f"No coordinates parsed from {xyz_path}.")
    return coords

def safe_title(s: str) -> str:
    # Gaussian title can be any text; still trim long/odd whitespace
    s = s.strip()
    return s if s else "Gaussian Job"

def make_route(method: str, extra_block: str | None) -> str:
    route = f"#p {method.strip()}"
    if extra_block:
        extras = " ".join([tok.strip() for tok in extra_block.split(",") if tok.strip()])
        if extras:
            route = f"{route} {extras}"
    return route

def xyz_to_gjf(args):
    xyz_file = Path(args.input)
    gjf_file = Path(args.output)
    if gjf_file.suffix.lower() != ".gjf":
        gjf_file = gjf_file.with_suffix(".gjf") # better fix that
    job_title = args.name or gjf_file.stem or xyz_file.stem

    method = args.method.strip()
    nproc = int(args.cpu)
    mem_value = args.mem.strip()
    charge_mult = args.charge_mult.strip()

    coords = read_xyz_xyzblock(xyz_file)

    route_line = make_route(method, None)

    # write the actual .gjf
    chk_name = f"{gjf_file.stem}.chk"
    with open(gjf_file, "w") as f:
        f.write(f"%mem={mem_value}\n")
        f.write(f"%nprocshared={nproc}\n")
        f.write(f"%chk={chk_name}\n")
        f.write(f"{route_line}\n\n")
        f.write(f"{safe_title(job_title)}\n\n")
        f.write(f"{charge_mult}\n")
        for sym, x, y, z in coords:
            f.write(f"{sym:2s}  {x:>16s}  {y:>16s}  {z:>16s}\n")
        f.write("\n")

    print(f"Converted: {xyz_file.name} -> {gjf_file.name}")

def process_all_xyz(args):
    """
    Convert all .xyz files in the specified directory to .gjf next to the inputs.
    """
    directory = Path(args.input or os.getcwd())
    count = 0
    for file in sorted(directory.glob("*.xyz")):
        out_gjf = file.with_suffix(".gjf")
        class A: pass
        a = A()
        a.input = str(file)
        a.output = str(out_gjf)
        a.name = args.name or file.stem
        a.method = args.method
        a.cpu = args.cpu
        a.mem = args.mem
        a.charge_mult = args.charge_mult
        a.block = args.block
        xyz_to_gjf(a)
        count += 1
    if count == 0:
        print(f"No .xyz files found in {directory}")

def main():
    args = parse_args()
    if args.all:
        process_all_xyz(args)
    else:
        xyz_to_gjf(args)

if __name__ == "__main__":
    main()
