import os
import glob
import argparse
import textwrap

'''
gau2orca
What does it do?

Will take a gaussian .gjf input file and construct an appropriate .in file for orca.
examples:

    python gau2orca.py -i myfile.gjf -o myfile.in  
Simply takes myfile.gjf and creates the same thing in orca .in format
    
    python gau2orca.py -i myfile.gjf -o myfile.in -cpu 4 -mem 4GB
As above, but requests 4 CPU cores and 4GB of RAM
    
    python gau2orca.py -i myfile.gjf -o myfile.in -m "GFN2-xTB opt freq" -cpu 1 -mem 1GB
Takes the .gjf file and requests and opt+freq job with the GFN2-xTB method, with 1 core and 1GB vram

    python gau2orca.py -i ./inputs -all -m "GFN2-xTB" -cpu 2 -mem 2GB
Much as above, but does it for an entire folder (./inputs; -all)
'''

def parse_args():
    parser = argparse.ArgumentParser(
        description="Convert Gaussian .gjf files to ORCA .inp format.",
        epilog=textwrap.dedent("""\
            Examples:
              python gau2orca.py -i myfile.gjf -o myfile.inp
              python gau2orca.py -i myfile.gjf -o myfile.inp -cpu 4 -mem 8GB
              python gau2orca.py -i ./inputs -all -m "GFN2-xTB" -cpu 2 -mem 2GB
              python gau2orca.py -i mol.gjf -o mol.inp -b "%tdscf, nroots 10, end"
        """),
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument("-i", "--input", help="Input .gjf file or directory.")
    parser.add_argument("-n", "--name", help="Name of the job to use (defaults to same as .gjf file")
    parser.add_argument("-o", "--output", help="Output .inp file (ignored if -all is used).")
    parser.add_argument("-m", "--method", default="", help="ORCA method and basis set.")
    parser.add_argument("-cpu", type=int, help="Number of CPU cores.", metavar='N')
    parser.add_argument("-mem", type=str, help="Memory allocation (e.g., 4GB).")
    parser.add_argument("-b", "--block", help="Custom ORCA input block (comma-separated, e.g. '%tdscf, nroots 10, end').")
    parser.add_argument("-all", action="store_true", help="Process all .gjf files in a directory.")
    parser.add_argument("-sge", action="store_true", help="Modify the SGE submission script.")
    parser.add_argument("-ex", "--examples", action="store_true", help="Show example usages and exit.")

    args = parser.parse_args()

    if args.examples:
        print_examples()
        exit(0)

    # validation
    if args.mem and not args.mem.lower().endswith("gb"):
        parser.error("Memory must be specified in GB, e.g., -mem 8GB")

    if not args.all and (not args.input or not args.output):
        parser.error("Either use -all to process all .gjf files in a folder, or provide both -i and -o.")

    return args

def convert_gjf_to_orca(args):
    '''
    Convert a single Gaussian .gjf file to an ORCA .inp file
    '''
    
    gjf_file = args.input
    orca_file = args.output
    method = args.method.strip()
    nproc = args.cpu
    mem = args.mem

    with open(gjf_file, 'r') as f:
        lines = f.readlines()

    # read nproc and mem from the parent gjf file if not given
    for line in lines:
        if line.startswith('%nprocshared') and not nproc:
            nproc = int(line.strip().split('=')[-1])
        elif line.startswith('%mem') and not mem:
            mem = line.strip().split('=')[-1]

    # Set defaults (could just do this in the arg parser)
    if not nproc:
        nproc = 4
    if not mem:
        mem = "4GB"

    blank_lines = [i for i, line in enumerate(lines) if line.strip() == '']
    job_title = args.name if args.name else lines[blank_lines[0] + 1].strip() if len(blank_lines) > 1 else "ORCA_JOB"

    # read the method from route section if not provided
    if not method:
        forbidden = ["geom=connectivity", "nosymm", "iop", "pop"]
        method_parts = []
        for line in lines:
            if line.strip().startswith('#'):
                route = line.strip()[1:].split()
                for item in route:
                    if not any(f in item.lower() for f in forbidden):
                        method_parts.append(item)
                break
        method = ' '.join(method_parts) if method_parts else "B3LYP D3BJ cc-pVTZ"

    charge_mult = lines[blank_lines[1] + 1].strip() if len(blank_lines) > 1 else "0 1"
    
    # if we have new blocks to add, parse them here:   
    if args.block:
      if args.block and not args.block.strip().startswith('%'):
        print("*** WARNING ***\nCustom block should begin with a block label like '%tdscf'\nThis Will Fail")
      if args.block and "end" not in args.block.lower():
        print("*** WARNING ***\nYour block does not contain 'end'. ORCA blocks usually require this.")
      block_lines = [line.strip() for line in args.block.split(',')]
            
    #### geometry block ####
    geometry = []
    for line in lines[blank_lines[1] + 2:]:
        tokens = line.split()
        if len(tokens) >= 4:
            element, x, y, z = tokens[0], tokens[-3], tokens[-2], tokens[-1]
            geometry.append(f"{element} {x} {y} {z}")
        else:
            break

    mem_value = int(mem.lower().replace('gb', '').strip()) * 1000

    with open(orca_file, 'w') as f:
        f.write(f"! {method.strip()}\n")
        f.write(f"%pal nprocs {nproc} end\n")
        f.write(f"%maxcore {mem_value}\n")
        if args.block:
          for line in block_lines:
            f.write(line + '\n')
        f.write(f"#{job_title}\n")
        f.write(f"* xyz {charge_mult}\n")
        for atom in geometry:
            f.write(atom + '\n')
        f.write("*\n")

    print(f"Converted {gjf_file} -> {orca_file}")

def process_all_gjf(args):
    '''
    Convert all .gjf files in the specified directory
    '''
    directory = args.input
    for gjf_file in glob.glob(os.path.join(directory, "*.gjf")):
        orca_file = gjf_file.replace(".gjf", ".inp")
        args.input = gjf_file
        args.output = orca_file
        convert_gjf_to_orca(args)

def modify_sge_script(args):
    '''
    Modify existing SGE script for ORCA submission
    '''
    nproc = args.cpu or 4
    mem = args.mem or "4GB"

    sge_script = None
    for file in os.listdir():
        if file.endswith(".sh"):
            with open(file, 'r') as f:
                if "#$ -cwd" in f.read():
                    sge_script = file
                    break

    if sge_script:
        new_script = sge_script.replace(".sh", "_orca.sh")
        with open(sge_script, 'r') as f:
            lines = f.readlines()

        with open(new_script, 'w') as f:
            for line in lines:
                if "module load gaussian" in line:
                    f.write("module load orca\n")
                elif "#$ -pe" in line:
                    f.write(f"#$ -pe smp {nproc}\n")
                elif "#$ -l h_vmem=" in line:
                    f.write(f"#$ -l h_vmem={mem}\n")
                else:
                    f.write(line)

        print(f"Modified SGE script: {new_script}")
    else:
        print("No SGE script found.")

def print_examples():
    print("\n--- gau2orca Example Usage ---\n")
    print("Convert single file:")
    print("  python gau2orca.py -i mol.gjf -o mol.inp")
    print()
    print("With method override and resources:")
    print("  python gau2orca.py -i mol.gjf -o mol.inp -m \"GFN2-xTB opt freq\" -cpu 4 -mem 8GB")
    print()
    print("Batch convert directory:")
    print("  python gau2orca.py -i ./inputs -all -m \"B3LYP D3BJ cc-pVTZ\" -cpu 4 -mem 16GB")
    print()
    print("Add a TDDFT block:")
    print("  python gau2orca.py -i mol.gjf -o mol.inp -b \"%tdscf, nroots 10, maxdim 20, end\"")
    print()
    print("Fix SGE submission script:")
    print("  python gau2orca.py -i mol.gjf -o mol.inp -sge")
    print()

def main():
    args = parse_args()

    if args.all:
        process_all_gjf(args)
    else:
        convert_gjf_to_orca(args)

    if args.sge:
        modify_sge_script(args)

if __name__ == "__main__":
    main()
