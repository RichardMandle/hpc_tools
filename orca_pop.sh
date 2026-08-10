#!/usr/bin/env bash

# simple bash script for evaluating a load of orca .out files (e.g. conformers) 
# and printing the lowest energy one (filename) to the terminal
# gives some idea of population too just to hammer home the point

T=298.15
R=0.008314462618    # kJ mol^-1 K^-1
HARTREE_TO_KJ=2625.499639

tmp=$(mktemp)



# read the energy values for each file we find
while IFS= read -r f; do

    E=$(grep "FINAL SINGLE POINT ENERGY" "$f" | tail -1 | awk '{print $5}')

    if [[ -n "$E" ]]; then
        printf "%s\t%s\n" "$f" "$E" >> "$tmp"
    fi

done < <(find . -name "orca.out" -type f)

if [[ ! -s "$tmp" ]]; then
    echo "No ORCA energies found."
    rm "$tmp"
    exit 1
fi

#find the lowest energy
Emin=$(awk 'NR==1 {min=$2} $2<min {min=$2} END {print min}' "$tmp")

printf "%-35s %20s %12s %12s\n" \
       "File" "Energy / Eh" "dE / kJ mol-1" "Population / %"
printf "%s\n" "--------------------------------------------------------------------------------------"

awk -v Emin="$Emin" \
    -v conv="$HARTREE_TO_KJ" \
    -v R="$R" \
    -v T="$T" '
{
    dE = ($2 - Emin) * conv
    w = exp(-dE / (R*T))

    file[NR] = $1
    energy[NR] = $2
    de[NR] = dE
    weight[NR] = w
    total += w
}
END {
    for (i=1; i<=NR; i++) {
        pop = 100 * weight[i] / total
        printf "%-35s %20.10f %12.3f %12.2f\n",
               file[i], energy[i], de[i], pop
    }
}' "$tmp" | sort -k3,3n

rm "$tmp"
