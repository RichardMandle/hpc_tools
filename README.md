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


# Gaussian Tools
## gjf2sge.py
Make a SGE job submission file (.sh) from a Gaussian input script. Arguments:<br>-i input.gjf file.

## gjf2slurm.py
Make a SLURM job submission file (.sh) from a Gaussian input script. Arguments:<br>-i input.gjf file.

## pygauss
A python module with a lot of tools for interacting with Gaussian output and plotting/viewing spectra (https://github.com/RichardMandle/pygauss)
