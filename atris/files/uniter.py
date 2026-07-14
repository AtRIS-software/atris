import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.colors import LogNorm
pd.set_option('display.max_rows', 1000)

def process_log(filename):
    # We need to extract from the GDML file the inner radious of each detector, and we also need to know the mass of the detector.
    # Format is :  SDIDr: $SDID, mass/kg, surface/cm2, volume/cm3, density g/cm3
    sdid_data         = []
    numberofdetectors = 0 
    for aLine in open(filename+'.log','r'):
        if aLine[:30] == "### AtRIS: proceeding to load ":
            nrphantoms = int(aLine[30:-13])
            print("This run included %i phantoms"%nrphantoms)
        if aLine[:6] == "SDIDr:":
            theLine = aLine[6:-1] # We remove the 'SDIDr:' from the start and the last newline character
            theLine = np.fromstring(theLine, sep=',')
            sdid_data.append(theLine)
            numberofdetectors += 1
    df = pd.DataFrame(sdid_data,columns=['sdid','mass/kg','tot_surface/cm2','volume/cm3','density/g/cm3'])
    df['inn_surface/cm2'] = 0 # inner surface
    df['out_surface/cm2'] = 0 # outer surface
    df.set_index(['sdid'],inplace=True)
    df.sort_index(inplace=True)
    df.index = df.index.map(int)
    df.loc[0,'out_surface/cm2'] = df.loc[0,'tot_surface/cm2']
    # from SDID=0, we do not have spheres with surface pi4r2, so we need to correct
    for anSDID in range(1,numberofdetectors):
        df.loc[anSDID,'out_surface/cm2'] = df.loc[anSDID]['tot_surface/cm2'] - df.loc[anSDID-1]['out_surface/cm2']
    df['inn_surface/cm2'] = df['tot_surface/cm2'] - df['out_surface/cm2']
    df['inn_surface/cm2'][0] = df['out_surface/cm2'][0] # overwrite the inner surface of the core to avoid division by zero
    return df, numberofdetectors, nrphantoms

def get_nr_energy_bins(simname):
    data = np.loadtxt(simname+'.bins')
    nrbins = data.shape[0]
    print ("This simulation had %i energy bins"%nrbins)
    return nrbins, data

def process_phantoms():
    phantoms   = pd.read_csv('phantoms.txt',sep=',',index_col=2,skiprows=2,names=['mass/g','crosssurface/cm2'])
    nrphantoms = phantoms.shape[0]
    print("we have %i phantoms in this run"%nrphantoms)
    return phantoms

def read_data(simname,nphant):
    # This read the histograms:
    #   - h1_h1.1.     : which contains information about the kinetic energy of the vertex particles.
    #   - h2_h2.dir    : which contains information about the direction of the vertex particles
    #   - h2_h2.pos    : which contains information about the position of the vertex particles
    #   - h2_h2.ion    : which contains information about the atmospheric ionization 
    #   - h2_h2.dosX   : which contains information about the atmospheric absorbed dose
    #   - h2_h2.equiX  : which contains information about the atmospheric dose equivalent
    #   - h2_h2.ratesX : which contains information about the atmospheric count rates
    names = ["_h1_h1.1","_h2_h2.dir","_h2_h2.pos","_h2_h2.ion"]
    for a_phantom_nr in range(nphant):
        names.append("_h2_h2.dos"+str(a_phantom_nr))
        names.append("_h2_h2.equi"+str(a_phantom_nr))
        names.append("_h2_h2.rates"+str(a_phantom_nr))
    sim_data = []
    counter  = 0 
    for a_name in names:
        a_name      = simname + a_name+".csv"
        if counter == 0: data = np.loadtxt(a_name,delimiter=',',skiprows=7)  # this discriminates between 1D and 2D
        else:            data = np.loadtxt(a_name,delimiter=',',skiprows=10)
        sim_data.append(data)
        print('loaded data from %s with shape:'%a_name, data.shape)
        names[counter] = a_name # replacing partial name with full name
        counter   += 1
    return sim_data,names

def scale_data(data,nphat,ndet,nenbins,phantom_data,df):
    # Here we scale the data
    # Scaling is not done for the first 3 histograms
    nrparticles   = data[0][:,0]
    nrparticles   = nrparticles[1:-1] # remove under, overflow bins
    print(nrparticles)
    limit         = 1+nphat*3
    shapex        = ndet + 2
    shapey        = nenbins + 1
    print("Now we will reshape the %i histograms with %i entries."%(limit,shapex*shapey))
    for hist_index in range(3,3+limit):
        new_data         = data[hist_index][:,1].reshape((shapex,shapey))
        new_data         = new_data[1:-1,1:-1]
        data[hist_index] = new_data / nrparticles[None,:]
        if hist_index == 3:
            # This is the ionization, we need to divide by mass
            #print("we scale the ionization histogram by dividing with the SDID volume")
            data[hist_index] = data[hist_index] / df['volume/cm3'][:,None]
        if hist_index > 3:
            #print("we scale other histograms with the surface factor")
            phantom_nr       = int((hist_index-4)/3)
            phantom_surface  = phantom_data['crosssurface/cm2'][phantom_nr]
            if ((hist_index-4)%3) != 2:
                # for dose and equi, we divide by phantom mass, to get per g
                #print("We also scale the dos/equi histograms by dividing with the phantom mass")
                phantom_surface  = phantom_surface / phantom_data['mass/g'][phantom_nr]
            data[hist_index] = data[hist_index]*phantom_surface/df['inn_surface/cm2'][:,None]
            pass
    return(data)

def make_allplots(data,xbins,df,simname,nphant):
    # The plots are only for doing a quick visual inspection
    ybins           = (df["inn_surface/cm2"] / (4.*np.pi))**0.5 / 100000.
    ybins           = ybins - ybins[2]
    fig, allaxes    = plt.subplots(ncols=4,figsize=(16,5*nphant),nrows=nphant,sharey=True)
    for phantom_index in range(nphant):
        counter         = 0
        axes            = allaxes[phantom_index]
        ax0,ax1,ax2,ax3 = axes
        axes            = [ax0,ax1,ax2,ax3]
        print("ploting phantom %i plots complete"%phantom_index)
        for data_idx in [3,4+phantom_index*3,4+phantom_index*3+1,4+phantom_index*3+2]:
            thedata  = data[data_idx]
            print('plotting data has shape',thedata.shape)
            vmin     = np.min(thedata[thedata>0])
            vmax     = np.max(thedata)
            ax       = axes[counter]
            ax.pcolormesh(xbins,ybins,thedata,norm=LogNorm(vmin=vmin,vmax=vmax))
            counter += 1
            ax.set_xscale('log')
            ax.set_ylim(0,ybins.values[-2])
    plt.tight_layout()
    plt.savefig(simname+".pdf")

def make_output(data,df,simname,nphant):
    # calculate altitude in km from inner surface
    altitude        = (df["inn_surface/cm2"] / (4.*np.pi))**0.5 / 100000.
    altitude        = altitude - altitude[2]
    altitude        = altitude.values
    altitude        = altitude[1:-1,None]
    # obtain SDID:
    SDID            = df.index.values
    SDID            = SDID[1:-1,None]
    # We need to remove the first and the last row
    extensions      = ['.dose','.equi','.rates']
    npformat        = ['%.5e']*(data[3].shape[1])
    npformat        = ['%8.3f'] + npformat 
    npformat        = ['%5i'] + npformat 
    for hist_index in range(3,3+1+nphant*3):
        if hist_index == 3: 
            ext     = '.ioni'
        else:
            ext     = extensions[(hist_index-4)%3] + str(int((hist_index-4)/3)) 
        outputfname = simname +ext
        histdata    = data[hist_index][1:-1,:]
        outdata     = np.hstack((SDID, altitude, histdata))
        print("Saving histogram %i under the name %s. Data shape is:"%(hist_index,outputfname),outdata.shape)
        # Encoding here is extremely important for the werkzeug
        np.savetxt(outputfname,outdata,fmt=npformat,delimiter=' ',encoding='utf-8')

def process_run(simname):
    df, ndet, nphant      = process_log(simname)
    nenbins,enbins        = get_nr_energy_bins(simname)
    phantom_data          = process_phantoms()
    data, filenames       = read_data(simname,nphant)
    scaled_data           = scale_data(data,nphant,ndet,nenbins,phantom_data,df)
    #make_allplots(scaled_data,enbins,df,simname,nphant)
    make_output(scaled_data,df,simname,nphant)


if __name__ == "__main__":
    """
    The new AtRIS variant implements multithreading, however, this came at a cost of reduced custom output capabiltiy. Previously
    AtRIS provided custom files corresponding to the ionization, absorbed dose, dose equivalent and rate response matrices. Now,
    AtRIS only provides the internal histograms as .csv files, in which we find a single line per histogram entry. For futher
    processing, we must convert these files into the old formats. 
    """
    print("This script creates the custom atris .ioni,.dose,.equi,.rate files that correspond to the various response matrices.")
    print("It is ment to be started within the simulation directory, where the data can be found.")
    print("In addition, the user must provided the 'phantoms.txt' file, speficying the phantom mass and cross surface.")
    print("For scaling, the script will open the gdml file and retrieve the DIID surface area and also the mass of each volume.")
    process_run("protons")
    process_run("alphas")



