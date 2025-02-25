# hpc_tools
Python and Bash scripts for high performance computing workflows on ARC3/4 and AIRE at the University of Leeds

#plt_csv.py
Simple plotter of csv data using python. Arguments:<br>-i - input .csv file.<br>-t - title for plot.<br>-x - x-label for plot, if not in header of .csv.<br>-y - y-label for plot, if not in header of csv.<br><br>

#plt_xvg.py
Simple plotter of gromacs .xvg data using python. Will read header data from xvg for labels etc. Arguments:<br>-i - input .xvg file.<br>-t - title for plot.<br>-x - x-label for plot, if not in header of .xvg.<br>-y - y-label for plot, if not in header of xvg.<br><br>

# OP.py
Calculation of order parameters using MDtraj.

# P1.py
Calculation of <P1> dipole order paramter using Gromacs/Numpy; saves data as .csv

#Ps.py
Calculate the spontaneous polarisation of an MD simulation using Gromacs/Numpy; saves data as .csv

#gjf2sge.py
Make a SGE job submission file (.sh) from a Gaussian input script

#gjf2slurm.py
Make a SLURM job submission file (.sh) from a Gaussian input script
