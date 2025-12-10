import argparse
import re
import os

def parse_goat_out(filepath, energy_cutoff=3.0):
    conformers = []

    with open(filepath, 'r') as f:
        lines = f.readlines()
        for i, line in enumerate(lines):
            if "# Final ensemble info #" in line:
                start_idx = i + 4  # skip next 3 lines
                break
        else:
            print("Could not find conformer table in file.")
            return []

        for line in lines[start_idx:]:
            parts = line.strip().split()
            if len(parts) == 5:
                try:
                    idx = int(parts[0])
                    energy = float(parts[1])
                    degeneracy = int(parts[2])
                    percent_total = float(parts[3])
                    percent_cumulative = float(parts[4])

                    conformers.append({
                        'index': idx,
                        'energy': energy,
                        'degeneracy': degeneracy,
                        'percent_total': percent_total,
                        'percent_cumulative': percent_cumulative
                    })
                except ValueError:
                    break  # end on malformed line
            else:
                break  # end on non data line

    print(f"\nParsed {len(conformers)} conformers from: {filepath}")
    print(f"Conformers within {energy_cutoff} kcal/mol of global minimum:\n")
    for c in conformers:
        if c['energy'] <= energy_cutoff:
            print(f"  #{c['index']:2d}: {c['energy']:6.3f} kcal/mol   "
                  f"(deg: {c['degeneracy']}  pop: {c['percent_total']:5.2f}%)")

    return conformers

def read_xyz_blocks(xyz_path):
    with open(xyz_path, 'r') as f:
        lines = f.readlines()

    blocks = []
    i = 0
    while i < len(lines):
        try:
            n_atoms = int(lines[i].strip())
        except ValueError:
            print(f"Invalid atom count at line {i}")
            break

        block = lines[i:i + n_atoms + 2]
        if len(block) < n_atoms + 2:
            print(f"Incomplete block at {i}")
            break
        blocks.append(block)
        i += n_atoms + 2

    return blocks


def write_xyz_blocks(blocks, output_dir, prefix="conf"):
    """
    write the conformers to INDIVIDUAL xyz files
    """
    os.makedirs(output_dir, exist_ok=True)
    for i, block in enumerate(blocks):
        filename = os.path.join(output_dir, f"{prefix}_{i:03d}.xyz")
        with open(filename, 'w') as f:
            f.writelines(block)
    print(f"Written {len(blocks)} individual .xyz files to: {output_dir}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Select low-energy conformers from GOAT output and .xyz file.")
    parser.add_argument('-o', '--out', required=True, help='GOAT .out file')
    parser.add_argument('-x', '--xyz', required=True, help='GOAT conformer ensemble .xyz file')
    parser.add_argument('-e', '--energy', type=float, default=3.0,
                        help='Energy cutoff in kcal/mol (default: 3.0)')
    parser.add_argument('-w', '--write', help='Write filtered .xyz files into this directory')

    args = parser.parse_args()


    all_conformers = parse_goat_out(args.out, args.energy)
    total_confs = len(all_conformers)

    if total_confs == 0:
        print("No conformers were parsed from the GOAT output.")
        exit(1)

    total_pop = sum(c['percent_total'] for c in all_conformers)

    conformers = [c for c in all_conformers if c['energy'] <= args.energy]
    n_selected = len(conformers)

    if n_selected == 0:
        print(f"\nNo conformers below {args.energy} kcal/mol.")
        exit(1)
  
    # new bit - lets print some statistics, what % of the conformers we captured ( and how many we had )
    selected_pop = sum(c['percent_total'] for c in conformers)
    selected_pop_norm = 100.0 * selected_pop / total_pop if total_pop > 0 else 0.0

    blocks = read_xyz_blocks(args.xyz)
    selected_blocks = [blocks[c['index']] for c in conformers]

    print(f"\nFound {n_selected} conformers below {args.energy} kcal/mol:\n")
    for c in conformers:
        print(f"  #{c['index']:2d}: {c['energy']:6.3f} kcal/mol   "
              f"(pop: {c['percent_total']:5.2f}%)")

    print(f"\nSummary:")
    print(f"  - Count below cutoff: {n_selected}/{total_confs}")
    print(f"  - Ensemble population below cutoff: {selected_pop:5.2f}% ")
    print(f"  - Energy cutoff used: {args.energy:.3f} kcal/mol\n")

    if args.write:
        write_xyz_blocks(selected_blocks, args.write)
