#!/bin/bash
#SBATCH --job-name=gromacs_setup_field
#SBATCH --time=00:05:00
#SBATCH --cpus-per-task=1
#SBATCH --mail-type=BEGIN,END,FAIL
#SBATCH --output=gromacs_setup_field-%j.out
#SBATCH --error=gromacs_setup_field-%j.err

module unload gromacs
module load gromacs/2024.4/gcc-13.2.0_cuda-12.6.2

gmx grompp -f $HOME/gromacs_mdp/efield.mdp -c confout.gro -p topology.top -t state.cpt -o testbox -maxwarn 10