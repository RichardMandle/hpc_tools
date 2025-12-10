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


def write_slurm_single(inp_file, walltime="48:00:00", clean_orca=False):
    """
    Single-job mode: one .inp -> one .slurm
    """
    # patterns of temporary files to remove at the end if requested
    # check a few outputs over the next few months and add/remove.
    tmp_patterns = ["*.gbw", "*.tmp", "*.densities", "*.engrad", "*.ges", "*_tmp.*"]

    if clean_orca:
        closing_remarks = "rm -f " + " ".join(tmp_patterns)
    else:
        closing_remarks = ""

    job_name, nprocs, mem_gb = parse_orca_input(inp_file)
    slurm_file = inp_file.replace(".inp", ".slurm")
    print(f"\n[Single] Job Name: {job_name}\nCpu cores: {nprocs}\nMemory: {mem_gb} GB")

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

{orca_path} {inp_file}
""")

        if closing_remarks:
            f.write(f"\n# Clean up ORCA temporary files\n{closing_remarks}\n")

        f.write("\n")

    print(f"SLURM script for {inp_file} was written to: {slurm_file}")
    if clean_orca:
        print(f"... and at your request, this will remove some temporary files at the end of the run:")
        print("   " + " ".join(tmp_patterns))


def write_slurm_array(task_prefix, walltime="48:00:00", clean_orca=False):
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

    # tmp cleanup patterns
    tmp_patterns = ["*.gbw", "*.tmp", "*.densities", "*.engrad", "*.ges", "*_tmp.*"]
    if clean_orca:
        closing_remarks = "rm -f " + " ".join(tmp_patterns)
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

{orca_path} "$inp_file"
""")

        if closing_remarks:
            f.write(f"\n# Clean up ORCA temporary files\n{closing_remarks}\n")

        f.write("\n")

    print(f"\nArray SLURM script written to: {slurm_file}")
    print(f"  Array range: 0-{max_index}")
    if clean_orca:
        print(f"... and at your request, each task will remove some temporary files at the end of the run:")
        print("   " + " ".join(tmp_patterns))


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

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    if args.inp_file:
        # single-job mode
        if not args.inp_file.endswith(".inp"):
            print("Error: inp_file must be an .inp file")
            sys.exit(1)
        write_slurm_single(args.inp_file, walltime=args.time, clean_orca=args.clean_orca)
    else:
        # array mode
        write_slurm_array(args.task_prefix, walltime=args.time, clean_orca=args.clean_orca)
