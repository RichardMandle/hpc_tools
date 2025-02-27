#!/bin/bash
# a script for simplifying the MD simulation setup with gromacs


shopt -s extglob

# Default GROMACS version
gmx_version="gromacs"
setup_only=false  # Default to false, meaning jobs will be submitted
electric_field=false  # Default to false, meaning electric field jobs are NOT submitted

while getopts n:b:t:k:v:es flag
do
    case "${flag}" in
        n) nmols=${OPTARG};;        # number of mols to shove in that box
        b) box=${OPTARG};;          # initial box size
        t) try=${OPTARG};;          # number of tries when filling box
        k) K=${OPTARG};;            # production MD run temperature (in K)
        v) gmx_version=${OPTARG};;  # flag for GROMACS version
        e) electric_field=true;;    # flag to enable field-based simulation
        s) setup_only=true;;        # flag to only prepare simulation but not submit jobs
    esac
done

echo "Using GROMACS version: $gmx_version"
echo "Inserting $nmols molecules..."

module load $gmx_version # Load the specified GROMACS version

sed -i "s/ref-t =.*/ref-t =          $K/" $HOME/gromacs_mdp/MD1.mdp      # Update temperature in the MDP file
sed -i "s/ref-t =.*/ref-t =          $K/" $HOME/gromacs_mdp/efield.mdp   # Update temperature in the e-field MDP file

gmx insert-molecules -ci *_GMX.gro -nmol $nmols -rot xyz -box $box $box $box -o simubox -try $try # Insert molecules into the simulation box

sed "s/ 1/ ${nmols}/g" *GMX.top > topology.top # Update the topology file with the correct number of molecules

loc=${PWD##*/} # Generate a unique job prefix based on the current directory name

# If setup-only mode is enabled, exit before job submission
if [ "$setup_only" = true ]; then
    echo "Setup complete. No jobs submitted (setup-only mode)."
    exit 0
fi

echo "Setup complete. Submitting jobs..."

# Submit jobs for energy minimization and equilibration. EM1, EM2 and so on increase the tollerance.
jid1=$(sbatch --job-name="${loc}GROMPP1" $HOME/gromacs_grompp/GROMPP1.sh | awk '{print $4}')
jid2=$(sbatch --job-name="${loc}EM1" --dependency=afterok:$jid1 $HOME/gromacs_sh_files/CPU.sh | awk '{print $4}')


jid3=$(sbatch --job-name="${loc}GROMPP2" --dependency=afterok:$jid2 $HOME/gromacs_grompp/GROMPP2.sh | awk '{print $4}')
jid4=$(sbatch --job-name="${loc}EM2" --dependency=afterok:$jid3 $HOME/gromacs_sh_files/CPU.sh | awk '{print $4}')

jid5=$(sbatch --job-name="${loc}GROMPP3" --dependency=afterok:$jid4 $HOME/gromacs_grompp/GROMPP3.sh | awk '{print $4}')
jid6=$(sbatch --job-name="${loc}EM3" --dependency=afterok:$jid5 $HOME/gromacs_sh_files/CPU.sh | awk '{print $4}')

jid7=$(sbatch --job-name="${loc}GROMPP4" --dependency=afterok:$jid6 $HOME/gromacs_grompp/GROMPP4.sh | awk '{print $4}')
jid8=$(sbatch --job-name="${loc}EM4" --dependency=afterok:$jid7 $HOME/gromacs_sh_files/CPU.sh | awk '{print $4}')

# Submit jobs for production run on GPU
jid9=$(sbatch --job-name="${loc}GROMPP5" --dependency=afterok:$jid8 $HOME/gromacs_grompp/GROMPP5.sh | awk '{print $4}')
jid10=$(sbatch --job-name="${loc}EQ1" --dependency=afterok:$jid9 $HOME/gromacs_sh_files/GPU_update.sh | awk '{print $4}')
jid11=$(sbatch --job-name="${loc}GROMPP6" --dependency=afterok:$jid10 $HOME/gromacs_grompp/GROMPP6.sh | awk '{print $4}')
jid12=$(sbatch --job-name="${loc}EQ2" --dependency=afterok:$jid11 $HOME/gromacs_sh_files/GPU_update.sh | awk '{print $4}')

# Conditionally submit electric field jobs
if [ "$electric_field" = true ]; then
    jid13=$(sbatch --job-name="${loc}GROMPPefield" --dependency=afterok:$jid12 $HOME/gromacs_grompp/GROMPPefield.sh | awk '{print $4}')
    jid14=$(sbatch --job-name="${loc}Efield" --dependency=afterok:$jid13 $HOME/gromacs_sh_files/GPU_update.sh | awk '{print $4}')
    final_dependency=$jid14  # Ensure MD waits for E-field job completion
else
    final_dependency=$jid12  # No E-field, so MD starts after EQ2
fi

# Submit jobs for production MD run on GPU, depending on whether E-field is enabled
jid15=$(sbatch --job-name="${loc}GROMPP7" --dependency=afterok:$final_dependency $HOME/gromacs_grompp/GROMPP7.sh | awk '{print $4}')
jid16=$(sbatch --job-name="${loc}MD1" --dependency=afterok:$jid15 $HOME/gromacs_sh_files/GPU_update.sh | awk '{print $4}')

# Clean up unnecessary files
rm -f *AC.frcmod *AC.inpcrd *AC.lib *AC.prmtop *CHARMM.inp *CHARMM.prm *CHARMM.rtf *CNS.inp *CNS.par *CNS.top *.pkl
