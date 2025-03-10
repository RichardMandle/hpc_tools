import argparse

def initialize():
    parser = argparse.ArgumentParser(description='Generate a SGE qsub file for a given .gjf file')
    parser.add_argument('-i', '--input', default='', type=str, help='Input .gjf filename')
    parser.add_argument('-v', '--gver', default='g16', type=str, help='Gaussian version to use')
    return parser

def parse_gjf_file(filepath):
    '''
    Parse a .gjf file and extract information needed to build SGE qsub script
    '''
    mem = "1GB"
    nprocshared = "1"
    with open(filepath, 'r') as file:
        for line in file:
            if line.startswith('%mem='):
                mem = (line.strip().split('=')[1]).split("B")[0]
            elif line.startswith('%nprocshared='):
                nprocshared = line.strip().split('=')[1]

    print(f'vmem={mem} nproc={nprocshared}')
    return mem, nprocshared

def make_sge_script(args, vmem = '8G', nproc = 8, maxdisk = 8):
    '''
    Just writes a simple job submission script for the ARC3/4 computer at UoL (uses SGE).
    '''
    with open(args.input.split('.')[0] + '.sh', 'w') as f:
        f.write('#$ -cwd\n')
        f.write('#$ -V\n')
        f.write('#$ -l h_rt=48:00:00\n')
        f.write(f'#$ -l h_vmem={int((vmem / nproc) * 1.1)}\n') # SGE allocates memory per core, so the total ram requested should be vmem/nproc *1.1 (must be int for Gaussian; the extra 10% to stop jobs failing for being OOM)
        f.write(f'#$ -pe smp {nproc}\n')
        f.write(f'#$ -l disk={maxdisk}G\n')
        f.write('module add gaussian\n')
        f.write('export GAUSS_SCRDIR=$TMPDIR\n')
        f.write(f'{args.gver} {args.input}\n')
        f.write('rm *.sh.* core* \n') # cleanup
        
def main():
    args = initialize().parse_args()
    mem, nprocshared = parse_gjf_file(args.input)
    make_sge_script(args, vmem=mem, nproc=nprocshared, maxdisk=5)
if __name__ == "__main__":
    main()
