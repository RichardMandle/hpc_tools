# hpc_tools
Python and Bash scripts for high performance computing workflows on ARC3/4 and AIRE at the University of Leeds

## plt_csv.py
Simple plotter of csv data using python. Arguments:<br>-i - input .csv file.<br>-t - title for plot.<br>-x - x-label for plot, if not in header of .csv.<br>-y - y-label for plot, if not in header of csv.<br><br>
<br><br>Example:<br>
```python $HOME/py_files/plt_csv.py -i P1.csv```<br>
![image](https://github.com/user-attachments/assets/42b89ad7-7bbb-4aa8-8ec8-4aef8224e24f)

## plt_xvg.py
Simple plotter of gromacs .xvg data using python. Will read header data from xvg for labels etc. Arguments:<br>-i - input .xvg file.<br>-t - title for plot.<br>-x - x-label for plot, if not in header of .xvg.<br>-y - y-label for plot, if not in header of xvg.<br><br>
Example:<br>
```gmx energy```
```18 19 20 0```
```python $HOME/py_files/plt_xvg.py -i energy.xvg```
![image](https://github.com/user-attachments/assets/564a72f1-157c-47b4-959e-513b30f6de45)

## OP.py
Calculation of order parameters using MDtraj. Arguments:<br>-traj trajectory file (e.g. .trr, .xtc).<br>-top - topology file (e.g. .gro).

## P1.py
Calculation of <P1> dipole order paramter using Gromacs/Numpy; saves data as .csv. Arguments:<br>-s Gromacs portable run file (.tpr).<br>-b - frame to begin from.<br>-e - frame to end on.

## Ps.py
Calculate the spontaneous polarisation of an MD simulation using Gromacs/Numpy; saves data as .csv. Arguments:<br>-s Gromacs portable run file (.tpr).<br>-b - frame to begin from.<br>-e - frame to end on.

# Gromacs Workflow Tools
## setup.sh
A bash script for simulation setup and scheduling equilibration (4 steps; 1000, 100, 10 and 1 kj E tolerence), NVE equilibration, NVT equilibration, (optional) electric field poling, production MD simulation. It expects you to have generated your initial configuration using acpype (https://github.com/alanwilter/acpype) and will use the *_GMX.gro file as the initial configuration, the *_GMX.top file as the basis of the topoloy file, and the *_GMX.itp file as the force field. The script _will submit jobs to the SLURM queue_ unless you pass the ```-s``` flag. <br><br>

A few optional arguments:<br>
        -n = number of mols to insert into initigal configuration<br>
        -b = initial box size (too small and they won't all fit)<br>
        -t = number of tries when filling box<br>
        -k = production MD run temperature (in K)<br>
        -v = flag for GROMACS version; normally will just load the "default" on your HPC via "module load"<br>
        -e = flag to enable field-based simulation - if enabled will apply a big electric field to "pole" the simulation between the NVT equilibration and production MD simulation (i.e. polar order)<br>
        -s = flag to only prepare simulation but not submit jobs - if called, will just write inputs.<br>
        
Example:<br>
First, put the output of acpype in your current directory. Then:<br>
```bash $HOME/gromacs_sh_files/setup.sh -n 2000 -b 20 -t 50 -e -k 400```<br>
This sets up a simulation of 2000 molecules in an initial box of 20 nm^3 with up to 50 tries. An electric field is applied (-e). The temperature to be used is 400k. 

Notes:<br>
You can edit the .mdp files for additional control over the simulations. By default, we are using anisotropic pressure coupling with a V-rescale thermostat. We offload as much of the computation to L40 GPUs as possible. 

## t_sweep_setup.sh
Takes a equilibrated .gro file and builds identical production MD simulations with different temperatures in a range given by -tmax and -tmin and -tstep.

# DFT / Electronic Structure Tools
### ORCA
## gau2orca.py
Make a working orca .inp file from a gaussian .gjf file. Works OK for simple things (tested with opt, freq, goat). You can specify a few things:<br>
        -i = input file (.gjf)
        -o = output file (.inp)
        -n = name of job file to use (defaults to same as gjf, or, if not present, "ORCA JOB")
        -m = method (uses gaussain one by default, removing things that wont work, but you can pass anything you like (e.g. "goat gf2n-xtb", "opt freq am1" etc)
        -b = pass a custom block; e.g. you might do -b "%DOCKER GUEST \"dioxane.xyz\" end" to run a docker calculation, or -b "%tddft, NRoots 50, maxdim 20, tda true, end" to do a TD calculation
        -cpu = number of cpu cores to use (note this means ORCA will want the full path to the binary I think, so probably wont work as you intend)
        -mem = ammount of ram, specify units (e.g. -mem 4GB not -mem 4)
        -all = do all files in a directory (if -i is a directory, like ./gaussian_inputs or something)
        -sge = write a sge submission script (if you want SLURM you can use orca2slurm.py, below)

Example usage:
``` python gau2orca.py -i myfile.gjf -o my_orca_file.inp -cpu 1 -mem 2GB -m "opt freq gfn2-xtb" ```
``` python gau2orca.py -i dioxane.gjf -o dioxpes.inp -n diox_pes -m "gfn2-xtb neb-ts freq" -b "%neb neb_end_xyzfile \"dioxane_ax_trans\" end" -cpu 4 -mem 4 ```

## xyz2orca
Take an xyz file(s) and create apropriate input files for ORCA (*.inp):<br>
        -i = input file (.xyz)
        -o = output file (.inp)
        -n = name of job file to use (defaults to same as xyz, or, if not present, "ORCA JOB")
        -m = method to use (defaults to "GF2N-xTB")
        -b = pass a custom block; e.g. you might do -b "%DOCKER GUEST \"dioxane.xyz\" end" to run a docker calculation, or -b "%tddft, NRoots 50, maxdim 20, tda true, end" to do a TD calculation
        -cpu = number of cpu cores to use (defaults to 4)
        -mem = ammount of ram, specify units(dfaults to 4GB)
        -all = do all files in a directory (if -i is a directory, like ./gaussian_inputs or something)

Example usage:
``` python xyz2orca.py -i my_coords.xy -o my_coords.inp -cpu 2 -mem 2GB -m "OPT PM3" ```
``` python xyz2orca.py -all -i coords/ -cpu 4 -mem 4GB -m "OPT FREQ r2SCAN-3C TightOpt TightSCF FREQ"```

## goat2orca
Take the output of a GOAT calculation in ORCA and extract the individual geometries to new xyz files based on specified energy cutoffs:<br>
        -x = input file (.xyz) - final ensemble .xyz 
        -o = output file (.out) - GOAT output file
        -e = energy threshold to use (kcal mol)
        -w = write filtered xyz files to this path (folder)

Example usage:
``` python goat2orca -o diox.out -x diox.finalensemble.xyz -e 4 -w confs ```
        
## orca2slurm.py
Inspect an orca .inp file and construct an appropriate .sh file for submission of the job to the slurm queue. Just pass the file name:<br>
``` python orca2slurm.py my_orca_file.inp ```<br>
And it returns a .slurm file that you can submit to the job queue.

### orca_td_spectra.py
Plot a absorbtion spectrum from a TD calculation by putting a lineshape over each oscilator with the specified fwhm and height equal to strength. Pass the file name (e.g. my_file.out) and the following flags:<br>
        -fwhm = FWHM in eV for lineshape broadening
        -shape = choose the lineshape to use in peak synthesis (gaussian of lorentzian)
        -xunit = units of x-axis, either eV or wavelength (nm)
        -xlim = the limits of the x-axis
        -pltosc = if called, plot the individual oscilators as a bar on the spectrum
        -save = save the plot as an image file of some sort.

Example usage:<br>
``` python orca_td_spectrum.py my_output_file.out -fwhm 20 -xunit eV -pltosc ```
        
### Gaussian
## gjf2sge.py
Make a SGE job submission file (.sh) from a Gaussian input file. Can work with single files or multiple (task arrays). Reads job dependency and requests apropriate resource from the HPC queue. Arguments:<br>-i input.gjf file.<br>-t input - creates a task array .sh file for all .gjf files named "input"; e.g. "input_1.gjf, input_2.gjf, ... input_n.gjf". Note, task array creation hasn't been thoroughly tested.

## gjf2slurm.py
Make a SLURM job submission file (.sh) from a Gaussian input script. Arguments:<br>-i input.gjf file.

## tdscf_screen.py
Reads a Gaussian .log file (given by -```-i```) and creates an array of follow-on jobs designed to explore different combinations of functional, basis set, dispersion correction, solvation, no. of states for the TD job etc. Initially performs OPT at the stated level, followed by a single point TD-SCF calculation. Arguments:<br><br>
```-cpu```: Number of CPU cores to use.<br>
```-mem```: Ammount of memory to use (in GB).<br>
```-f```: Functional to use (pass a list; defaults to B3LYP PBE).<br>
```-b```: Basis set to use (pass a list; defaults to "6-31G(d)", "cc-pVDZ", "aug-cc-pVDZ", "cc-pVTZ").<br>
```-ed```: Toggles GD3BJ empirical dispersion on/off (default = off).<br>
```-sol```: Toggles solvation on/off (default = off).<br>
```--solvation_model```: Pass a list of solvation models to use (default = "scrf=(scipcm,solvent=methanol)").<br>
```-ns```: Number of states for the TD-SCF job (default = 10).<br>
```-o```: Output base filename for the generated .gjf files. If not provided, it'll default to that of the input file + ```-array```.<br>
```--remove_existing```: Will remove existing .gjf files with the same name as the output (default = on).<br>
<br>
Can be used with gjf2sge.py in task array mode to quickly set up jobs. For example:

```python tdscf_screen.py -i my_optimised_geometry.log -f "b3LYP" "B97D3" "B97D3" -sol -o "test_job" -cpu 8 -mem 8```<br>
Creates 24x jobs using the 3x functionals, the 4x default basis sets, both with and without solvation.<br><br>
Using gjf2sge.py we can quickly create a SGE wrapper for the jobsubmission:<br>
```python gjf2sge.py -t test_job```

## log_to_gjf.py 
Reads a Gaussian.log file and produces a new .gjf file with the final geometry in the .log file, i.e. a new job. Arguments:<br><br>
```-i```: the .log file to work on (e.g. "myfile.log").<br>
```-cpu```: Number of CPU cores to use (default = 4).<br>
```-mem```: Ammount of memory to use (in GB; default = 4).<br>
```-f```: Functional to use (defaults to B3LYP).<br>
```-b```: Basis set to use (defaults to cc-pVDZ).<br>
```-ed```: Toggles GD3BJ empirical dispersion on/off (default = off).<br>
```-chk```: Toggles saving the checkpoint file (default = off). <br>
```-o```: Output base filename for the generated .gjf files. If not provided, it'll default to that of the input file + ```-new```.<br>
```-r```: Allows passing a new Gaussian route (defaults to a blank route wit hthe combination of ```-f``` and ```-b```, i.e. a single point.) For example, you might do ```-r "OPT FREQ``` for an OPT+FREQ job.<br>
```--remove_existing```: Will remove existing .gjf files with the same name as the output (default = on).<br>
## pygauss
A python module with a lot of tools for interacting with Gaussian output and plotting/viewing spectra (https://github.com/RichardMandle/pygauss)
