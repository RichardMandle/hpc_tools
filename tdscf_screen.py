import argparse
import re
import itertools
import os
import sys
import glob
from rdkit import Chem  # use the GetPeriodicTable function to convert atomic numbers to symbols

def extract_final_geometry(log_file):
    """
    get the final geometry from a Gaussian .log file by locating the last
    "Standard orientation" block. Taken from bimolpes.py

    Returns:
        A list of tuples: (element, x, y, z)
    """
    with open(log_file, 'r') as f:
        content = f.read()

    start_matches = [m.start() for m in re.finditer(r"Standard orientation:", content)]
    finish_matches = [m.start() for m in re.finditer(r"Rotational constants", content)]
    
    if not start_matches or not finish_matches:
        raise ValueError("No complete geometry block found in the log file.")

    geom_block = content[start_matches[-1]:finish_matches[-1]]
    lines = geom_block.splitlines()
    
    dash_lines = [i for i, line in enumerate(lines) if re.match(r'-+', line.strip())]
    if len(dash_lines) < 2:
        raise ValueError("Unexpected geometry block format.")
    start_idx = dash_lines[1] + 1  # Geometry data starts after the second dashed line.
    end_idx = None
    for i in range(start_idx, len(lines)):
        if re.match(r'-+', lines[i].strip()):
            end_idx = i
            break
    if end_idx is None:
        end_idx = len(lines)
    
    geometry = []
    for line in lines[start_idx:end_idx]:
        parts = line.split()
        if len(parts) < 6:
            continue  # Skip malformed lines.
        
        # Expected format: Center, Atomic number, Atomic type, x, y, z.
        element = Chem.GetPeriodicTable().GetElementSymbol(int(parts[1]))
        x, y, z = parts[3], parts[4], parts[5]
        geometry.append((element, x, y, z))
    return geometry

def generate_gjf_files(args):
    """
    get the final geometry from the log file (args.input) and writes .gjf files for every
    combination of functional, basis set, and (optionally) empirical dispersion and solvation.
    
    each .gjf file contains two chained jobs:
      1. An OPT (geometry optimization) job.
      2. A TD-SCF job for UV–vis spectra using the checkpoint from the OPT job.
    
    files are named sequentially (e.g. outputBase_1.gjf, outputBase_2.gjf, ...).
    
    Returns:
        A list of generated .gjf filenames.
    """
    geometry = extract_final_geometry(args.input)
    
    ed_options = [False, True] if args.ed else [False]
    sol_options = ([None] + args.solvation_model) if args.sol else [None]
    
    # Determine the base name for output files.
    base = args.output  # already set via -o or defaulted in main()
    
    # If requested, remove existing .gjf files matching the output pattern.
    if args.remove_existing:
        pattern = base + "_*.gjf"
        existing_files = glob.glob(pattern)
        for file in existing_files:
            os.remove(file)
            print(f"Removed existing file: {file}")
    
    generated_files = []
    file_counter = 1  # Sequential numbering

    for func, basis, ed_flag, sol_model in itertools.product(args.functionals, args.basis, ed_options, sol_options):
        # Build the OPT job route line.
        route_opt = f"# {func}/{basis} opt"
        if ed_flag:
            route_opt += " EmpiricalDispersion=gd3bj"
        if sol_model is not None:
            route_opt += f" {sol_model}"
        
        # Build the TD-SCF job route line.
        route_td = f"# TD(NStates={args.ns}) {func}/{basis}"
        if ed_flag:
            route_td += " EmpiricalDispersion=gd3bj"
        if sol_model is not None:
            route_td += f" {sol_model}"
        route_td += " geom=check guess=read"
        
        gjf_filename = f"{base}_{file_counter}.gjf"
        chk_filename = gjf_filename.replace(".gjf", ".chk")
        file_counter += 1
        
        with open(gjf_filename, 'w') as gjf_file:
            # Write the OPT job section.
            gjf_file.write(f"%chk={chk_filename}\n")
            gjf_file.write(f"%mem={args.mem}\n")
            gjf_file.write(f"%nprocshared={args.cpu}\n")
            gjf_file.write(f"{route_opt}\n\n")
            gjf_file.write(f"Title Card: OPT job generated from {args.input}\n\n")
            gjf_file.write("0 1\n")
            for atom in geometry:
                element, x, y, z = atom
                gjf_file.write(f"{element}    {x}    {y}    {z}\n")
            gjf_file.write("\n")
            
            # Write the chained TD-SCF job section.
            gjf_file.write("--Link1--\n")
            gjf_file.write(f"%OldChk={chk_filename}\n")
            gjf_file.write(f"%Chk={chk_filename}\n")
            gjf_file.write(f"{route_td}\n\n")
            gjf_file.write(f"Title Card: TD-SCF job based on OPT geometry from {args.input}\n\n")
            gjf_file.write("0 1\n")
        
        print(f"Generated {gjf_filename}")
        generated_files.append(gjf_filename)
    return generated_files

def main():
    parser = argparse.ArgumentParser(
        description="Generate Gaussian .gjf input files (with chained OPT and TD-SCF jobs) "
                    "from a .log file and create a SLURM job array submission script."
    )
    # Gaussian input generation options.
    parser.add_argument('-i', '--input', required=True, type=str, help="Input Gaussian log file (.log)")
    parser.add_argument('-cpu', type=int, default=4, help="Number of CPU cores (default: 4)")
    parser.add_argument('-mem', type=str, default="4GB", help="Memory (default: 4GB)")
    parser.add_argument('-f', '--functionals', type=str, nargs='+', default=["b3lyp", "pbe"],
                        help="List of DFT functionals (default: b3lyp pbe)")
    parser.add_argument('-b', '--basis', type=str, nargs='+', default=["6-31g(d)", "cc-pvdz", "aug-cc-pvdz", "cc-pvtz"],
                        help="List of basis sets (default: 6-31g(d) cc-pvtz)")
    parser.add_argument('-ed', action='store_true', help="Toggle empirical dispersion (gd3bj) on/off")
    parser.add_argument('-ns', type=int, default=10, help="Number of states for TD-SCF (default: 10)")
    parser.add_argument('-sol', action='store_true', help="Toggle solvation model usage on/off")
    parser.add_argument('--solvation_model', type=str, nargs='+',
                        default=["scfr=(scipcm,solvent=methanol)"],
                        help="List of solvation model strings (default: scfr=(scipcm,solvent=methanol))")
    # New options for output file base name and for removing existing files.
    parser.add_argument('-o', '--output', type=str, default="",
                        help="Output base filename for generated .gjf files. "
                             "If not provided, defaults to input base + '_array'.")
    parser.add_argument('--remove_existing', action='store_true',
                        help="Remove existing .gjf files with the same output base name before generating new ones.")
    
    args = parser.parse_args()
    
    # set the output base name if not provided.
    if not args.output:
        args.output = os.path.splitext(os.path.basename(args.input))[0] + "_array"
    
    try:
        gjf_files = generate_gjf_files(args)
        if not gjf_files:
            print("No .gjf files were generated.")
            sys.exit(1)
    except Exception as e:
        print(f"Error generating .gjf files: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
