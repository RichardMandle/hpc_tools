#!/usr/bin/env python3

import argparse
import os
import sys
import subprocess
import numpy as np

'''
lcmd - script for analysing MD simulations of liquid crystals and
getting order parameters from geometry (p2, p4), dipole (p1), 
and spontaneous polarisation.

replaces the seperate op.py, p1.py, ps.py scripts.
'''


DEBYE_TO_C_M = 3.335640952e-30
NM3_TO_M3 = 1.0e-27


def run_with_input(cmd, input_text, stdout_file):
    try:
        with open(stdout_file, "w") as f:
            subprocess.run(
                cmd,
                input=input_text,
                text=True,
                stdout=f,
                stderr=subprocess.PIPE,
                check=True,
            )
    except FileNotFoundError:
        print("<< error >> gmx was not found in path")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"<< error >> command failed: {' '.join(cmd)}")
        print(e.stderr)
        sys.exit(1)


def run_gmx_dipoles(tpr_file, begin):
    cmd = ["gmx", "dipoles", "-s", tpr_file, "-b", str(begin)]
    run_with_input(cmd, "0\n", "dip.txt")
    print("generated dip.txt and Mtot.xvg")


def run_gmx_energy(tpr_file, begin, energy_select):
    cmd = ["gmx", "energy", "-s", tpr_file, "-b", str(begin)]
    run_with_input(cmd, f"{energy_select}\n", "energy.xvg")
    print("generated energy.xvg")


def remove_files(files):
    for fname in files:
        if os.path.exists(fname):
            os.remove(fname)


def xvg_to_array(xvg_file):
    data = []

    with open(xvg_file, "r") as f:
        for line in f:
            line = line.strip()

            if not line:
                continue

            if line.startswith(("#", "@", "&")):
                continue

            data.append([float(x) for x in line.split()])

    if not data:
        raise ValueError(f"<< warning >> no numerical data found in {xvg_file}!")

    return np.asarray(data, dtype=float)


def parse_dip_data(fname="dip.txt"):
    with open(fname, "r") as f:
        lines = f.readlines()

    try:
        nmols = int(lines[3].split()[2])
        dipole = float(lines[8].split()[2])
    except Exception:
        raise ValueError("<< error >> could not parse dip.txt. check the gmx dipoles output format.")

    return nmols, dipole


def save_csv(fname, time, values, label):
    data = np.column_stack((time, values))
    np.savetxt(fname, data, delimiter=",", header=f"Time (ps), {label}", comments="")


def output_name(args, stem):
    if args.prefix:
        return f"{args.prefix}_{stem}.csv"
    return f"{stem}.csv"


def compute_p1_dipole(args):
    data = xvg_to_array("Mtot.xvg")

    time = data[:, 0]
    total_dipole = data[:, 4]

    nmols, mol_dipole = parse_dip_data()
    p1 = total_dipole / (nmols * mol_dipole)

    if args.extract_final:
        time = np.asarray([time[-1]])
        p1 = np.asarray([p1[-1]])

    fname = output_name(args, "p1_dipole_basis")
    save_csv(fname, time, p1, "P1")

    print("\nresults: p1, dipole basis")
    if args.extract_final:
        print(f"final <P1>: {p1[0]:.3f} at {time[0]:.1f} ps")
    else:
        print(f"<P1>: {np.mean(p1):.3f} +/- {np.std(p1):.3f}")
    print(f"saved {fname}")


def compute_ps(args):
    dip_data = xvg_to_array("Mtot.xvg")
    energy_data = xvg_to_array("energy.xvg")

    time = dip_data[:, 0]
    total_dipole = dip_data[:, 4]
    volume = energy_data[:, 1]

    n = min(len(time), len(total_dipole), len(volume))
    window = min(args.window, n)

    time = time[-window:]
    total_dipole = total_dipole[-window:]
    volume = volume[-window:]

    if args.extract_final:
        time = np.asarray([time[-1]])
        total_dipole = np.asarray([total_dipole[-1]])
        volume = np.asarray([np.mean(volume)])

    ps = (total_dipole * DEBYE_TO_C_M) / (volume * NM3_TO_M3)

    fname = output_name(args, "ps_dipole_volume")
    save_csv(fname, time, ps, "Ps")

    print("\nresults: ps")
    if args.extract_final:
        print(f"final Ps: {ps[0]:.3f} C m^-2 at {time[0]:.1f} ps")
    else:
        print(f"Ps: {np.mean(ps):.3f} +/- {np.std(ps):.3f} C m^-2")
    print(f"saved {fname}")


def normalise_vectors(vectors):
    norms = np.linalg.norm(vectors, axis=-1)

    if np.any(norms == 0):
        raise ValueError("<< warning >> zero-length director found!")

    return vectors / norms[..., np.newaxis]


def q_tensor_from_vectors(vectors):
    n = vectors.shape[0]
    q = 1.5 * np.einsum("ni,nj->ij", vectors, vectors) / n
    q -= 0.5 * np.eye(3)
    return q


def p2_p4_for_frame(vectors):
    q = q_tensor_from_vectors(vectors)

    eigvals, eigvecs = np.linalg.eigh(q)
    director = eigvecs[:, np.argmax(eigvals)]

    cos_theta = vectors @ director
    cos2 = cos_theta ** 2
    cos4 = cos2 ** 2

    p2 = np.mean(0.5 * (3.0 * cos2 - 1.0))
    p4 = np.mean((35.0 * cos4 - 30.0 * cos2 + 3.0) / 8.0)

    return p2, p4


def molecule_indices_from_residues(traj, atoms_per_mol=None):
    if atoms_per_mol is None:
        atoms_per_mol = int(traj.n_atoms / traj.n_residues)

    if traj.n_atoms % atoms_per_mol != 0:
        raise ValueError("<< error >> atom count is not divisible by atoms per molecule")

    return [
        list(range(start, start + atoms_per_mol))
        for start in range(0, traj.n_atoms, atoms_per_mol)
    ]


def compute_director_order(args):
    try:
        import mdtraj as md
    except ImportError:
        print("<< error >> mdtraj is required for -p2 and -p4")
        sys.exit(1)

    print("loading trajectory")
    traj = md.load(args.traj, top=args.top, stride=args.stride)

    indices = molecule_indices_from_residues(traj, args.atoms_per_mol)

    print("computing molecular directors")
    directors = md.compute_directors(traj, indices)
    directors = normalise_vectors(directors)

    p2 = np.empty(traj.n_frames)
    p4 = np.empty(traj.n_frames)

    print("computing order parameters")
    for i in range(traj.n_frames):
        p2[i], p4[i] = p2_p4_for_frame(directors[i])

    time = traj.time

    if args.p2:
        fname = output_name(args, "p2_director_basis")
        save_csv(fname, time, p2, "P2")
        print(f"saved {fname}")
        print(f"<P2>: {np.mean(p2):.3f} +/- {np.std(p2):.3f}")

    if args.p4:
        fname = output_name(args, "p4_director_basis")
        save_csv(fname, time, p4, "P4")
        print(f"saved {fname}")
        print(f"<P4>: {np.mean(p4):.3f} +/- {np.std(p4):.3f}")


def need_dipoles(args):
    return args.p1 or args.ps


def need_trajectory(args):
    return args.p2 or args.p4


def check_args(args):
    if need_dipoles(args) and args.structure is None:
        raise SystemExit("<< error >> -s/--structure is required for -p1 or -ps")

    if need_trajectory(args) and (args.traj is None or args.top is None):
        raise SystemExit("<< error >> -traj and -top are required for -p2 or -p4")

    if not (args.p1 or args.ps or args.p2 or args.p4):
        raise SystemExit("<< error >> choose at least one of -p1, -ps, -p2, -p4")


def main():
    parser = argparse.ArgumentParser(
        description="calculate simple liquid crystal md observables"
    )

    parser.add_argument("-p1", action="store_true", help="calculate dipole-basis P1")
    parser.add_argument("-ps", action="store_true", help="calculate spontaneous polarisation")
    parser.add_argument("-p2", action="store_true", help="calculate director-basis P2")
    parser.add_argument("-p4", action="store_true", help="calculate director-basis P4")

    parser.add_argument("-s", "--structure", help="gromacs .tpr file")
    parser.add_argument("-traj", help="trajectory file")
    parser.add_argument("-top", help="topology file for mdtraj")

    parser.add_argument("-b", "--begin", type=int, default=100000, help="start time / ps")
    parser.add_argument("-w", "--window", type=int, default=300, help="averaging window")
    parser.add_argument("-e", "--extract-final", action="store_true", help="use final value only")

    parser.add_argument("--energy-select", default="21 22", help="gmx energy selection")
    parser.add_argument("--atoms-per-mol", type=int, default=None, help="atoms per molecule")
    parser.add_argument("--stride", type=int, default=1, help="trajectory stride")
    parser.add_argument("--reuse", action="store_true", help="reuse existing xvg files")
    parser.add_argument("--prefix", default=None, help="prefix for csv files")

    args = parser.parse_args()
    check_args(args)

    if need_dipoles(args):
        if not args.reuse:
            remove_files(["dip.txt", "Mtot.xvg"])

        if not os.path.exists("dip.txt") or not os.path.exists("Mtot.xvg"):
            run_gmx_dipoles(args.structure, args.begin)

    if args.ps:
        if not args.reuse:
            remove_files(["energy.xvg"])

        if not os.path.exists("energy.xvg"):
            run_gmx_energy(args.structure, args.begin, args.energy_select)

    if args.p1:
        compute_p1_dipole(args)

    if args.ps:
        compute_ps(args)

    if need_trajectory(args):
        compute_director_order(args)


if __name__ == "__main__":
    main()
