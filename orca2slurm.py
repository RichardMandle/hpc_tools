import sys
import os
import re
import subprocess
import argparse
import textwrap
import glob


"""
Reads ORCA .inp files and produces .slurm scripts for AIRE.
Supports:
  - single-job mode (one .inp -> one .slurm)
  - array mode (prefix -> many .inp -> one array .slurm)
  - reads the .inp file for the correct .xyz file and handles coppying etc
  
"""


def parse_xyz_from_orca_input(inp_file):
    """
    Extract the xyz filename from:
    * xyzfile 0 1 filename.xyz
    """
    with open(inp_file, "r") as f:
        for line in f:
            line = line.strip()
            if line.lower().startswith("* xyzfile"):
                parts = line.split()
                if len(parts) >= 5:
                    return parts[4]
    return None


def working_path_block(inp_file, xyz_file=None, storage='TMP_LOCAL',):
    '''
    Function for setting the working directory to be used

    xyz_file isn't passed explicitly (yet)

    Let the user pick between fastest (TMP_LOCAL; on node NVME), fast-ish (TMP_SHARED; lustre-NVME), or slow (SCRATCH; lustre-disk)
    '''

    storage = storage.strip('$').upper()

    possible_storage = ['TMP_LOCAL', 'TMP_SHARED', 'SCRATCH']
    if storage not in possible_storage:
        print(f"You selected storage as {storage}, but it should only be one of {possible_storage}")
        print(f"Defaulting to TMP_LOCAL")
        storage = "TMP_LOCAL"

    if xyz_file is None:
        xyz_file = parse_xyz_from_orca_input(inp_file)

    if storage == "SCRATCH":
        text = "working_dir=$(pwd)"
    else:
        text = f"""
cp "{inp_file}" ${storage}/
cp "{xyz_file}" ${storage}/
cd ${storage}
working_dir=$(pwd)
"""

    return text, storage


def return_job(storage):
    '''
    we'll copy run files onto our scratch path and then, once the job is finsihed, copy back stuff we care about.

    we'll delete *.tmp* anyway.

    '''

    if storage == "SCRATCH":
        return ""

    return """
rm -f *.tmp*
rsync -a . "$working_dir"
cd "$working_dir"
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
    return None


def parse_orca_input(inp_file):
    """
    Extract job name, nprocs, and memory from ORCA .inp file
    """
    with open(inp_file, 'r') as f:
        lines = f.readlines()

    job_name = os.path.splitext(os.path.basename(inp_file))[0]
    nprocs = 4
    maxcore = 4000

    for line in lines:
        if line.strip().lower().startswith('%pal'):
            m = re.search(r'nprocs\s+(\d+)', line, re.IGNORECASE)
            if m:
                nprocs = int(m.group(1))
        elif line.strip().lower().startswith('%maxcore'):
            m = re.search(r'\d+', line)
            if m:
                maxcore = int(m.group(0))

    mem_total_gb = ((nprocs * maxcore) + 999) // 1000
    return job_name, nprocs, mem_total_gb


def make_safe_cleanup(job_name):
    exts = ["gbw", "tmp", "densities", "engrad", "ges", "bibtex", "hess"]
    parts = [f'"{job_name}.{ext}"' for ext in exts]
    parts.append(f'"{job_name}"_tmp.*')
    parts.append(f'"{job_name}".finalensemble.globaliter.*.xyz')
    return "rm -f " + " ".join(parts)


def write_slurm_single(inp_file, walltime, clean_orca, xyz_file, storage):

    job_name, nprocs, mem_gb = parse_orca_input(inp_file)

    if xyz_file is None:
        xyz_file = parse_xyz_from_orca_input(inp_file)

    if clean_orca:
        closing_remarks = make_safe_cleanup(job_name)
    else:
        closing_remarks = ""

    slurm_file = inp_file.replace(".inp", ".slurm")

    print(f"\n[Single] Job: {job_name}; CPUs: {nprocs}; RAM: {mem_gb} GB; Scratch: {storage}")

    if nprocs > 1:
        orca_path = get_full_orca_path()
        if orca_path is None:
            print("***Warning***: Could not find ORCA with `which orca`. Using fallback 'orca'.")
            orca_path = "orca"
    else:
        orca_path = "orca"

    path_text, storage = working_path_block(inp_file, xyz_file, storage)
    return_text = return_job(storage)

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

{orca_path} "{inp_file}"

{return_text}
""")

        if closing_remarks:
            f.write(f"\n# Clean up ORCA temporary files\n{closing_remarks}\n")

    print(f"SLURM script written to: {slurm_file}")


def write_slurm_array(task_prefix, walltime, clean_orca, storage):

    pattern = f"{task_prefix}*.inp"
    inp_files = sorted(glob.glob(pattern))

    if not inp_files:
        print(f"No .inp files found matching pattern: {pattern}")
        sys.exit(1)

    first_job_name, nprocs, mem_gb = parse_orca_input(inp_files[0])

    array_job_name = f"{task_prefix}array"
    slurm_file = f"{task_prefix}array.slurm"
    max_index = len(inp_files) - 1

    if nprocs > 1:
        orca_path = get_full_orca_path() or "orca"
    else:
        orca_path = "orca"

    bash_array_lines = ["inp_files=("]
    for fpath in inp_files:
        bash_array_lines.append(f'  "{fpath}"')
    bash_array_lines.append(")")
    bash_array_block = "\n".join(bash_array_lines)

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

{bash_array_block}

inp_file=${{inp_files[$SLURM_ARRAY_TASK_ID]}}
job_name=$(basename "$inp_file" .inp)

xyz_file=$(grep -i "^\\* xyzfile" "$inp_file" | awk '{{print $5}}')

if [ "{storage}" != "SCRATCH" ]; then
    cp "$inp_file" ${storage}/
    cp "$xyz_file" ${storage}/
    cd ${storage}
    working_dir=$(pwd)
else
    working_dir=$(pwd)
fi

{orca_path} "$inp_file"

if [ "{storage}" != "SCRATCH" ]; then
    rm -f *.tmp*
    rsync -a . "$working_dir"
    cd "$working_dir"
fi
""")

        if clean_orca:
            f.write("\n# Clean up ORCA temporary files\n")
            f.write('rm -f "$job_name".gbw "$job_name".tmp*\n')

    print(f"\nArray SLURM script written to: {slurm_file}")
    print(f"Array range: 0-{max_index}")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Creates .slurm files from ORCA inputs (.inp) for AIRE (single or array mode).",
        epilog=textwrap.dedent("""\
            Examples:
              python orca2slurm.py myfile.inp
              python orca2slurm.py myfile.inp --time 24:00:00 --clean-orca
              python orca2slurm.py --task-prefix cob1_ --time 48:00:00 --clean-orca
        """),
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    group = parser.add_mutually_exclusive_group(required=True)

    group.add_argument("inp_file", nargs="?",
                       help="ORCA input (.inp) file for single-job mode.")

    group.add_argument("--task-prefix",
                       help="Prefix for array mode. All files matching '<prefix>*.inp' will be used.")

    parser.add_argument("-t", "--time", default="48:00:00",
                        help="Specify job wallclock time in hh:mm:ss")

    parser.add_argument("-x", "--xyz_file", default=None,
                        help="Pass the .xyz file to use.")

    parser.add_argument("--clean-orca", action="store_true",
                        help="Remove ORCA temporary files at end of job.")

    parser.add_argument("-s", "--storage", default="TMP_LOCAL",
                        help="TMP_LOCAL, TMP_SHARED, SCRATCH")

    return parser.parse_args()


if __name__ == "__main__":

    args = parse_args()

    if args.inp_file:
        if not args.inp_file.endswith(".inp"):
            print("Error: inp_file must be an .inp file")
            sys.exit(1)

        write_slurm_single(
            inp_file=args.inp_file,
            walltime=args.time,
            clean_orca=args.clean_orca,
            xyz_file=args.xyz_file,
            storage=args.storage
        )

    else:
        write_slurm_array(
            task_prefix=args.task_prefix,
            walltime=args.time,
            clean_orca=args.clean_orca,
            storage=args.storage
        )
