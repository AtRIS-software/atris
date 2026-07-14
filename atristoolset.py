import os
import shutil
import subprocess
import urllib.request
from os.path import exists
import pprint
import shlex


def resolve_geant4_install(rootdir):
    env_install = os.environ.get("GEANT4_INSTALL_DIR")
    env_script = os.environ.get("GEANT4_SH")
    candidates = []
    if env_script:
        candidates.append(env_script)
    if env_install:
        candidates.append(os.path.join(env_install, "bin", "geant4.sh"))
    candidates.append(os.path.join(rootdir, "install", "bin", "geant4.sh"))

    for candidate in candidates:
        if candidate and exists(candidate):
            return candidate
    return None


def check_requirements():
    cond1     = len(os.popen("/sbin/ldconfig -p | grep xerces").read()) == 0 # check if xerces is here 
    cond2 = len(os.popen("gcc --version").read()) ==0            # check if fcc is here
    cond3 = len(os.popen("cmake --version").read()) ==0           # check for cmake
    score = cond1*1 + cond2*2 + cond3*4
    errors  = {1:'xerces is missing',
               2:'gcc is missing',
               3:'xerces and gcc are missing',
               4:'cmake is missing',
               5:'xerces and cmake are missing',
               6:'gcc and cmake are missing',
               7:'xerces, gcc and cmake are missing',
               0:'all conditions are ok, proceeding'}
    result = score == 0
    print('Checking for libraries: %s'%['ok','not ok'][result==0], errors[score])
    return result

def find_latest_geant4_release():
    forced_version = os.environ.get("GEANT4_VERSION")
    if forced_version:
        version = forced_version if forced_version.startswith("v") else f"v{forced_version}"
        dlink = "https://github.com/Geant4/geant4/archive/refs/tags/" + version + ".tar.gz"
        return dlink, version

    url = 'https://github.com/Geant4/geant4/releases/latest'
    page = urllib.request.urlopen(url).read().decode("utf-8").split('\n')
    thestring = None
    for k in page:
        if 'expanded_assets' in k:
            thestring = k
            break
    if thestring is None:
        raise RuntimeError("Unable to determine latest Geant4 release tag from GitHub")
    version = thestring.split('/')[-1].split('"')[0]
    dlink = "https://github.com/Geant4/geant4/archive/refs/tags/" + version + '.tar.gz'
    return dlink, version

def download_geant4(thelink):
    import requests
    from tqdm.auto import tqdm
    
    r = None  # sometimes the get fails, so I've modified this to make it more reliable
    m = None  # sometimes even deeper fails happen in the fetching algo
    while (r == None) or (type(r) == None) or (m==None) or (type(m)==None):
        if (type(r) != None):
            r = requests.get(thelink, stream=True)
            r.raise_for_status()
        m = r.headers.get("Content-Length")
    total_length = int(m)
    with tqdm.wrapattr(r.raw, "read", total=total_length, desc="")as raw:
        # save the output to a file
        with open(f"{os.path.basename(r.url)}"+'.tar.gz', 'wb')as output:
            shutil.copyfileobj(raw, output)        

def get_threads():
    return os.cpu_count() or 1

def geantinstall(rootdir):
    os.chdir(rootdir)
    external_geant4 = resolve_geant4_install(rootdir)
    if external_geant4:
        print('Found an existing Geant4 setup script at', external_geant4)
        print('Skipping bundled Geant4 installation and using the external install instead.')
        return True
    if not (exists('geant4_install_ok')): 
        dlink, ver = find_latest_geant4_release()
        print('proceeding to download version', ver, ' using the link ',dlink)
        download_geant4(dlink)
        to_remove = ["source","build","install","geant4*"]
        for k in to_remove: shutil.rmtree('./%s'%k, ignore_errors=True)
        os.system('rm -rf ./geant4-*')
        os.system('tar -zxf %s.tar.gz'%ver)
        os.system('mkdir build install')
        os.system('mv geant4* ./source')
        test = check_requirements()
        if test:
            print('proceeding to build geant4, please wait 10-20 minutes.')
            os.chdir("build")
            os.system("cmake --version")
            N = get_threads()
            os.popen("cmake -DCMAKE_INSTALL_PREFIX=../install -DGEANT4_USE_GDML=ON -DGEANT4_INSTALL_DATA=ON -DGEANT4_BUILD_VERBOSE_CODE=OFF ../source/").read()
            print("Build config complete, proceeding to compile. Please wait")
            os.popen("make -j"+str(N)).read()
            os.popen("make install").read()
            print("installation and compilation of geant4 has been succesfully completed.")
            os.chdir(rootdir)
            os.system('touch geant4_install_ok')
            print('The "geant4_install_ok" file has been created to avoid future reinstallations.')
            return True
        else:
            print('please check that you have gcc, cmake and xerces-c installed')
            return False
    else:
        print('The file "geant4_install_ok" has been found. Continuing without geant4 installation.')
        print('If you wish for the script to perform a clean install, please remove the  "geant4_install_ok".')
        return True

def source_geant4_from_python(rootdir):
    fname = resolve_geant4_install(rootdir)
    if fname is None:
        raise FileNotFoundError("Could not find geant4.sh. Set GEANT4_INSTALL_DIR or GEANT4_SH, or install Geant4 first.")
    command   = shlex.split("env bash -c 'source %s && env'"%fname)
    proc      = subprocess.Popen(command, stdout = subprocess.PIPE)
    for line in proc.stdout:
        (key, _, value) = line.decode().partition("=")
        os.environ[key] = value
    proc.communicate()
    #pprint.pprint(dict(os.environ)) # used only for debugging
    
    
        
def atrisinstall(rootdir):
    os.chdir(rootdir)
    N = get_threads()
    if not (exists('atris_install_ok')): 
            os.chdir(rootdir)
            #os.system("source ./install/bin/geant4.sh") # this doesn't work
            source_geant4_from_python(rootdir)            
            print("Sourcing complete, now proceeding to build and install AtRIS.")
            os.chdir(rootdir+"atris")
            shutil.rmtree('./simulation', ignore_errors=True)
            os.makedirs("./simulation")
            os.system("pwd")
            os.chdir("simulation")
            os.system("pwd")
            os.system("cmake ..")
            os.system("make -j"+str(N))
            os.chdir(rootdir)
            os.system('touch atris_install_ok')
            print('The "atris_install_ok" file has been created to avoid future reinstallations.')
    else:
        print('The file "atris_install_ok" has been found. Continuing without atris installation.')
        print('If you wish for the script to perform a clean install, please remove the  "atris_install_ok".')
        print('Continuing to source geant4.sh .')        
        os.chdir(rootdir)
        source_geant4_from_python(rootdir)
        os.chdir(rootdir)
        print("Sourcing geant4.sh is complete. Returning to root AtRIS folder.")
    os.system("pwd")
    os.chdir("./atris/simulation/")
    if os.getcwd()[-10:] == "simulation":
        print('Setting work directory to ./atris/simulation successful. Continuing to simulation conf.')
    else:
        print("Current working directory isn't ./atris/simulation/ - aborting! - please check install.")
        
def create_simconfig(long,lat,year,month,day,hour,alt_min,alt_max,alt_step,parts,phantoms,number,threads,phys_list,alpha_factor):
    if not (exists('simconfig_ok')):
        output_string  = 'longitude     = %.2f\n'%long
        output_string += 'latitude      = %.2f\n'%lat
        output_string += 'year          = %i\n'%year
        output_string += 'month         = %i\n'%month
        output_string += 'day           = %i\n'%day
        output_string += 'hour_utc      = %.2f\n'%hour
        output_string += 'alt_max       = %.2f\n'%alt_max
        output_string += 'alt_step      = %.2f\n'%alt_step
        output_string += 'particles     = %s\n'%parts
        output_string += 'numberparts   = %i\n'%number
        output_string += 'numberthreads = %i\n'%threads
        output_string += 'alt_min       = %.2f\n'%alt_min
        output_string += 'phantoms      = "%s"\n'%phantoms
        output_string += 'phys_list     = "%s"\n'%phys_list
        output_string += 'alpha_factor  = "%s"\n'%alpha_factor
        output_file    = open('simconfig_ok','w')
        output_file.write(output_string)
        output_file.close()
        print("simconfig file has been created")
    else:
        print("The file simconfig_ok exists. Using existing simulation configuration. To reconfigure, and")
        print("provide a new configuration, please remove the simconfig_ok from the simulation subfolder.")

    

if __name__ == "__main__":
    rootfolder = '/git/AtRIS2/'
    result = geantinstall(rootfolder)
    if result: atrisinstall(rootfolder)
