#!/bin/bash
#SBATCH --job-name=gromacs_md
#SBATCH --time=48:00:00
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mail-type=BEGIN,END,FAIL
#SBATCH --mail-user=$USER
#SBATCH --output=gromacs_md-%j.out
#SBATCH --error=gromacs_md-%j.err

module unload gromacs
module load gromacs/2024.4/gcc-13.2.0_cuda-12.6.2

gmx mdrun -s *.tpr -ntmpi 1 -ntomp $SLURM_CPUS_PER_TASK -bonded gpu -nb gpu -pme gpu -cpi state -c confout_MD -nsteps 1000000000
