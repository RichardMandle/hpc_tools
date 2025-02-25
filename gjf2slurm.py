import argparse
import os
import sys
import re 

'''
gjf2slurm.py - a small script for writing jobsubmission scripts (*.sh) for the slurm workload manager
                by reading the contents of a Gaussian input file (.gjf)
             
args:
    -i (str):   the input .gjf filename you are wanting to use.
    -t (str):   the max time you want the job to run for (in HH:MM:SS; defaults to 48:00:00)
    -m (bool):  turn off email notifications (begining and end) for the job
    -w (bool):  turn off checking for and correcting MS windows paths (e.g. C:\ this, D:\ that) in the .gjf file.
    
returns:
    ***.sh:     a .sh file you cna use to submit the .gjf input to the queue.   
'''


def initialize():
    parser = argparse.ArgumentParser( description='Generate a Slurm qsub file for a given .gjf file' )
    parser.add_argument('-i', '--filename', required=True, type=str, help='Input .gjf filename')    # By default, emails are sent. Using -m will turn them off.
    parser.add_argument('-t', '--time', default='48:00:00', type=str, help='Time for job (HH:MM:SS); defaults to 48h')    # how long do you want hte job to run for? defualt = 48:00:00
    parser.add_argument('-m', action='store_false', dest='mail', default=True, help='Turn off sending an email about the job status.')
    parser.add_argument('-w', action='store_false', dest='check_windows', default=True, help='Turn off checking for Windows errors in the .gjf file (e.g. "C:\\").') # By default, Windows path errors are checked. Using -w will turn this check off.
    return parser
    
def fix_windows_paths(line):
    """
    replace any Windows path in the given line with just the filename.
    
    The re expression below matches a drive letter (like C:), a backslash, and any number
    of directories ending with a filename. It then replaces the full path with the filename only. 
    
    Minimally tested!
    """
    # regex explanation:
    #   ([A-Za-z]:\\(?:[^\\\s]+\\)*) matches the drive letter and directories
    #   (?P<fname>[^\\\s]+) captures the filename (no backslashes or whitespace)
    pattern = re.compile(r'([A-Za-z]:\\(?:[^\\\s]+\\)*)(?P<fname>[^\\\s]+)')
    new_line = pattern.sub(lambda m: m.group('fname'), line)
    return new_line
    
def parse_gjf_file(args):
    """
    read a .gjf file, fix any Windows path errors in lines starting with '%',
    and extract information needed to build the slurm submission script.
    """
    mem = "1GB"
    nprocshared = "1"
    corrected_lines = []
    changed = False
    try:
        with open(args.filename, 'r') as file:
            for line in file:
                # Only fix lines that start with '%' (typical for Gaussian input directives)
                if line.startswith('%') and args.check_windows and 'C:\\' in line:
                    new_line = fix_windows_paths(line)
                    if new_line != line:
                        print(f"Fixed Windows path in line:\nOld: {line}New: {new_line}")
                        line = new_line
                        changed = True
                if line.startswith('%mem='):
                    mem_value = line.strip().split('=')[1]
                    # Remove trailing 'B' if present (e.g. "8GB" -> "8G")
                    mem = mem_value[:-1] if mem_value.endswith('B') else mem_value
                elif line.startswith('%nprocshared='):
                    nprocshared = line.strip().split('=')[1]
                corrected_lines.append(line)
    except FileNotFoundError:
        raise

    # if any changes were made, write the corrected content back to the file.
    if changed:
        with open(args.filename, 'w') as file:
            file.writelines(corrected_lines)
        print(f"Updated file {args.filename} with corrected Windows paths.")
    
    print(f'vmem={mem} nproc={nprocshared}')
    return mem, nprocshared

def make_slurm_script(args, vmem='8G', nproc=8, maxdisk=8):
    """
    Writes a simple job submission script for SLURM.
    """
    base_name = os.path.splitext(args.filename)[0]
    output_script = base_name + '.sh'
    with open(output_script, 'w') as f:
        f.write('#!/bin/bash\n')
        f.write(f'#SBATCH --job-name={base_name}_gaussian\n')
        f.write(f'#SBATCH --time={args.time}\n')
        f.write(f'#SBATCH --mem={vmem}\n')
        f.write(f'#SBATCH --cpus-per-task={nproc}\n')
        f.write(f'#SBATCH --output={base_name}-%j.out\n')
        f.write(f'#SBATCH --error={base_name}-%j.err\n')

        if args.mail:
            f.write('#SBATCH --mail-type=BEGIN,END,FAIL\n')
            f.write(f'#SBATCH --mail-user={args.mail}\n')
            
        
        f.write('module add gaussian\n') # load that module
        
        f.write('export GAUSS_SCRDIR=$TMP_SHARED\n')

        f.write(f'g16 {args.filename}\n')
        
        f.write('rm -rf $GAUSS_SCRDIR/*\n') # cleanup, including temporary directory
        
    print(f"SLURM submission script generated: {output_script}")

def main():
    parser = initialize()
    args = parser.parse_args()
    
    try:
        mem, nprocshared = parse_gjf_file(args)
    except FileNotFoundError:
        print(f"Error: The file {args.filename} does not exist.")
        sys.exit(1)
    except Exception as e:
        print(f"An error occurred while loading the file: {e}")
        sys.exit(1)
    
    make_slurm_script(args, vmem=mem, nproc=nprocshared, maxdisk=5)

if __name__ == "__main__":
    main()
