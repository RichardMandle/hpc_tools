#!/bin/bash
#SBATCH --job-name=gromacs_setup_step3
#SBATCH --time=00:05:00
#SBATCH --cpus-per-task=1
#SBATCH --mail-type=BEGIN,END,FAIL
#SBATCH --output=gromacs_setup_step3-%j.out
#SBATCH --error=gromacs_setup_step3-%j.err

module unload gromacs
module load gromacs/2024.4/gcc-13.2.0_cuda-12.6.2

gmx grompp -f $HOME/gromacs_mdp/energymin_10.mdp -c confout.gro -p topology.top -o testbox -maxwarn 10