#!/usr/bin/env python3

import argparse
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt

'''
Simply plots the *.relaxedscan.dat data from orca scan calculations. Made for quick looks rather than rigorous scientific visualisation.

Can handle multiple inputs on the same axes etc.
'''

HARTREE_TO_KJMOL = 2625.499638


def wrap_angle_deg(x):
    return ((x + 180.0) % 360.0) - 180.0


def load_scan(filename, wrap=True):
    data = np.loadtxt(filename)

    if data.ndim == 1:
        data = data.reshape(1, -1)

    x = data[:, 0]
    e = data[:, 1]

    e_rel = (e - np.min(e)) * HARTREE_TO_KJMOL

    if wrap:
        x = wrap_angle_deg(x)
        order = np.argsort(x)
        x = x[order]
        e_rel = e_rel[order]

    return x, e_rel


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input", nargs="+", required=True)
    parser.add_argument("-o", "--output", default=None)
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument("--no-wrap", action="store_true")

    args = parser.parse_args()

    fig, ax = plt.subplots(figsize=(6, 4))

    for filename in args.input:
        x, e_rel = load_scan(filename, wrap=not args.no_wrap)
        label = Path(filename).stem
        ax.plot(x, e_rel, marker="o", linewidth=1.5, markersize=4, label=label)

    ax.set_xlabel("Dihedral angle / degrees")
    ax.set_ylabel("Relative energy / kJ mol$^{-1}$")

    if not args.no_wrap:
        ax.set_xlim(-180, 180)

    if len(args.input) > 1:
        ax.legend(frameon=False)

    fig.tight_layout()

    if args.output is None:
        if len(args.input) == 1:
            output = Path(args.input[0]).with_suffix(".png")
        else:
            output = Path("orca_scan.png")
    else:
        output = Path(args.output)

    fig.savefig(output, dpi=args.dpi)
    print(f"Saved {output}")


if __name__ == "__main__":
    main()
