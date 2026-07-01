#!/usr/bin/env python3

from pathlib import Path
import numpy as np
import argparse

'''
xyz2orca_scan.py

Aims to:
reads a molecule geometry in .xyz format; using the user supplied atom IDs (--atoms) it finds the angle between them and 
creates an appropriate orca input file (-o) to execute a relaxed scan about the given torsion.

Why? 
Orca torsion/dihedral scans require the initial dihedral angle to be supplied; this just retrieves it from the xyz file
so that the calculation won't go wrong.

Use:
python xyz2orca_scan.py my_input.xyz --atoms 1 2 3 4 -o my_input.inp

Options:
--nsteps - number of scan steps; default=72
--scan-degrees - number of degrees to scan over; default=360.0
'''

def read_xyz_coords(xyz_file):
    lines = Path(xyz_file).read_text().splitlines()
    atom_lines = lines[2:]
    coords = []

    for line in atom_lines:
        parts = line.split()
        if len(parts) < 4:
            continue
        coords.append([float(parts[1]), float(parts[2]), float(parts[3])])

    return np.array(coords, dtype=float)

def dihedral_deg(p0, p1, p2, p3):

    b0 = p0 - p1
    b1 = p2 - p1
    b2 = p3 - p2

    b1 /= np.linalg.norm(b1)

    v = b0 - np.dot(b0, b1) * b1
    w = b2 - np.dot(b2, b1) * b1

    x = np.dot(v, w)
    y = np.dot(np.cross(b1, v), w)

    return np.degrees(np.arctan2(y, x))

def normalise_0_360(angle):
    return angle % 360.0

def make_orca_scan_input(
    xyz_file,
    out_file,
    atoms,
    nsteps=72,
    scan_degrees=360.0,
    method_line="! opt gfn2-xtb",
    nprocs=1,
    maxcore=4000,
    charge=0,
    multiplicity=1,
):
    coords = read_xyz_coords(xyz_file)

    i, j, k, l = atoms
    phi = dihedral_deg(coords[i], coords[j], coords[k], coords[l])
    start = normalise_0_360(phi)
    end = start + scan_degrees

    stem = Path(xyz_file).stem

    text = f"""{method_line}
%pal nprocs {nprocs} end
%maxcore {maxcore}
%geom scan
    D {i} {j} {k} {l} = {start:.6f}, {end:.6f}, {nsteps}
end
    AddExtraBonds false
end
#{stem}
* xyzfile {charge} {multiplicity} {xyz_file}
"""

    Path(out_file).write_text(text)
    print(f"Wrote {out_file}")
    print(f"Initial dihedral D {i} {j} {k} {l} = {phi:.6f} degrees")
    print(f"ORCA scan: {start:.6f} -> {end:.6f} in {nsteps} steps")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("xyz_file")
    parser.add_argument("-o", "--out", default=None)
    parser.add_argument("--atoms", nargs=4, type=int, required=True,
                        help="ORCA-style atom indices, i.e. zero-based")
    parser.add_argument("--nsteps", type=int, default=72)
    parser.add_argument("--scan-degrees", type=float, default=360.0)
    # TO DO 
    # implement some option to turn on/off bond breaking/making 
    args = parser.parse_args()

    xyz_path = Path(args.xyz_file)
    out_file = args.out or xyz_path.with_suffix(".inp")

    make_orca_scan_input(
        xyz_file=str(xyz_path),
        out_file=str(out_file),
        atoms=args.atoms,
        nsteps=args.nsteps,
        scan_degrees=args.scan_degrees,
    )
