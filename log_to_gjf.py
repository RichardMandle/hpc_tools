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
    
    args:
        log_file:   a Gaussian .log file containing at least one geometry.
    returns:
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
            continue  # skip over lines with different format.
        
        element = Chem.GetPeriodicTable().GetElementSymbol(int(parts[1]))
        x, y, z = parts[3], parts[4], parts[5]
        geometry.append((element, x, y, z))
    return geometry

def generate_gjf_file(args):
    """
    get the final geometry from the log file (args.input) and write a .gjf file
    
    args:
        the arguments from the command parser.
    Returns:
        the filename of the new .gjf file which was written
    """
    geometry = extract_final_geometry(args.input)
        
    base = args.output  # already set via -o or defaulted in main()
    
    if args.remove_existing:
        pattern = base + "_*.gjf"
        existing_files = glob.glob(pattern)
        for file in existing_files:
            os.remove(file)
            print(f"Removed existing file: {file}")
    
    route_opt = f"# {args.route} {args.functional}/{args.basis} "
    if args.ed:
        route_opt += " EmpiricalDispersion=gd3bj"
            
    gjf_filename = f"{base}.gjf"
    chk_filename = gjf_filename.replace(".gjf", ".chk")
    
    with open(gjf_filename, 'w') as gjf_file:
        if args.chk:
            gjf_file.write(f"%chk={chk_filename}\n")
        gjf_file.write(f"%mem={args.mem}GB\n")
        gjf_file.write(f"%nprocshared={args.cpu}\n")
        gjf_file.write(f"{route_opt}\n\n")
        gjf_file.write(f"Title Card: job generated from {args.input}\n\n")
        gjf_file.write("0 1\n")
        for atom in geometry:
            element, x, y, z = atom
            gjf_file.write(f"{element}    {x}    {y}    {z}\n")
        gjf_file.write("\n")
        
    print(f"Generated {gjf_filename}")
    return gjf_filename

def main():
    parser = argparse.ArgumentParser(
        description="Generate Gaussian .gjf input files (with chained OPT and TD-SCF jobs) "
                    "from a .log file and create a SLURM job array submission script."
    )
    # Gaussian input generation options.
    parser.add_argument('-i', '--input', required=True, type=str, help="Input Gaussian log file (.log)")
    parser.add_argument('-cpu', type=int, default=4, help="Number of CPU cores (default: 4)")
    parser.add_argument('-mem', type=str, default="4GB", help="Memory (default: 4GB)")
    parser.add_argument('-f', '--functional', type=str, nargs='+', default="b3lyp",
                        help="functional to use (e.g. default: b3lyp)")
    parser.add_argument('-b', '--basis', type=str, nargs='+', default="cc-pvdz",
                        help="basis set to use (default: cc-pvdz)")
    parser.add_argument('-ed', action='store_true', help="Toggle empirical dispersion (gd3bj) on/off")
    parser.add_argument('-chk', action='store_true', help="Toggle saving checkpoint file on/off")
    parser.add_argument('-o', '--output', type=str, default="",
                        help="Output base filename for generated .gjf files. "
                             "If not provided, defaults to input base + '_new'.")
    parser.add_argument('-r', '--route', type=str, default="",
                        help="The route section of the new job (e.g. OPT, FREQ etc.) default = "". "
                             "If not provided, defaults to input base + '_new'.")
    parser.add_argument('--remove_existing', action='store_true',
                        help="Remove existing .gjf files with the same output base name before generating new ones.")
    
    args = parser.parse_args()
    
    if not args.output:
        args.output = os.path.splitext(os.path.basename(args.input))[0] + "_new"
    
    try:
        gjf_file = generate_gjf_file(args)
        if not gjf_file:
            print("No .gjf files were generated.")
            sys.exit(1)
    except Exception as e:
        print(f"Error generating .gjf file: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
