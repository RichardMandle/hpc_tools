
import sys
import os
import re

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

    with open(slurm_file, 'w') as f:
        f.write(f"""#!/bin/bash
#SBATCH --job-name={job_name}
#SBATCH --output={job_name}.out
#SBATCH --error={job_name}.err
#SBATCH --ntasks=1
#SBATCH --cpus-per-task={nprocs}
#SBATCH --mem={mem_gb}G
#SBATCH --time=2-00:00:00

module load orca

orca {inp_file}
""")

    print(f"SLURM script for {inp_file} was written to: {slurm_file}")

if __name__ == "__main__":
    if len(sys.argv) != 2 or not sys.argv[1].endswith(".inp"):
        print("Usage: python orca_slurm_writer.py your_input.inp")
        sys.exit(1)

    write_slurm_script(sys.argv[1])