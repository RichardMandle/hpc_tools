import sys
import os
import re
import shutil
import subprocess
import argparse
import textwrap
import glob

"""
Reads ORCA .inp files and produces .slurm scripts for AIRE.
Supports:
  - single-job mode (one .inp -> one .slurm)
  - array mode (prefix -> many .inp -> one array .slurm)
"""


def working_path_block(inp_file, xyz_file = None, storage='TMP_LOCAL',):
    '''
    Function for setting the working directory to be used
    
    xyz_file isn't passed explicitly (yet)
    
    Let the user pick between fastest (TMP_LOCAL; on node NVME), fast-ish (TMP_SHARED; lustre-NVME), or slow (SCRATCH; lustre-disk)
    '''
    storage = storage.strip('$').upper() # strip out dollar signs incase they are included; but do it quietly; change to CAPS
    
    # check the user is using a sensible place for storage, and if not default to NVME flash on node ($TMP_LOCAL).
    possible_storage = ['TMP_LOCAL','TMP_SHARED','SCRATCH']
    if storage not in possible_storage:
        print(f"You selected storage as {storage}, but it should only be one of {possible_storage}")
        print(f"Defaulting to TMP_LOCAL")
        storage="TMP_LOCAL"
        
    job_name = os.path.splitext(os.path.basename(inp_file))[0]
    if not xyz_file:
        xyz_file = f"{job_name}.xyz"
        
    text = f"""
cp {inp_file} ${storage}/{inp_file} 
cp {xyz_file} ${storage}/{xyz_file}
cd ${storage}

working_dir=pwd
    """
    if storage == 'SCRATCH':
        '''
        This isn't optimal, but if they ask for it we shouldn't stop them.
        '''
        text =f"working_dir=pwd"
    
    return text, storage
    
def return_job(storage):
    '''
    we'll copy run files onto our scratch path and then, once the job is finsihed, copy back stuff we care about.
    
    we'll delete *.tmp* anyway. 
    
    '''
    
    text = f"""
rm *.tmp*
cp ${storage}/* $working_dir
rm -rf ${storage}
    """
    return text

def get_full_orca_path():
    """
    if we haven't already done 'module load orca' in the terminal, then we'll get a duff
    path for orca and it wont work (for parallel runs)...
    """
    cmd = "bash -c 'module load orca && which orca'"
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode == 0:
        return result.stdout.strip()
    else:
        return None


def parse_orca_input(inp_file):
    """
    Extract job name, nprocs, and memory from ORCA .inp file
    """
    with open(inp_file, 'r') as f:
        lines = f.readlines()

    job_name = os.path.splitext(os.path.basename(inp_file))[0]
    nprocs = 4      # default
    maxcore = 4000  # default in MB (per core)

    for line in lines:
        # crude header check; adjust to taste if you use a different style
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

    # convert per-core memory (in MB) to total memory in GB (round up)
    mem_total_gb = ((nprocs * maxcore) + 999) // 1000

    return job_name, nprocs, mem_total_gb

def make_safe_cleanup(job_name):
    # delete ONLY files belonging to this job_name
    exts = ["gbw", "tmp", "densities", "engrad", "ges", "bibtex", "hess"]
    parts = [f'"{job_name}.{ext}"' for ext in exts]
    parts.append(f'"{job_name}"_tmp.*')
    parts.append(f'"{job_name}".finalensemble.globaliter.*.xyz')  # optional, if you want
    return "rm -f " + " ".join(parts)

def write_slurm_single(inp_file, walltime="48:00:00", clean_orca=False, xyz_file = None, storage = None):
    """
    Single-job mode: one .inp -> one .slurm
    """
    # patterns of temporary files to remove at the end if requested
    # check a few outputs over the next few months and add/remove.
    
    job_name, nprocs, mem_gb = parse_orca_input(inp_file)
    
    if clean_orca:
        closing_remarks = make_safe_cleanup(job_name)
    else:
        closing_remarks = ""
    
    slurm_file = inp_file.replace(".inp", ".slurm")
    print(f"\n[Single] Job: {job_name}; CPUs: {nprocs}; RAM: {mem_gb} GB; Scratch: {args.storage}")

    # If we have more than one cpu core, we need the full orca path (module-loaded)
    if nprocs > 1:
        orca_path = get_full_orca_path()
        print(f"ORCA path: {orca_path}")
        if orca_path is None:
            print("***Warning***: Could not find ORCA with `which orca`. "
                  "Using fallback 'orca', which will probably fail.")
            orca_path = "orca"
    else:
        orca_path = "orca"
        
    path_text, storage_text = working_path_block(inp_file = inp_file, xyz_file = xyz_file, storage=args.storage)
    return_text = return_job(storage = storage_text)

    with open(slurm_file, 'w') as f:
        f.write(f"""#!/bin/bash
#SBATCH --job-name={job_name}
#SBATCH --output={job_name}.out
#SBATCH --error={job_name}.err
#SBATCH --ntasks={nprocs}
#SBATCH --nodes=1
#SBATCH --cpus-per-task=1
#SBATCH --mem={mem_gb}G
#SBATCH --time={walltime}

module add openmpi
module load orca

{path_text}

{orca_path} {inp_file}

{return_text}
""")

        if closing_remarks != "":
            f.write(f"\n# Clean up ORCA temporary files\n{closing_remarks}\n")

        f.write("\n")

    print(f"SLURM script for {inp_file} was written to: {slurm_file}")
    if clean_orca:
        print(f"... and at your request, this will remove some temporary files at the end of the run:")

def write_slurm_array(task_prefix, walltime="48:00:00", clean_orca=False, xyz_file = None, storage = None):
    """
    Array mode: prefix -> many .inp -> one array .slurm
    Finds all {task_prefix}*.inp in the current directory.
    """
    pattern = f"{task_prefix}*.inp"
    inp_files = sorted(glob.glob(pattern))

    if not inp_files:
        print(f"No .inp files found matching pattern: {pattern}")
        sys.exit(1)

    print(f"\n[Array] Found {len(inp_files)} input files:")
    for fpath in inp_files:
        print(f"  {fpath}")

    # use just the first file to decide resources
    first_job_name, nprocs, mem_gb = parse_orca_input(inp_files[0])
    print(f"\n[Array] Using resources from first file ({inp_files[0]}):")
    print(f"Cpu cores: {nprocs}\nMemory: {mem_gb} GB")

    # throw an error if other files have different settings
    for other in inp_files[1:]:
        jname, np_other, mem_other = parse_orca_input(other)
        if np_other != nprocs or mem_other != mem_gb:
            print(f"BIG WARNING: {other} has nprocs={np_other}, mem={mem_other} GB "
                  f"(first file: nprocs={nprocs}, mem={mem_gb} GB). "
                  "The array will *try* to use the first file's settings for all tasks but this might fail.")

        
    if clean_orca:
        closing_remarks = make_safe_cleanup(job_name)
    else:
        closing_remarks = ""

    # one job name for the whole array
    array_job_name = f"{task_prefix}array"
    slurm_file = f"{task_prefix}array.slurm"

    # ORCA path as before
    if nprocs > 1:
        orca_path = get_full_orca_path()
        print(f"\nORCA path: {orca_path}")
        if orca_path is None:
            print("***Warning***: Could not find ORCA with `which orca`. "
                  "Using fallback 'orca', which will probably fail.")
            orca_path = "orca"
    else:
        orca_path = "orca"

    # Build the bash array of input files
    bash_array_lines = ["inp_files=("]
    for fpath in inp_files:
        bash_array_lines.append(f'  "{fpath}"')
    bash_array_lines.append(")")
    bash_array_block = "\n".join(bash_array_lines)

    max_index = len(inp_files) - 1
        
    path_text, storage_text = working_path_block(inp_file = inp_file, xyz_file = xyz_file, storage=args.storage)
    return_text = return_job(storage = storage_text)

    with open(slurm_file, 'w') as f:
        f.write(f"""#!/bin/bash
#SBATCH --job-name={array_job_name}
#SBATCH --output={array_job_name}_%A_%a.out
#SBATCH --error={array_job_name}_%A_%a.err
#SBATCH --ntasks={nprocs}
#SBATCH --nodes=1
#SBATCH --cpus-per-task=1
#SBATCH --mem={mem_gb}G
#SBATCH --time={walltime}
#SBATCH --array=0-{max_index}

module add openmpi
module load orca

# List of input files (indexed by $SLURM_ARRAY_TASK_ID)
{bash_array_block}

inp_file=${{inp_files[$SLURM_ARRAY_TASK_ID]}}
job_name=$(basename "$inp_file" .inp)

echo "Running ORCA on $inp_file (job_name=$job_name)"

{path_text}
{orca_path} "$inp_file"
{return_text}

""")

        if closing_remarks != "":
            f.write(f"\n# Clean up ORCA temporary files\n{closing_remarks}\n")

        f.write("\n")

    print(f"\nArray SLURM script written to: {slurm_file}")
    print(f"  Array range: 0-{max_index}")
    if clean_orca:
        print(f"... and at your request, each task will remove some temporary files at the end of the run.")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Creates .slurm files from ORCA inputs (.inp) for AIRE (single or array mode).",
        epilog=textwrap.dedent("""\
            Examples:
              # Single job
              python orca2slurm.py myfile.inp

              # Single job with cleanup and custom time
              python orca2slurm.py myfile.inp --time 24:00:00 --clean-orca

              # Array job: all cob1_*.inp in this directory
              python orca2slurm.py --task-prefix cob1_ --time 48:00:00 --clean-orca
        """),
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "inp_file",
        nargs="?",
        help="ORCA input (.inp) file for single-job mode."
    )
    

    group.add_argument(
        "--task-prefix",
        help="Prefix for array mode. All files matching '<prefix>*.inp' will be used."
    )

    parser.add_argument(
        "-t", "--time",
        default="48:00:00",
        help="Specify job wallclock time in hh:mm:ss (default: 48:00:00; limit = 48:00:00)"
    )
    parser.add_argument(
        "--clean-orca",
        action="store_true",
        help="If set, add commands at the end of the Slurm script to remove ORCA temporary files."
    )
    parser.add_argument(
        "-s", "--storage",
        default="TMP_LOCAL",
        help="Where to write files to? Choices: TMP_LOCAL, TMP_SHARED, SCRATCH. TMP_LOCAL is default as itthe fastest, on-node NVME M2 drives. TMP_SHARED is faster than SCRATCH"
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    if args.inp_file:
        # single-job mode
        if not args.inp_file.endswith(".inp"):
            print("Error: inp_file must be an .inp file")
            sys.exit(1)
        write_slurm_single(args.inp_file, walltime=args.time, clean_orca=args.clean_orca, xyz_file = None, storage = args.storage)
    else:
        # array mode
        write_slurm_array(args.task_prefix, walltime=args.time, clean_orca=args.clean_orca)
