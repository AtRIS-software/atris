import requests
import pandas as pd
import io
import numpy as np
import os
import re
import requests
import datetime
import hashlib
import json
import shlex
import atrismacrogen as amg
import subprocess
import atristoolset as ia
from IPython.display import clear_output
import time
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
import warnings
warnings.filterwarnings('ignore')
#pd.set_option('display.max_rows', 1000)

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
    #df.loc[1,'out_surface/cm2'] = df.loc[0,'tot_surface/cm2']
    # from SDID=0, we do not have spheres with surface pi4r2, so we need to correct
    for anSDID in range(1,numberofdetectors):
        #print(anSDID, df.loc[anSDID]['tot_surface/cm2'], df.loc[anSDID-1]['out_surface/cm2'],df.loc[anSDID]['tot_surface/cm2']- df.loc[anSDID-1]['out_surface/cm2'])
        df.loc[anSDID,'out_surface/cm2'] = df.loc[anSDID]['tot_surface/cm2'] - df.loc[anSDID-1]['out_surface/cm2']
    df['inn_surface/cm2'] = df['tot_surface/cm2'] - df['out_surface/cm2']
    df['inn_surface/cm2'][0] = df['out_surface/cm2'][0] # overwrite the inner surface of the core to avoid division by zero
    df.sort_values('inn_surface/cm2',inplace=True) # sort fix
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
        #print('loaded data from %s with shape:'%a_name, data.shape)
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
    #print("Now we will reshape the %i histograms with %i entries."%(limit,shapex*shapey))
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
        #print("ploting phantom %i plots complete"%phantom_index)
        for data_idx in [3,4+phantom_index*3,4+phantom_index*3+1,4+phantom_index*3+2]:
            thedata  = data[data_idx]
            #print('plotting data has shape',thedata.shape)
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
        #print("Saving histogram %i under the name %s. Data shape is:"%(hist_index,outputfname),outdata.shape)
        # Encoding here is extremely important for the werkzeug
        np.savetxt(outputfname,outdata,fmt=npformat,delimiter=' ',encoding='utf-8')

def process_run(simname):
    df, ndet, nphant      = process_log(simname)
    nenbins,enbins        = get_nr_energy_bins(simname)
    phantom_data          = process_phantoms()
    print('Processing phantoms')
    data, filenames       = read_data(simname,nphant)
    print("Reading data complete.")
    scaled_data           = scale_data(data,nphant,ndet,nenbins,phantom_data,df)
    #make_allplots(scaled_data,enbins,df,simname,nphant)
    print("Making output files.")
    make_output(scaled_data,df,simname,nphant)
    print('Response files have been created.')
    


def unite(rootdir,phi):
    os.chdir(rootdir+'atris/simulation/')
    process_run("protons")
    process_run("alphas")
    print("Postprocesing is now complete. You can load the data with the Werkzeug.")
    print("Read the readme in this repository to learn how to start the Werkzeug.")
    print("If done properly, Werkzeug should be available under http://localhost:9123/")
    print("we recommend the use of the 20mm randramona phantom with index 24 and")
    print("the 25mm randramona phantom with index 31. Make sure to unselect the CMakeFiles folder when uploading.")
    print("Geomagnetic cutoff rigidity can be calculated e.g. with https://tools.izmiran.ru/cutoff/")
    print("The solar recommended solar modulation parameter has been calculated in cell nr %.1f MV"%phi)
          





phi_url = 'https://cosmicrays.oulu.fi/phi/Phi_mon_2017.txt'


# We load "nist.exist", which holds information about which materials already
# exist in the Geant4 material database. This information is useful when 
# creating sheet materials. 
try:
    f      = open('./atris/interface/nist.exist','r')
except:
    f      = open('../../atris/interface/nist.exist','r')

nistdb = f.readline()
# Appending own materials. Here, I should add all the project-related molecules
nistdb = nistdb[:-1]+",'G4_VACUUM']"
f.close()


headers = {
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'de-DE,de;q=0.9,hr-BA;q=0.8,hr;q=0.7,da-DK;q=0.6,da;q=0.5,en-US;q=0.4,en;q=0.3',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive',
    # Already added when you pass json=
    # 'Content-Type': 'application/json',
    'DNT': '1',
    'Origin': 'https://kauai.ccmc.gsfc.nasa.gov',
    'Pragma': 'no-cache',
    'Referer': 'https://kauai.ccmc.gsfc.nasa.gov/instantrun/msis',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-origin',
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 Safari/537.36',
    'sec-ch-ua': '"Chromium";v="104", " Not A;Brand";v="99", "Google Chrome";v="104"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"macOS"',
}

NRLMSIS_API_URL = 'https://kauai.ccmc.gsfc.nasa.gov/instantrun/api/nrlmsis'
NRLMSIS_MAX_ROWS = 150


def _to_utc_datetime_string(year, month, day, hour):
    hour_int = int(hour)
    minute_float = (hour - hour_int) * 60.0
    minute_int = int(minute_float)
    second = int(round((minute_float - minute_int) * 60.0))
    dt = datetime.datetime(year, month, day, hour_int, minute_int, 0, tzinfo=datetime.timezone.utc)
    dt += datetime.timedelta(seconds=second)
    return dt.isoformat().replace("+00:00", "Z")


def _nrlmsis_payload(year, month, day, hour, longitude, latitude, hmin, hmax, deltah):
    version = os.environ.get("NRLMSIS_VERSION", "NRLMSIS2")
    return {
        "version": version,
        "timeType": "ut",
        "coordinateType": "geo",
        "datetime": _to_utc_datetime_string(year, month, day, hour),
        "lat": float(latitude),
        "lon": float(longitude),
        "height": max(float(hmax), 100.0),
        "profileType": 1,
        "start": float(hmin),
        "stop": float(hmax),
        "step": float(deltah),
        "fdaily": -1,
        "f3month": -1,
        "ap": -1,
    }


def _nrlmsis_cache_path(payload):
    cache_key = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    cache_dir = os.path.join(os.getcwd(), ".nrlmsis-cache")
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, cache_key + ".txt")


def _round_altitude(value):
    return round(float(value), 10)


def _expected_nrlmsis_rows(start, stop, step):
    return int(round((float(stop) - float(start)) / float(step))) + 1


def _nrlmsis_chunk_ranges(hmin, hmax, deltah):
    if float(deltah) <= 0.0:
        raise ValueError("deltah must be positive")
    expected_rows = _expected_nrlmsis_rows(hmin, hmax, deltah)
    if expected_rows <= NRLMSIS_MAX_ROWS:
        return [(_round_altitude(hmin), _round_altitude(hmax))]

    chunk_span = float(deltah) * float(NRLMSIS_MAX_ROWS - 1)
    ranges = []
    start = float(hmin)
    while start <= float(hmax) + 1e-9:
        stop = min(float(hmax), start + chunk_span)
        ranges.append((_round_altitude(start), _round_altitude(stop)))
        start = stop + float(deltah)
    return ranges


def _fetch_nrlmsis_output(payload):
    api_headers = {
        "User-Agent": headers["User-Agent"],
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Origin": "https://kauai.ccmc.gsfc.nasa.gov",
        "Referer": "https://kauai.ccmc.gsfc.nasa.gov/instantrun/nrlmsis/",
    }
    response = requests.post(NRLMSIS_API_URL, headers=api_headers, data=json.dumps(payload), timeout=120)
    try:
        response_data = response.json()
    except ValueError as exc:
        raise RuntimeError("CCMC NRLMSIS API returned a non-JSON response.") from exc
    if not response.ok:
        message = response_data.get("error") or response_data.get("message") or response.text
        raise RuntimeError("CCMC NRLMSIS API request failed: %s" % message)
    txt_url = response_data.get("txt")
    if not txt_url:
        raise RuntimeError("CCMC NRLMSIS API response did not include an output URL.")
    txt_response = requests.get(txt_url, headers={"User-Agent": headers["User-Agent"]}, timeout=120)
    txt_response.raise_for_status()
    return txt_response.text


def _load_nrlmsis_content(payload):
    cache_path = _nrlmsis_cache_path(payload)
    if os.path.exists(cache_path):
        print('Using cached NRLMSIS response from', cache_path)
        with open(cache_path, 'r', encoding='utf-8') as cache_file:
            return cache_file.read()

    content = _fetch_nrlmsis_output(payload)
    with open(cache_path, 'w', encoding='utf-8') as cache_file:
        cache_file.write(content)
    print('Cached NRLMSIS response to', cache_path)
    return content


def _parse_nrlmsis_output(content):
    return pd.read_csv(io.StringIO(content), sep=r'\s+', engine='python', skiprows=1, header=None)

def get_atmosphere(year, month, day, hour, longitutde, latitude, hmin=0,hmax=100,deltah=1):
    chunk_ranges = _nrlmsis_chunk_ranges(hmin, hmax, deltah)
    print('we will request an atmosphere from nasa using the new nrlmsise model using the following parameters:')
    print({
        "version": os.environ.get("NRLMSIS_VERSION", "NRLMSIS2"),
        "timeType": "ut",
        "coordinateType": "geo",
        "datetime": _to_utc_datetime_string(year, month, day, hour),
        "lat": float(latitude),
        "lon": float(longitutde),
        "height": max(float(hmax), 100.0),
        "profileType": 1,
        "start": float(hmin),
        "stop": float(hmax),
        "step": float(deltah),
        "fdaily": -1,
        "f3month": -1,
        "ap": -1,
    })
    if len(chunk_ranges) > 1:
        print('Splitting NRLMSIS request into %i chunks to stay under the CCMC row limit.' % len(chunk_ranges))

    frames = []
    for chunk_start, chunk_stop in chunk_ranges:
        payload = _nrlmsis_payload(year, month, day, hour, longitutde, latitude, chunk_start, chunk_stop, deltah)
        print('Requesting chunk %.3f km -> %.3f km' % (chunk_start, chunk_stop))
        content = _load_nrlmsis_content(payload)
        data_frame = _parse_nrlmsis_output(content)
        expected_rows = _expected_nrlmsis_rows(chunk_start, chunk_stop, deltah)
        if data_frame.shape[0] != expected_rows:
            raise RuntimeError(
                'CCMC NRLMSIS response row count mismatch for chunk %.3f..%.3f km: expected %i rows, got %i'
                % (chunk_start, chunk_stop, expected_rows, data_frame.shape[0])
            )
        frames.append(data_frame)

    merged = pd.concat(frames, ignore_index=True)
    merged.drop_duplicates(subset=5, keep='first', inplace=True)
    merged.sort_values(by=5, inplace=True)
    merged.reset_index(drop=True, inplace=True)
    expected_total_rows = _expected_nrlmsis_rows(hmin, hmax, deltah)
    if merged.shape[0] != expected_total_rows:
        raise RuntimeError(
            'Merged CCMC NRLMSIS response row count mismatch: expected %i rows, got %i'
            % (expected_total_rows, merged.shape[0])
        )
    return merged

def nrlm_reformer(nrlm20data):
    # to use the psf2gdml converter with the new nrlm model, we need to create a file format that fits the previous format
    # Needed format:
    # 0 : altitiude in km
    # 1 : O1 density in per cm3
    # 2 : N2 density in per cm3
    # 3 : O2 density in per cm3
    # 4 : air density in g per cm3
    # 5 : neutral temperature in K
    # 6 : He density in per cm3
    # 7 : Ar density in per cm3
    # 8 : H  density in per cm3
    # 9 : N1 density in per cm3
    if nrlm20data.shape[1] >= 28:
        modern_idx = [5,8,9,10,12,13,15,16,17,18] # NRLMSIS 2.1 includes nitric oxide ahead of density and temperature
    else:
        modern_idx = [5,8,9,10,11,12,14,15,16,17] # NRLMSIS 2.0 / NRLMSIS-00
    newdata    = nrlm20data.values[:,modern_idx]
    return newdata
    
def nrml2psf(data):
    alt  = data[:,0]
    temp = data[:,5]
    rho  = data[:,4]
    nN2  = data[:,2] + 0.5 * data[:,9] # molecular + atomic
    nO2  = data[:,3] + 0.5 * data[:,1] # molecular + atomic
    nHe  = data[:,6]
    nAr  = data[:,7]
    nH   = data[:,8]

    #Prepare output array
    nrSheets    = data.shape[0]           #one line per sheet
    output      = np.zeros((nrSheets,16)) #Array of zeros
    earthRadius = 6371000               #in meters
    thickness   = (data[1:,0]-data[:-1,0]) #uniform sheet thickness
    thickness  *= 1000                  #convert to meters
    thickness   = np.append(thickness,thickness[-1])
    botAltitudes= earthRadius + alt*1000
    topAltitudes= botAltitudes + thickness

    #Fill out the pressures
    kb   = 1.38064852e-23 #m^2kgs^-2K^-1 - 
    pO2  = nO2 * kb * 1000000 * temp#convert to Pascals
    pN2  = nN2 * kb * 1000000 * temp#convert to Pascals
    pAr  = nAr * kb * 1000000 * temp#convert to Pascals
    pHe  = nHe * kb * 1000000 * temp#convert to Pascals
    pH   = nH  * kb * 1000000 * temp#convert to Pascals
    pTotal    = pO2+ pN2 + pAr + pHe + pH

    #Here are the molecular weights
    wO2  = 2*15.9994   
    wN2  = 2*14.0067   
    wAr  = 39.948      
    wHe  = 4.0026
    wH   = 1.008 
    u         = 1.66054e-24 #atomic mass unit in g
    mO2  = nO2*wO2*u #mass of oxygen in 1 cm3
    mN2  = nN2*wN2*u 
    mAr  = nAr*wAr*u 
    mHe  = nHe*wHe*u
    mH   = nH*wH*u
    total = mO2+mN2+mAr+mHe+mH
    mfO2 = mO2/total
    mfN2 = mN2/total
    mfAr = mAr/total
    mfHe = mHe/total
    mfH   = mH/total
    #for l in range(nrSheets):
    #    print "%10e ::: %.10f :: %.10f :: %.10f ::::: %.10f :: %.10f :: %.10f"%(nOxygen[l], mfOxygen[l],mfNitrogen[l],mfArgon[l],total[l], density[l],total[l]/ density[l])

    # we now fill out the output file
    output[::,0]  = botAltitudes / 1000.
    output[::,1]  = topAltitudes / 1000.
    output[::,2]  = 0 #dummy
    output[::,3] += 2*np.pi #unit is pi!
    output[::,4]  = 0 #dummy
    output[::,5] += 1*np.pi #unit is pi!
    output[::,6]  = np.arange(2,nrSheets+2)
    output[::,7]  = temp
    output[::,8]  = rho
    output[::,9]  = pTotal
    output[::,10]  = 0 #dummy
    output[::,11] = mfN2
    output[::,12] = mfO2
    output[::,13] = mfAr
    output[::,14] = mfHe
    output[::,15] = mfH
    
    print("COMPLETE: writing out the psf lines.")
    formatstring = "%e %e %e %e %e %e %i %e %e %e %e %e %e %e %e %e"
    #formatstring = "%i %i %.2f %.2f %.2f %.2f %i %.1f %e %e %.5f %.5f %.5f %.5f %.5f %.5f"
    np.savetxt("simulation.psf",output,fmt=formatstring)
    # we now read the saved file an add the header, the core, crust and loss
    # volumes. 
    f      = open("simulation.psf","r")
    ff     = f.readlines()
    f.close()

    cr = 20/1000. #thickness in kilometers
    er = earthRadius/1000.
    top= (topAltitudes[-1]+1)/1000.
    t  = 293.15 #temperature in Kelvins
    p  = 101325 #pressure in Pascals
    d  = 2.7    #density in g/cm3
    f  = open("simulation.psf","w")
    f.write("#O478Si284Al84Fe52Ca37Na28Mg15 N O Ar He H\n") # Adding the header file
    f.write(formatstring%(0,er-cr,0,2*np.pi,0,1*np.pi,0,t,d,p,1.0,0,0,0,0,0))
    f.write("\n")
    f.write(formatstring%(er-cr,er,0,2*np.pi,0,1*np.pi,1,t,d,p,1.0,0,0,0,0,0))
    f.write("\n")
    for k in ff: f.write(k)
    f.write(formatstring%(top,top+cr,0,2*np.pi,0,1*np.pi,nrSheets+2,t,d,p,1.0,0,0,0,0,0))
    f.write("\n")
    f.close()
    
def parse_header(filename):
    thefile = open(filename,'r')
    header = thefile.readline()
    thefile.close()
    header     = header.split()
    nrformulas = len(header)
    
    #Generate the header gdml text
    coremat  = parse_solid(header[0])
    
    #generate template dictionary for other sheets
    template   = {}
    idx = 0
    for material in header[1:]:
        template.update({material:{"mass fraction":0, "material":material, "colidx":idx}})
        idx += 1
    return coremat, template


def gdml_material(mat, name, temperature, density, pressure,state="solid"):
    """
    # units for T, rho, P are K, g/ccm, Pa
    This function is specially tailored for the solid materials, which are
    to be used for the core and the crust, but it can be also used to make
    gaseous materials. 
    """
    header = '\t<material name="%s" state="%s">\n'%(name,state)
    footer = '\t</material>\n'
    output = ""
    output += header
    output += '\t\t<D value="%e" unit="g/cm3" />\n'%density
    output += '\t\t<T value="%e" unit="K" />\n'%temperature
    output += '\t\t<P value="%e" unit="Pa" />\n'%pressure
    for key in mat:
        frac, name = mat[key]["mass fraction"],mat[key]["material"]
        if frac != 0.:
            current = '\t\t<fraction n="%e" ref="G4_%s" />\n'%(frac,name)
            output += current
    output += footer
    return output


def gdml_compile(materials, world, geometry, structure, filename):
    finalfile = ""
    header = '<?xml version="1.0" encoding="UTF-8" standalone="no" ?>\n<gdml xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://service-spi.web.cern.ch/service-spi/app/releases/GDML/schema/gdml.xsd">\n\n\n\n'
    footer = '\n<setup name="Exoplanet" version="1.0">\n\t<world ref="World"/>\n</setup>\n</gdml>'
    finalfile += header
    
    #now the <define> part
    #here we need to modify the offset of the world box. 
    define = '<define>\n\t<constant name="PI" value="1.*pi"/>\n\t<constant name="TWOPI" value="2.*pi"/>\n\t<position name="center"/>\n\t<rotation name="identity"/>\n</define>\n'
    finalfile += define
    
    #Now the materials
    finalfile += "<materials>\n"
    #We also add the AtRIS material extensions
    f = open("../interface/atris.materials","r")
    ff = f.readlines()
    for fff in ff:
        finalfile += fff
    f.close()
    for mat in materials:
        finalfile += mat
    finalfile += "</materials>\n"
    #Now the geometry
    finalfile += "<solids>\n"
    #add the world
    wd         = world * 2
    add        = '\t<box name="WorldBox" x="%f" y="%f" z="%f" lunit="km"/>\n'%(wd,wd,wd)
    finalfile += add
    
    for vol in geometry:
        finalfile += vol
    finalfile += "</solids>\n"
    
    #now the structure
    finalfile += "<structure>\n"
    for st in structure:
        add = '\t<volume name="%s">\n\t\t<materialref ref="%s"/>\n\t\t<solidref ref="%s"/>\n\t\t<auxiliary auxtype="SensDet" auxvalue="%i"/>\n\t</volume>\n'%tuple(st)
        finalfile += add
    #now we need to add the world and place all the other volumes
    worldpart = '\t<volume name="World">\n\t\t<materialref ref="Vacuum"/>\n\t\t<solidref ref="WorldBox"/>\n'
    finalfile += worldpart
    for st in structure:
        vv = st[0]
        add = '\t\t<physvol>\n\t\t\t<volumeref ref="%s"/>\n\t\t\t<positionref ref="center"/>\n\t\t</physvol>\n'%vv
        finalfile += add
    finalfile += "\t</volume>\n"
    finalfile += "</structure>\n"
    #Now the footer
    finalfile += footer
    f = open(filename,"w")
    f.write(finalfile)
    f.close()

def parse_solid(formula):
    """
    parse_solid is ment to deal with the first element in the header.
    In the PSF format spec, we have described in detail the representation
    of the header. To summarize, the first element is a series of chemical
    elements followed by their mass fraction in per milles. For example,
    O762C111H101N26 corresponds to:
        : 762 parts oxygen
        : 111 parts carbon
        : 101 parts hydrogen
        :  26 parts nitrogen
        ====================
        :1000 parts
    Notes:
        - Sum of per milles should add up to 1000
        - Order according to decreasing abundance
        - This is only for the header! The GDML material will be designated
          as a "solid"
        - The macroscopic properties of the core elemnts still have to be 
          provided in the first line of the PSF file. 
    """
    # convert formula using regular expressions in to a list of tuples
    first = re.findall(r'([A-Z][a-z]*)(\d*)', formula)
    for k in first:
        element = k[0]
    if element not in nistdb: 
        print("element not found in the nist database. ABORTING!!")
        return 0
    g4mat, totalmass = {}, 0.
    for k in first:
        material    = k[0]
        massfrac    = float(k[1]) / 1000.
        g4mat.update({material:{"mass fraction":massfrac, "material":material}})
        totalmass   += massfrac        
    if np.abs(totalmass - 1.0) >0.0001:
        print("\ttotal mass is not equal to 1!!\n\t\t\tformula: %s\n\t\t\ttotalmas: %.10f. Rescaling."%(formula,totalmass))
        new_g4mat = {}
        new_totalmass = 0.
        factor = 1.0/totalmass
        for k in first:
            material    = k[0]
            massfrac    = float(k[1]) / 1000. * factor
            new_g4mat.update({material:{"mass fraction":massfrac, "material":material}})
            new_totalmass   += massfrac        
        if np.abs(new_totalmass - 1.0) >0.0001:
            print("\ttotal mass is AGAIN not equal to 1!! formula: %s totalmas: %.10f. Serious problem encuntered."%(formula,new_totalmass))
        else:
            print("\ttotal mass is now fine. Problem solved.")
        return new_g4mat
    return g4mat

def line_processor(filename):
    core,template = parse_header(filename)
    columnnames   = {"rmin":0,"rmax":1,"phimin":2,"phimax":3,"thetamin":4,
                     "thetamax":5,"SDID":6,"temperature":7,"density":8,"pressure":9,"core":10}
    #print "template:", template
    for mat in template:
        idx  = template[mat]["colidx"] + 11
        name = template[mat]["material"]
        columnnames.update({name:idx})
    # now we generate the gdml material blocks
    data          = np.loadtxt(filename)
    nrsheets      = data.shape[0]
    assert data.shape[1] == len(columnnames), "data shape and columnnames missmatch: (%ix%i) vs %i"%(data.shape[0],data.shape[1],len(columnnames))
    
    #We generate the materials and geometry entries
    materials, geometry, struct = [], [], []
    for aLine in data:
        custom = aLine[columnnames["core"]] == 1.0
        sdid = int(aLine[columnnames["SDID"]])
        name = "material" + str(sdid)
        temp = aLine[columnnames["temperature"]]
        dens = aLine[columnnames["density"]]
        pres = aLine[columnnames["pressure"]]
        if custom:
            gdmlmater = gdml_material(core, name, temp, dens, pres,"solid")
            materials.append(gdmlmater)
        else: 
            atmomat = template.copy()
            for mat in template:
                nname = template[mat]["material"]
                idx  = columnnames[mat]
                atmomat[nname]["mass fraction"] = aLine[idx]
            gdmlmater = gdml_material(atmomat, name, temp, dens, pres,"gas")
            materials.append(gdmlmater)
        #now the geometry  entry
        solname  = "solid" + str(int(aLine[columnnames["SDID"]]))
        rmin     = aLine[columnnames["rmin"]]
        rmax     = aLine[columnnames["rmax"]]
        phimin   = aLine[columnnames["phimin"]]
        phimax   = aLine[columnnames["phimax"]]
        phimax   = phimax - phimin
        if np.abs(phimax -2.0*np.pi) < 0.01: phimax = "TWOPI"
        thetamin = aLine[columnnames["thetamin"]]
        thetamax = aLine[columnnames["thetamax"]]
        thetamax = thetamax - thetamin
        if np.abs(thetamax -np.pi) < 0.01: thetamax = "PI"
        if thetamax == 2.0: thetamax = "PI"
        sphere   = '\t<sphere name="%s" rmin="%f" rmax="%f" startphi="%.4f" deltaphi="%s" starttheta="%.4f" deltatheta="%s" lunit="km" aunit="rad"/>\n'%(solname,rmin,rmax,phimin,str(phimax),thetamin,str(thetamax))
        geometry.append(sphere)
        struct.append(['volume'+str(sdid),name,solname,sdid])
    wrld = data[-1,1]
    return materials, geometry, struct, wrld

def psf2gdml():
    mat, geom, struct,wrld = line_processor('simulation.psf')
    wrld += 100
    gdml_compile(mat,wrld,geom,struct,'simulation.gdml')
    
def convert_phi(phi):
    # K. Herbst phi conversion for LIS.
    new_phi = 1.025 * phi + 24.18
    return new_phi

def load_array(theurl,rowstoskip=7):
    response = requests.get(theurl, verify=False)
    phidata  = response.content.decode('utf-16')
    phis     = []
    for k in phidata.split('\n'):
        thesplit = k.split()
        if len(thesplit)==2:
            newphis = [float(k) for k in thesplit]
            phis.append(newphis)
    phis = np.array(phis)
    return phis

   
def find_phi(year,month,day,hour):
    year_start    = datetime.date(year,1,1)
    year_event    = datetime.date(year,month,day)
    diff          = year_event - year_start + datetime.timedelta(hours = hour)
    year_ratio    = diff / datetime.timedelta(days=365.25)
    year_usoskin  = year+year_ratio
    phis          = load_array(phi_url)
    diff_ar       = np.absolute(phis[:,0]-year_usoskin)
    index         = diff_ar.argmin()
    phi_to_conv   = phis[index,1]
    phi_converted = convert_phi(phi_to_conv)
    print('converted phi obtained: %.2f MV for the GCR spectrum (Herbst conversion of Usoskin values)'%phi_converted)
    phi_file      = open('sim_phi','w')
    phi_file.write('# Solar modulation parameter phi in MV, obtained from Usoskin, modified by Herbst.\n')
    phi_file.write("%.2f\n"%phi_converted)
    phi_file.close()
    return phi_converted

def copy_sim_files():
    # his function assumes that the working directory is the simulation subfolder within the atris directory.
    os.system("cp ../../phantoms/* ./")
    print("coppied phantoms and simulation.bins to the simulation subfolder")
     
def check_physics_list():
    # this function checks if the provided physics list is valid or not
    pass
    


def simprep_manager(year,month,day,hour_utc,latitude,longitude,hmin,hmax,deltah):
    print("currently working in the following folder: ",os.getcwd())
    print("this should be the simulation subfolder within the atris directory. If not, please check.")
    nrlm  = get_atmosphere(year,month,day,hour_utc,longitude,latitude,hmin,hmax,deltah) # get the model output
    nrlm  = nrlm_reformer(nrlm) # rearange the modern format in to the legacy format
    nrml2psf(nrlm)      # take the data and create a psf file
    psf2gdml()       # read the psf file and create the gdml file
    phi = find_phi(year,month,day,hour_utc)
    copy_sim_files()
    print("The simulation has been prepared. If you want to perform additional manual settings, please go ahead an modify the configuration files.")
    print("In particular the simulation macro allows you to define additional control aspects for the simulation.")
    return phi
    
def gen_macros(rootdir,number,workerthreads,alpha_factor):
    os.chdir(rootdir)
    amg.macroGenManager(number,workerthreads,alpha_factor)
    print("Simulation macros and files for protons and alphas have been created. The simulation can be started.")


def resolve_geant4_setup_script(rootdir):
    candidates = []
    geant4_sh = os.environ.get("GEANT4_SH")
    geant4_install_dir = os.environ.get("GEANT4_INSTALL_DIR")
    if geant4_sh:
        candidates.append(geant4_sh)
    if geant4_install_dir:
        candidates.append(os.path.join(geant4_install_dir, "bin", "geant4.sh"))
    candidates.append(os.path.join(rootdir, "install", "bin", "geant4.sh"))
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate
    return None
    
def start_sim(rootdir,simname,physlist):
    os.chdir(rootdir+'atris/simulation/')
    os.system('rm -f ./%s.log'%simname)
    print('the %s simulation is starting using the following command:'%simname)
    command      = './AtRIS '+physlist+' '+simname+' -1 32 > ' + simname + ".log"
    geant4_sh = resolve_geant4_setup_script(rootdir)
    if geant4_sh is not None:
        command = "source " + shlex.quote(geant4_sh) + "; " + command
    else:
        print("No geant4.sh found via GEANT4_SH, GEANT4_INSTALL_DIR, or rootdir/install/bin/geant4.sh.")
        print("Proceeding without sourcing Geant4 from simtools.py.")
    print(command)
    #subprocess.run(command, shell=True)
    subprocess.Popen(command,shell=True)
    print('Now we start simulation monitoring and wait for finish')

def monitor_process(simname):
    result = subprocess.check_output(['tail', '-n4', './%s.log'%simname]).decode('utf-8')
    #while result.splitlines()[-1] != "sasa":
    return(result)
    
def monitor_sim(simname):
    lastResultLine = ""
    expected       = "Sasa"
    old_result     = ""
    while lastResultLine != expected:
        time.sleep(5)
        results = monitor_process(simname)
        if old_result != results:
            clear_output(wait=False)
            print(results)
            old_result = results
            if results.split('\n')[-2][-4:]=='ed. ':
                lastResultLine = "Sasa"
                if simname == "protons":
                    print(simname, " simulation has finished at least one thread. It will take 5 more minutes to finish all threads. You can proceed with the alpha simulations.")
                elif simname == "alphas":
                    print(simname, " simulation has finished at least one thread. It will take 5 more minutes to finish all threads. Now it is time to postprocess the data.")

    
    
if __name__ == "__main__":
    #simprep_manager(1999,11,17,12.5,23,-33,0,100,1.)
    copy_sim_files()
