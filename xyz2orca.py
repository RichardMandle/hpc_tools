import os
import glob
import argparse
import textwrap

'''
xyz2orca
What does it do?

Take an .xyz file and create an orca .inp file that includes it.

    python xyz2orca.py -i myfile.xyz -o myfile.in  
Simply takes myfile.xyz and creates the same thing in orca .in format
    
    python xyz2orca.py -i myfile.xyz -o myfile.in -cpu 4 -mem 4GB
As above, but requests 4 CPU cores and 4GB of RAM
    
    python xyz2orca.py -i myfile.xyz -o myfile.in -m "GFN2-xTB opt freq" -cpu 1 -mem 1GB
Takes the .xyz file and requests and opt+freq job with the GFN2-xTB method, with 1 core and 1GB vram

    python xyz2orca.py -i ./inputs -all -m "GFN2-xTB" -cpu 2 -mem 2GB
Much as above, but does it for an entire folder (./inputs; -all)
'''

def parse_args():
    parser = argparse.ArgumentParser(
        description="Convert Gaussian .xyz files to ORCA .inp format.",
        epilog=textwrap.dedent("""\
            Examples:
              python xyz2orca.py -i myfile.xyz -o myfile.inp
              python xyz2orca.py -i myfile.xyz -o myfile.inp -cpu 4 -mem 8GB
              python xyz2orca.py -i ./inputs -all -m "GFN2-xTB" -cpu 2 -mem 2GB
              python xyz2orca.py -i mol.xyz -o mol.inp -b "%tdscf, nroots 10, end"
        """),
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument("-i", "--input", help="Input .xyz file or directory.")
    parser.add_argument("-n", "--name", help="Name of the job to use (defaults to same as .xyz file")
    parser.add_argument("-o", "--output", help="Output .inp file (ignored if -all is used).")
    parser.add_argument("-m", "--method", default="GFN2-xTB", help="ORCA method and basis set (default = \"GFN2-xTB\".")
    parser.add_argument("-c", "--charge_mult", default="0 1", help="charge / multiplicity entry (default =\"0 1\")")
    parser.add_argument("-cpu", type=int, default="4", help="Number of CPU cores.", metavar='N')
    parser.add_argument("-mem", type=str, default="4GB", help="Memory allocation (e.g., 4GB).")
    parser.add_argument("-b", "--block", help="Custom ORCA input block (comma-separated, e.g. '%tdscf, nroots 10, end').")
    parser.add_argument("-all", action="store_true", help="Process all .xyz files in a directory.")
    parser.add_argument("-ex", "--examples", action="store_true", help="Show example usages and exit.")

    args = parser.parse_args()

    if args.examples:
        print_examples()
        exit(0)

    # validation
    if args.mem and not args.mem.lower().endswith("gb"):
        parser.error("Memory must be specified in GB, e.g., -mem 8GB")

    if not args.all and (not args.input or not args.output):
        parser.error("Either use -all to process all .xyz files in a folder, or provide both -i and -o.")

    return args

def xyz_to_orca(args):
    '''
    
    '''
    
    xyz_file = args.input
    orca_file = args.output
    job_title = args.name
    method = args.method.strip()
    nproc = args.cpu
    mem_value = int(args.mem.lower().replace('gb', '').strip()) * 1000
    charge_mult = args.charge_mult

    # if we have new blocks to add, parse them here:   
    if args.block:
      if args.block and not args.block.strip().startswith('%'):
        print("*** WARNING ***\nCustom block should begin with a block label like '%tdscf'\nThis Will Fail")
      if args.block and "end" not in args.block.lower():
        print("*** WARNING ***\nYour block does not contain 'end'. ORCA blocks usually require this.")
      block_lines = [line.strip() for line in args.block.split(',')]


    with open(orca_file, 'w') as f:
        f.write(f"! {method.strip()}\n")
        f.write(f"%pal nprocs {nproc} end\n")
        f.write(f"%maxcore {mem_value}\n")
        if args.block:
          for line in block_lines:
            f.write(line + '\n')
        f.write(f"#{job_title}\n")
        f.write(f"* xyzfile {charge_mult} {xyz_file}\n")

    print(f"Converted {xyz_file} -> {orca_file}")

def process_all_xyz(args):
    '''
    Convert all .xyz files in the specified directory
    '''
    directory = args.input
    for file in glob.glob(os.path.join(directory, "*.xyz")):
        orca_file = file.replace(".xyz", ".inp")
        args.output = orca_file
        convert_xyz_to_orca(args)


def print_examples():
    print("\n--- xyz2orca Example Usage ---\n")
    print("Convert single file:")
    print("> python xyz2orca.py -i mol.xyz -o mol.inp\n")
    print("With method override and resources:")
    print("> python xyz2orca.py -i mol.xyz -o mol.inp -m \"GFN2-xTB opt freq\" -cpu 4 -mem 8GB\n")
    print("Batch convert directory:")
    print("> python xyz2orca.py -i ./inputs -all -m \"B3LYP D3BJ cc-pVTZ\" -cpu 4 -mem 16GB\n")
    print("Add a TDDFT block:")
    print("> python xyz2orca.py -i mol.xyz -o mol.inp -b \"%tdscf, nroots 10, maxdim 20, end\"\n")

def main():
    args = parse_args()

    if args.all:
        process_all_xyz(args)
    else:
        xyz_to_orca(args)


if __name__ == "__main__":
    main()
