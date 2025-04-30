#!/bin/bash
# ==============================================================================
# setup.sh - GROMACS simulation setup script
#
# this script builds and submits a sequence of GROMACS simulation jobs:
# - energu minimizations
# - equilibration  (NVT and then NPT)
# - (Optional) electric field biasing
# - the actual production MD
#
# USAGE EXAMPLES:
#
# 1. simulation starting from molecule insertion:
#    bash setup.sh -n 400 -b 8 -t 100 -k 400 -v gromacs/2024.4
#
# 2. setup molecules and topology only, without submitting any jobs (-s flag):
#    bash setup.sh -n 400 -b 8 -t 100 -k 400 -v gromacs/2024.4 -s
#
# 3. resume from equilibration stage only (skip energy minimization... need to test this):
#    bash setup.sh -f eq
#
# 4. continue with electric field biasing stage (after equilibrations... need to test this):
#    bash setup.sh -f ef -e
#
# 5. Resume from production MD stage only (no e-field or equilibration... need to test this):
#    bash setup.sh -f md
#
# FLAG OPTIONS:
#
# -n   number of molecules to insert
# -b   box size (nm)
# -t   number of insertion attempts 
# -k   simulation temperature (K)
# -v   GROMACS module version (default: "gromacs"; make sure you have a GPU version)
# -e   enable electric field bias
# -s   setup only (no job submission)
# -f   start from stage: em (minimization), eq (equilibration), ef (efield), md (production MD)
#
# Author - Dr. R. Mandle, UoL, 2024/5
# ==============================================================================

# --- code begins --- #
shopt -s extglob

# define our default settings
gmx_version="gromacs"
setup_only=false
electric_field=false
start_from="em"

while getopts n:b:t:k:v:esf: flag
do
    case "${flag}" in
        n) nmols=${OPTARG};;
        b) box=${OPTARG};;
        t) try=${OPTARG};;
        k) K=${OPTARG};;
        v) gmx_version=${OPTARG};;
        e) electric_field=true;;
        s) setup_only=true;;
        f) start_from=${OPTARG};;  # from which stage? em, eq, ef, md?
    esac
done

# this will pass a useful list of commands if the user does setup.sh -h or setup.sh --help etc.
if [[ "$1" == "-h" || "$1" == "--help" ]]; then
    cat <<EOF
setup.sh - Automate GROMACS simulation job setup and submission

Usage:
  bash setup.sh [options]

Options:
  -n   Number of molecules
  -b   Box size (nm)
  -t   Number of insertion tries
  -k   Target temperature (K)
  -v   GROMACS version (default "gromacs")
  -e   Enable electric field biasing
  -s   Setup only, do not submit jobs
  -f   Stage to start from: em, eq, ef, md
  -h, --help  Show this help message

Examples:
  bash setup.sh -n 400 -b 8 -t 100 -k 400 -v gromacs/2024.4
  bash setup.sh -f eq
  bash setup.sh -f md

EOF
    exit 0
fi

echo "Using GROMACS version: $gmx_version"
echo "Starting from stage: $start_from"

module unload gromacs
module load $gmx_version

# this code aims to submit jobs safely and will cause the whole chain to fail if anything is wrong
submit_job() {
    local script=$1
    jid=$(sbatch "$script" | awk '{print $4}')
    if [ -z "$jid" ]; then
        echo "Error: sbatch submission failed for $script"
        exit 1
    fi
    echo "Submitted $script with JobID $jid"
}

# we'll generate GROMPP steps on the fly rather than having 7 or 8 seperate .sh files for each GROMPP stage
generate_and_submit_grompp() {
    local mdpfile=$1
    local jobname=$2
    local grofile=$3
    local topfile=$4
    local cptfile=$5
    local output=$6
    local depend=${7:-}  # optional dependency

    local temp_script=$(mktemp grompp_job_${jobname}_XXXXXX.sh)

    echo "#!/bin/bash
#SBATCH --job-name=${jobname}
#SBATCH --time=00:05:00
#SBATCH --cpus-per-task=1
#SBATCH --mail-type=BEGIN,END,FAIL
#SBATCH --output=${jobname}-%j.out
#SBATCH --error=${jobname}-%j.err
${depend:+#SBATCH --dependency=afterok:${depend}}

module unload gromacs
module load ${gmx_version}

set -e

gmx grompp -f ${mdpfile} -c ${grofile} -p ${topfile} ${cptfile:+-t $cptfile} -o ${output} -maxwarn 10
" > "$temp_script"

    chmod +x "$temp_script"

    submit_job "$temp_script"
    rm -f "$temp_script"
}

loc=${PWD##*/}

# if we are starting from "em" then we'll also prepare the system.
# here we need to have the *_GMX.gro, *_GMX.top and *_GMX.itp files from acpype.
# if you want GAFF-LCFF, run the gaff_lcff.py script BEFORE setup.sh!
if [[ "$start_from" == "em" ]]; then
    echo "Setting up molecules and topology..."

    gmx insert-molecules -ci *_GMX.gro -nmol "$nmols" -rot xyz -box "$box" "$box" "$box" -o simubox -try "$try"

    # build topology.top from the acpype GMX topology
    sed "s/ 1/ ${nmols}/g" *GMX.top > topology.top
fi

if [ "$setup_only" = true ]; then
    echo "Setup complete. No jobs submitted (setup-only mode)."
    exit 0
fi

# update the target temperatures in MDPs
sed -i "s/ref-t =.*/ref-t =          $K/" $HOME/gromacs_mdp/MD1.mdp
sed -i "s/ref-t =.*/ref-t =          $K/" $HOME/gromacs_mdp/efield.mdp

echo "Submitting jobs..."

prev_jid=""

# --- this section is the energy minimisation jobs --- #
if [[ "$start_from" == "em" ]]; then
    # EM1 - GROMPP then CPU
    generate_and_submit_grompp "$HOME/gromacs_mdp/energymin_1000.mdp" "${loc}_GROMPP1" "simubox.gro" "topology.top" "" "testbox" "$prev_jid"
    prev_jid=$jid
    prev_jid=$(sbatch --dependency=afterok:$prev_jid $HOME/gromacs_sh_files/CPU.sh | awk '{print $4}')

    # EM2 - GROMPP then CPU
    generate_and_submit_grompp "$HOME/gromacs_mdp/energymin_100.mdp" "${loc}_GROMPP2" "confout.gro" "topology.top" "" "testbox" "$prev_jid"
    prev_jid=$jid
    prev_jid=$(sbatch --dependency=afterok:$prev_jid $HOME/gromacs_sh_files/CPU.sh | awk '{print $4}')

    # EM3 - GROMPP then CPU
    generate_and_submit_grompp "$HOME/gromacs_mdp/energymin_10.mdp" "${loc}_GROMPP3" "confout.gro" "topology.top" "" "testbox" "$prev_jid"
    prev_jid=$jid
    prev_jid=$(sbatch --dependency=afterok:$prev_jid $HOME/gromacs_sh_files/CPU.sh | awk '{print $4}')

    # EM4 - GROMPP then CPU
    generate_and_submit_grompp "$HOME/gromacs_mdp/energymin_1.mdp" "${loc}_GROMPP4" "confout.gro" "topology.top" "" "testbox" "$prev_jid"
    prev_jid=$jid
    prev_jid=$(sbatch --dependency=afterok:$prev_jid $HOME/gromacs_sh_files/CPU.sh | awk '{print $4}')
fi

# --- this section is equilibration (NVT then NPT) --- #
if [[ "$start_from" == "em" || "$start_from" == "eq" ]]; then
    generate_and_submit_grompp "$HOME/gromacs_mdp/equil_nvt.mdp" "${loc}_GROMPP5" "confout.gro" "topology.top" "" "testbox" "$prev_jid"
    prev_jid=$jid
    prev_jid=$(sbatch --dependency=afterok:$prev_jid $HOME/gromacs_sh_files/GPU_update.sh | awk '{print $4}')

    generate_and_submit_grompp "$HOME/gromacs_mdp/equil_npt.mdp" "${loc}_GROMPP6" "confout.gro" "topology.top" "state.cpt" "testbox" "$prev_jid"
    prev_jid=$jid
    prev_jid=$(sbatch --dependency=afterok:$prev_jid $HOME/gromacs_sh_files/GPU_update.sh | awk '{print $4}')
fi

# --- this is the electric field part; only triggers if $electric_field = true! --- #
if [[ "$start_from" == "em" || "$start_from" == "eq" || "$start_from" == "ef" ]]; then
    if [ "$electric_field" = true ]; then
        generate_and_submit_grompp "$HOME/gromacs_mdp/efield.mdp" "${loc}_GROMPPefield" "confout.gro" "topology.top" "state.cpt" "testbox" "$prev_jid"
        prev_jid=$jid
        prev_jid=$(sbatch --dependency=afterok:$prev_jid $HOME/gromacs_sh_files/GPU_update.sh | awk '{print $4}')
    fi
fi

# --- finally, the bit we are here for; production MD simulation --- #
if [[ "$start_from" == "em" || "$start_from" == "eq" || "$start_from" == "ef" || "$start_from" == "md" ]]; then
    generate_and_submit_grompp "$HOME/gromacs_mdp/MD1.mdp" "${loc}_GROMPP7" "confout.gro" "topology.top" "state.cpt" "testbox" "$prev_jid"
    prev_jid=$jid
    prev_jid=$(sbatch --dependency=afterok:$prev_jid $HOME/gromacs_sh_files/GPU_update.sh | awk '{print $4}')
fi

echo "All requested jobs submitted successfully."
