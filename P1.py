#!/usr/bin/env python3

import numpy as np
import os
import sys
import subprocess
import argparse

'''
Small script for calculation of the polar order parameter (P1) for an MD simulation in Gromacs,
using the total dipole moment of the simulation (via gmx dipoles).

Program asks for:
-s:    Gromacs .tpr file 
-e:    Just take the final value of dipole moment for the calculation
-b:    Give a frame number to begin at

Dr. R. Mandle - University of Leeds, 2025
'''

def run_gmx_dipoles(tpr_file, b_value):
    """ run gmx dipoles to generate dip.txt and Mtot.xvg. """
    try:
        with open("tmp.tmp", "w") as f:
            f.write("0\n")  # Selects group 0 (total dipole)

        cmd = ["gmx", "dipoles", "-s", tpr_file, "-b", str(b_value)]
        with open("dip.txt", "w") as f:
            subprocess.run(cmd, stdin=open("tmp.tmp", "r"), stdout=f, stderr=subprocess.PIPE, check=True)

        os.remove("tmp.tmp")
        print("dip.txt and Mtot.xvg successfully generated.")

    except FileNotFoundError:
        print("Error: GROMACS (gmx) not found in PATH. Ensure it is installed.")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"Error running gmx dipoles: {e}")
        sys.exit(1)

def xvg2csv(xvg_file):
    """ turn an .xvg file to .csv. """
    delimiter = ','

    with open(xvg_file, 'r') as fid:
        lines = fid.readlines()

    data = []
    for line in lines:
        if not line.startswith(("#", "@")):
            data.append(list(map(float, line.split())))

    if not data:
        raise ValueError(f"No numerical data found in {xvg_file}.")

    return np.array(data)  # Return numpy array

def compute_P1(final_value_only=False):
    """ Computes and prints the polar order parameter <P1>. """
    data = xvg2csv('Mtot.xvg')
    time = data[:, 0]  # First column is time
    TotDip = data[:, 4]  # 5th column is total dipole

    NMols, Dipole = parse_dip_data()

    P1 = TotDip / (NMols * Dipole)

    if final_value_only:
        time = np.array([time[-1]])  # Keep only last time point
        P1 = np.array([P1[-1]])  # Keep only last P1 value

    output_data = np.column_stack((time, P1))  # Merge time and P1 columns

    np.savetxt("P1.csv", output_data, delimiter=",", header="Time (ps), P1", comments="")

    print("\nResults:")
    if final_value_only:
        print(f"Final <P1>: {np.round(P1[0], 3)} at {time[0]} ps")
    else:
        print("<P1> is: " + 
              str(np.round(np.mean(P1), 3)) +
              ' +/- ' +
              str(np.round(np.std(P1), 3)))

def parse_dip_data(fname='dip.txt'):
    """ Retrieves dipole data from dip.txt. """
    with open(fname, 'r') as fid:
        ll = fid.readlines()

    NMols = int(ll[3].split()[2])
    Dipole = float(ll[8].split()[2])    
    return NMols, Dipole

def main():
    parser = argparse.ArgumentParser(description="Compute polar order parameter (P1) from GROMACS dipole analysis.")
    parser.add_argument("-s", "--structure", required=True, help="Input GROMACS .tpr file")
    parser.add_argument("-b", "--begin", type=int, default=100000, help="Start time for gmx dipoles (default: 100000)")
    parser.add_argument("-e", "--extract-final", action="store_true", help="Only use the final value of Mtot.xvg")

    args = parser.parse_args()

    # Remove old files to prevent mismatches
    for f in ["dip.txt", "Mtot.xvg", "P1.csv"]:
        if os.path.exists(f):
            os.remove(f)

    if not os.path.exists("dip.txt") or not os.path.exists("Mtot.xvg"):
        print("dip.txt or Mtot.xvg not found. Running gmx dipoles...")
        run_gmx_dipoles(args.structure, args.begin)

    compute_P1(final_value_only=args.extract_final)

if __name__ == "__main__":
    main()
