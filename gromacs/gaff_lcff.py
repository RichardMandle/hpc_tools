import argparse
import re
import shutil
from pathlib import Path
from datetime import datetime

'''
Update a RESP/Antechamber/Acpype-derived *_GMX.itp file with sigma/epsilon values and/or torsional parameters from
GAFF-LCFF according to Boyd & Wilson, PCCP 2015.

ref 1 10.1039/C7CP07496D
ref 2 10.1039/C5CP03702F

This script supports:
 - Updating [ atomtypes ] LJ parameters
 - Updating [ dihedrals ] proper torsions by matching atom indices to atomtypes
 - Converting matching dihedrals to RB format (func=3) with C0..C5 coefficients
 - Inserting a comment line noting the update under the ACPYPE header

Usage:
    python gaff_lcff.py [-a] [-d] [--backoff] [-q] infile.itp [outfile.itp]

By default, both sections are updated, backup is created, and updated lines printed.
Use -a/--atoms to update only atomtypes; -d/--dihedrals for only dihedrals;
--backoff to disable backup; -q/--quiet to suppress printing updates.
'''

# atom parmeters
ATOMTYPE_PARAMS = {
    'o':  (0.295992, 0.478608),
    'ca': (0.339967, 0.289824),
    'os': (0.300001, 0.611280),
    'nd': (0.325000, 0.411280),
    'cc': (0.369967, 0.429824),
    'c3': (0.353600, 0.287020),
    'hc': (0.245310, 0.091730),
}
# dihedrals in RB style
DIHEDRAL_PARAMS = {
    ('ca','ca','c','os'):  ( 7.335350,  0.000000, -7.335350,  0.000000, 0.000000, 0.000000),
    ('ca','ca','os','c'):  ( 6.000000,  0.000000,  0.000000,  0.000000,-6.000000, 0.000000),
    ('c3','c3','c3','c3'): ( 0.565680,  1.697030,  0.000000, -2.262710, 0.000000, 0.000000),
    ('ca','os','c3','c3'): (11.531200,  0.000000,-11.531200,  0.000000, 0.000000, 0.000000),
}

# note, dihedral entries are duplicated in reverse order to catch reverse matches like ('ca','ca','c','os') vs ('os', 'c', 'ca','ca')....
# for newer torsions we probably need some smarter logic. But for now, this is OK

for key, coeffs in list(DIHEDRAL_PARAMS.items()):
    rev = key[::-1]
    if rev not in DIHEDRAL_PARAMS:
        DIHEDRAL_PARAMS[rev] = coeffs

# small functions

def build_atomtype_regex():
    pat = r'(?:' + '|'.join(re.escape(n) for n in ATOMTYPE_PARAMS) + r')\b'
    return re.compile(rf'^\s*(?P<name>{pat})\b')

# map atom index -> atom type from [ atoms ] block

def parse_atomtypes(lines):
    atom_map = {}
    in_block = False
    for L in lines:
        low = L.strip().lower()
        if low.startswith('['):
            in_block = '[ atoms ]' in low
            continue
        if in_block:
            if not L.strip():  # empty line ends block
                break
            if L.strip().startswith(';'):  # skip comments
                continue
            cols = L.split()
            atom_map[int(cols[0])] = cols[1]
    return atom_map

# update LJ sigma/epsilon in [ atomtypes ]
def update_atomtypes(lines):
    rex = build_atomtype_regex()
    out = []
    in_block = False
    for L in lines:
        low = L.strip().lower()
        if low.startswith('['):
            in_block = '[ atomtypes ]' in low
            out.append(L)
            continue
        if in_block and L.strip() and not L.strip().startswith(';'):
            m = rex.match(L)
            if m:
                name = m.group('name')
                sigma, eps = ATOMTYPE_PARAMS[name]
                parts = L.split()
                parts[-2] = f"{sigma:.6f}"
                parts[-1] = f"{eps:.6f}"
                out.append('    ' + '   '.join(parts) + '\n')
                continue
        out.append(L)
    return out

# update dihedral lines in [ dihedrals ] using atom_map

def update_dihedrals(lines, quiet=False):
    atom_map = parse_atomtypes(lines)
    out = []
    in_block = False
    for L in lines:
        low = L.strip().lower()
        if low.startswith('['):
            in_block = '[ dihedrals ]' in low
            out.append(L)
            continue
        if in_block and L.strip() and not L.strip().startswith(';'):
            # split code and comment
            if ';' in L:
                code, comment = L.split(';', 1)
                comment = ';' + comment.rstrip('\n')
            else:
                code = L.rstrip('\n')
                comment = ''
            tokens = code.strip().split()
            if len(tokens) >= 4 and tokens[0].isdigit():
                i, j, k, l = map(int, tokens[:4])
                atypes = (atom_map.get(i), atom_map.get(j), atom_map.get(k), atom_map.get(l))
                if None not in atypes and atypes in DIHEDRAL_PARAMS:
                    old_line = L.rstrip('\n')
                    coeffs = DIHEDRAL_PARAMS[atypes]
                    new_tokens = [str(i), str(j), str(k), str(l), '3'] + [f"{c:.6f}" for c in coeffs]
                    new_code = '    ' + '     '.join(new_tokens)
                    new_line = new_code + ('     ' + comment if comment else '') + '\n'
                    if not quiet:
                        print(f"Updating dihedral at {i},{j},{k},{l} -> {atypes}:")
                        print("  Before:", old_line)
                        print("  After: ", new_line.rstrip())
                    out.append(new_line)
                    continue
        out.append(L)
    return out

# insert comment under ACPYPE header

def insert_header_comment(lines):
    for idx, L in enumerate(lines):
        if L.startswith(';') and 'created by acpype' in L.lower():
            comment = f"; Updated by gaff_lcff.py on {datetime.now().isoformat()}\n"
            lines.insert(idx + 1, comment)
            break
    return lines

# main loop

def main():
    p = argparse.ArgumentParser(description='Patch GROMACS .itp with GAFF-LCFF params')
    p.add_argument('infile', help='input .itp')
    p.add_argument('outfile', nargs='?', help='output .itp (defaults to infile)')
    grp = p.add_argument_group('options')
    grp.add_argument('-a', '--atoms', action='store_true', help='only atomtypes')
    grp.add_argument('-d', '--dihedrals', action='store_true', help='only dihedrals')
    p.add_argument('--backoff', action='store_true', help='no backup')
    p.add_argument('-q', '--quiet', action='store_true', help='suppress prints')
    args = p.parse_args()

    infile = Path(args.infile)
    outfile = Path(args.outfile) if args.outfile else infile
    if not args.backoff and infile.exists():
        bak = infile.with_suffix(infile.suffix + '.bak')
        shutil.copy(infile, bak)
        print(f"Backup created: {bak}")

    lines = infile.read_text().splitlines(keepends=True)
    lines = insert_header_comment(lines)
    do_atoms = args.atoms or not args.dihedrals
    do_dihedrals = args.dihedrals or not args.atoms
    if do_atoms:
        lines = update_atomtypes(lines)
    if do_dihedrals:
        lines = update_dihedrals(lines, quiet=args.quiet)
    outfile.write_text(''.join(lines))
    print(f"Wrote patched file to {outfile}: atoms={do_atoms}, dihedrals={do_dihedrals}, backup={'off' if args.backoff else 'on'}")

if __name__ == '__main__':
    main()
