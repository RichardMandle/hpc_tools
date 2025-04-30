#!/bin/bash
# ==============================================================================
# temperature_sweep.sh
# this aims to setup a series of simulations in a temperature sweep
# by modifying the root $HOME/gromacs_mdp/MD1.mdp, generating the required .tpr files,
# and submitting jobs using our fine-tuned GPU_update.sh script.
# ==============================================================================

# this will pass a useful list of commands if the user does setup.sh -h or setup.sh --help etc.
if [[ "$1" == "-h" || "$1" == "--help" ]]; then
    cat <<EOF
t_sweep_setup.sh - take an equilibrated .gro file and setup identical simulations with varying temperature

Usage:
  bash setup.sh [options]

Options:
  -tmin   Minimum temperature of sweep in K (default = 300)
  -tmax   Maximum temperature of sweep in K (default = 550)
  -tstep  Step size between temperatures (in K, defualt = 25)
  -v      GROMACS version (default "gromacs")
  -gro    Gromacs.gro file of configuration (defualt = confout.gro)
  -top    Gromacs topology file (default = topology.top)
  -cpt    specify checkpoint file (e.g. state.cpt) to read in velocities

example:
  bash t_sweep_setup.sh (uses all defaults)
  bash t_sweep_setup.sh -gro polar.gro -top polar.top -tmin 313 -tmax 413 -tstep 20


EOF
# default parameters
tmin=300
tmax=550
tstep=25
gmx_version="gromacs"
grofile="confout.gro"
topfile="topology.top"
cptfile="state.cpt"

while [[ "$#" -gt 0 ]]; do
    case "$1" in
        -tmin) tmin="$2"; shift 2;;
        -tmax) tmax="$2"; shift 2;;
        -tstep) tstep="$2"; shift 2;;
        -v) gmx_version="$2"; shift 2;;
        -gro) grofile="$2"; shift 2;;   # specify which .gro file
        -top) topfile="$2"; shift 2;;   # specify which .top file
        -cpt) cptfile="$2"; shift 2;;   # specify checkpoint file
        *) echo "Unknown parameter passed: $1"; exit 1;;
    esac
done

echo "Running temperature sweep from $tmin K to $tmax K in steps of $tstep K"
echo "Using GROMACS version: $gmx_version"
echo "Using structure file: $grofile"
echo "Using topology file: $topfile"
echo "Using checkpoint file: $cptfile"

module load $gmx_version

# sanity checks
if [ ! -f "$HOME/gromacs_mdp/MD1.mdp" ]; then
    echo "Error: Cannot find $HOME/gromacs_mdp/MD1.mdp"
    exit 1
fi

if [ ! -f "$grofile" ]; then
    echo "Error: Structure file '$grofile' not found!"
    exit 1
fi

if [ ! -f "$topfile" ]; then
    echo "Error: Topology file '$topfile' not found!"
    exit 1
fi

if [ ! -f "$cptfile" ]; then
    echo "Warning: Checkpoint file '$cptfile' not found! Proceeding without checkpoint."
    use_cpt=false
else
    use_cpt=true
fi

# copy MD1 to somewhere local for modification
cp "$HOME/gromacs_mdp/MD1.mdp" MD1_temp.mdp

# main loop for temperature sweeping
for (( temp=$tmin; temp<=$tmax; temp+=$tstep ))
do
    dir="T_${temp}"
    mkdir -p "$dir"

    echo "Preparing TPR for T = $temp K"

    sed -i "s/ref-t =.*/ref-t =          $temp/" MD1_temp.mdp

    if [ "$use_cpt" = true ]; then
        gmx grompp -f MD1_temp.mdp -c "$grofile" -p "$topfile" -t "$cptfile" -o "${dir}/topol" -maxwarn 10
    else
        gmx grompp -f MD1_temp.mdp -c "$grofile" -p "$topfile" -o "${dir}/topol" -maxwarn 10
    fi

    # make sure that grompp successfully built the .tpr file
    if [ $? -ne 0 ]; then
        echo "Error: grompp failed for T = $temp K. Skipping."
        continue
    fi

    sbatch --job-name="T${temp}" --chdir="$PWD/$dir" "$HOME/gromacs_sh_files/GPU_update.sh"

    echo "Submitted T = $temp K"
done

# clean up the temp .mdp file
rm -f MD1_temp.mdp

echo "Temperature sweep submission complete."
