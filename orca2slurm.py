
import sys
import os
import re
import shutil
import subprocess

'''
small script that reads an orca .inp file and produces an appropriate
.slurm file for submission to the queue.

does a few things to achieve this:
1) reads the orca input file to determine # cores, RAM etc
2) gets the full path to ORCA (needed for parallel runs)
3) loads openmpi etc

limited testing; email r<dot>mandle<at>leeds<dot>ac<dot>uk with any problems/errors
'''


def get_full_orca_path():
    '''
    If we haven't already done module load orca in the terminal, then we'll get a duff
    path for orca and it wont work (for parallel runs)...
    '''
    cmd = "bash -c 'module load orca && which orca'"
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode == 0:
        return result.stdout.strip()
    else:
        return None

def parse_orca_input(inp_file):
    '''
	Extract job name, nprocs, and memory from ORCA .inp file
	'''
    with open(inp_file, 'r') as f:
        lines = f.readlines()

    job_name = os.path.splitext(os.path.basename(inp_file))[0]
    nprocs = 4  # default
    maxcore = 4000  # default in MB

    for line in lines:
        if line.strip().startswith('#') and job_name == os.path.splitext(os.path.basename(inp_file))[0]:
            job_name = line.strip('#').strip().replace(' ', '_')
        elif line.strip().lower().startswith('%pal'):
            m = re.search(r'nprocs\s+(\d+)', line, re.IGNORECASE)
            if m:
                nprocs = int(m.group(1))
        elif line.strip().lower().startswith('%maxcore'):
            m = re.search(r'\d+', line)
            if m:
                maxcore = int(m.group(0))

    # convert per-core memory (in MB) to total memory in GB (and round up)
    mem_total_gb = ((nprocs * maxcore) + 999) // 1000

    return job_name, nprocs, mem_total_gb

def write_slurm_script(inp_file):
    job_name, nprocs, mem_gb = parse_orca_input(inp_file)
    slurm_file = inp_file.replace(".inp", ".slurm")
    print(f"\nJob Name: {job_name}\nCpu cores: {nprocs}\nMemory: {mem_gb}")
    # so if we have more than one cpu core, we need to call the full orca path, which we'll do with shutil and "which orca":
    if nprocs > 1:
        orca_path = get_full_orca_path()
        print(f"ORCA path: {orca_path}")
        if orca_path is None:
            print("***Warning***: Could not find ORCA with `which orca`. Using fallback 'orca', which will probably fail.")
            orca_path = "orca"
    else:
        orca_path = "orca"
        
    with open(slurm_file, 'w') as f:
        f.write(f"""#!/bin/bash
#SBATCH --job-name={job_name}
#SBATCH --output={job_name}.out
#SBATCH --error={job_name}.err
#SBATCH --ntasks={nprocs}
#SBATCH --cpus-per-task=1
#SBATCH --mem={mem_gb}G
#SBATCH --time=2-00:00:00

module add openmpi 
module load orca

{orca_path} {inp_file}
""")

    print(f"SLURM script for {inp_file} was written to: {slurm_file}\n")

if __name__ == "__main__":
    if len(sys.argv) != 2 or not sys.argv[1].endswith(".inp"):
        print("Usage: python orca_slurm_writer.py your_input.inp")
        sys.exit(1)

    write_slurm_script(sys.argv[1])
