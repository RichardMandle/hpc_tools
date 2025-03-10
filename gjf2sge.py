import argparse
import glob
import os

#gjf2sge.py - script for generating SGE submission files from Gaussian input(s).

def initialize():
    parser = argparse.ArgumentParser(description='Generate a SGE qsub file for a given .gjf file')    parser.add_argument('-i', '--input', default='', type=str, help='Input .gjf filename')
    parser.add_argument('-t', '--task', default='', type=str, help='Base part of the .gjf filename for task array jobs; e.g. myfile_{x}.gjf would be "myfile_".')
    parser.add_argument('-v', '--gver', default='g16', type=str, help='Gaussian version to use')
    return parser

def get_task_count(args):
    """
    get glob to count the number of .gjf files that start with the task base.
    """
    files = glob.glob(args.task + "*.gjf")
    return len(files)

def parse_gjf_file(filepath):
    '''    Parse a .gjf file and extract information needed to build SGE qsub script    '''
    mem = "1GB"    nprocshared = "1"    with open(filepath, 'r') as file:        for line in file:            if line.startswith('%mem='):                mem = (line.strip().split('=')[1]).split("G")[0]            elif line.startswith('%nprocshared='):                nprocshared = line.strip().split('=')[1]    print(f'vmem={mem} nproc={nprocshared}')    return mem, nprocshared

def make_sge_script(args, vmem = '8G', nproc = 8, maxdisk = 8):
    '''
    Just writes a simple job submission script for the ARC3/4 computer at UoL (uses SGE).    '''
    if args.task:
        script_filename = args.task + '.sh'
        num_tasks = get_task_count(args)
    else:
        script_filename = args.input.split('.')[0] + '.sh'
            with open(script_filename, 'w') as f:        f.write('#$ -cwd\n')        f.write('#$ -V\n')        f.write('#$ -l h_rt=48:00:00\n')        f.write(f'#$ -l h_vmem={int((vmem / nproc) * 1.1)}\n') # SGE allocates memory per core, so the total ram requested should be vmem/nproc *1.1 (must be int for Gaussian; the extra 10% to stop jobs failing for being OOM)        f.write(f'#$ -pe smp {nproc}\n')        f.write(f'#$ -l disk={maxdisk}G\n')
        if args.task: # if its a task array job, we need to add this line.
            f.write(f'#$ -t 1-{num_tasks}\n')        
        f.write('module add gaussian\n')        f.write('export GAUSS_SCRDIR=$TMPDIR\n')       
        if args.task:
            # for task arrays we'll have the filename constructed as: task_base + _${SGE_TASK_ID}.gjf
            f.write(f'{args.gver} {args.task}_$SGE_TASK_ID.gjf\n')
        else:
            f.write(f'{args.gver} {args.input}\n')
        
        f.write('rm *.sh.* core* \n') # cleanup files at the end
        
    print(f"SGE submission script generated: {script_filename}")
def main():
    args = initialize().parse_args()
    # do a sanity check for task base: ensure it ends with an underscore.
    if args.task:
        first_file = args.task + "_1.gjf"
        mem, nprocshared = parse_gjf_file(first_file)
    else:
        mem, nprocshared = parse_gjf_file(args.input)

    make_sge_script(args, vmem=int(mem), nproc=int(nprocshared), maxdisk=5)

if __name__ == "__main__":
    main()
