#!/usr/bin/env python3

import numpy as np
import os
import sys
import subprocess
import argparse

'''
Small script for calculation of the spontaneous polarisation (PS) for an MD simulation in Gromacs,
using the total dipole moment of the simulation (via gmx dipoles) and the volume/density.

Program asks for a few inputs:
-s:    Gromacs .tpr file 
-e:    Just take the final value of dipole moment for the calculation (useful for checking <P1> is
       saturated in an electric field simulation)
-w:    window size; I can't remember why I added this.
-b:    give a frame number to begin at; useful for checking the average of <P1> over some duration,
       ignoring the effects of initial fluctuations (e.g., starting a simulation where <P1> is ~ 1 but without a field; checking that <P1> is stable etc.)

Dr. R. Mandle - University of Leeds, 2025

This will yield:

Ps.csv: Evolution of Ps over simulation time

and Print:
average value of Ps in units of C.M^2
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

def run_gmx_energy(tpr_file, b_value):
    """ run gmx energy to generate energy.xvg for volume and density. """
    try:
        with open("tmp.tmp", "w") as f:
            f.write("21 22\n")  # Selects Volume (21) and Density (22)

        cmd = ["gmx", "energy", "-s", tpr_file, "-b", str(b_value)]
        with open("energy.xvg", "w") as f:
            subprocess.run(cmd, stdin=open("tmp.tmp", "r"), stdout=f, stderr=subprocess.PIPE, check=True)

        os.remove("tmp.tmp")
        print("energy.xvg successfully generated.")

    except FileNotFoundError:
        print("Error: GROMACS (gmx) not found in PATH. Ensure it is installed.")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"Error running gmx energy: {e}")
        sys.exit(1)

def xvg2csv(xvg_file):
    """ Convert an .xvg file to a numpy array. """
    with open(xvg_file, 'r') as fid:
        lines = fid.readlines()

    data = []
    for line in lines:
        if not line.startswith(("#", "@")):
            data.append(list(map(float, line.split())))

    if not data:
        raise ValueError(f"No numerical data found in {xvg_file}.")
    
    return np.array(data)

def compute_Ps(window, final_value_only=False):
    """ Compute spontaneous polarization (Ps) and store time as a column. """
    TotDip_data = xvg2csv('Mtot.xvg')
    time = TotDip_data[:, 0]  # First column is time
    TotDip = TotDip_data[:, 4]  # Fifth column is total dipole

    energy_data = xvg2csv('energy.xvg')
    Vol = energy_data[:, 1]  # Second column is volume

    # Ensure window size does not exceed available data
    max_window = min(len(TotDip), len(Vol))
    window = min(window, max_window)

    TotDip = TotDip[-window:]
    time = time[-window:]  # Ensure time aligns with TotDip
    Vol = Vol[-window:]

    if final_value_only:
        time = np.array([time[-1]])  # Keep only last time point
        TotDip = np.array([TotDip[-1]])  # Keep only last dipole value
        Vol = np.mean(Vol)  # Use mean volume over window

    Ps = (TotDip * 3.335640952e-30) / (Vol * 1e-27)

    output_data = np.column_stack((time, Ps))  # Merge time and Ps columns
    np.savetxt("Ps.csv", output_data, delimiter=",", header="Time (ps), Ps", comments="")

    print("\nResults:")
    if final_value_only:
        print(f"Final Ps: {np.round(Ps[0], 3)} C.M^2 at {time[0]} ps")
    else:
        print(f"Ps is: {np.round(np.mean(Ps), 3)} +/- {np.round(np.std(Ps), 3)} C.M^2")

def main():
    parser = argparse.ArgumentParser(description="Compute spontaneous polarization (Ps) from GROMACS data.")
    parser.add_argument("-s", "--structure", required=True, help="Input GROMACS .tpr file")
    parser.add_argument("-b", "--begin", type=int, default=100000, help="Start time for gmx (default: 100000)")
    parser.add_argument("-w", "--window", type=int, default=300, help="Number of frames for averaging (default: 300)")
    parser.add_argument("-e", "--extract-final", action="store_true", help="Only use the final value")

    args = parser.parse_args()

    # Remove old files to prevent mismatches
    for f in ["dip.txt", "Mtot.xvg", "energy.xvg", "Mtot.csv", "energy.csv", "Ps.csv"]:
        if os.path.exists(f):
            os.remove(f)

    if not os.path.exists("dip.txt") or not os.path.exists("Mtot.xvg"):
        print("dip.txt or Mtot.xvg not found. Running gmx dipoles...")
        run_gmx_dipoles(args.structure, args.begin)

    if not os.path.exists("energy.xvg"):
        print("energy.xvg not found. Running gmx energy...")
        run_gmx_energy(args.structure, args.begin)

    compute_Ps(args.window, final_value_only=args.extract_final)

if __name__ == "__main__":
    main()