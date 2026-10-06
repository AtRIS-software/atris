# Install and use AtRIS on UiO Geosciences servers

This guide installs AtRIS on Ivan using the University of Oslo Geosciences
shared Geant4 installation. It explains the terminal commands as you go:
log in, connect to GitHub, build AtRIS, and install the Python tools.
For other computers, use [Installing AtRIS](installation.md).

Once installed, follow the [Earth tutorials](../tutorials/earth-nrlmsis-full.md)
to prepare a simulation and inspect its first results, or
[prepare your own model](prepare-simulation.md).

## What to do when

The guide separates background information from commands according to when
they are needed:

| When | What to do |
| --- | --- |
| Before starting | Read [Background](#background-read-as-needed) if the terminal, paths, or Git are unfamiliar. |
| First installation only | Complete [One-time installation](#one-time-installation): connect GitHub, create the workspace, clone AtRIS, link Geant4, build, and install the Python tools. |
| After every login used for AtRIS work | Complete [Prepare the shell](#after-every-login-prepare-the-shell): load the runtime modules and source `setup_atris.sh`. |
| After installation | Continue with [a simulation](#after-installation-prepare-and-run-a-simulation). |

## Background (read as needed)

The material in this section explains the tools and notation. It is not a set
of installation commands to repeat.

### Expected background

The commands below explain the shell, Git, CMake, Python installation, and
UiO environment modules as they are needed. You can run the prepared examples
without writing Python or C++. For more practice with the terminal or Python,
use the resources below.

UiO's archived [introductory informatics day-one
exercises](https://www.uio.no/studier/emner/matnat/ifi/INF0010/h23/dag-1-.pdf)
provide a Norwegian-language introduction to the terminal, directories, and
paths. Its [day-two
exercises](https://www.uio.no/studier/emner/matnat/ifi/INF0010/h23/dag-2--in1900.pdf)
introduce running Python. The current
[Software Carpentry lessons](https://swcarpentry.github.io/) provide more
extensive introductions to the
[Unix shell](https://swcarpentry.github.io/shell-novice/),
[Git](https://swcarpentry.github.io/git-novice/), and
[Python](https://swcarpentry.github.io/python-novice-inflammation/). These are
learning resources rather than additional AtRIS installation requirements.

### How to read the commands

The terminal is a text interface to the computer. It displays a prompt and
waits for a command. On Ivan, a prompt may look like this:

```text
[username@ivan ~]$
```

Do not type the prompt itself. In this guide, type or paste only the text in a
`bash` block, then press Enter. Run the lines in order. Commands and filenames
are case-sensitive.

Three basic commands help you keep track of your location:

```bash
pwd
ls
cd /scratch/${USER}
```

- `pwd` prints the current directory.
- `ls` lists its contents.
- `cd` changes directory.
- `${USER}` is a shell variable containing your UiO username. The shell replaces
  it automatically; do not replace it by hand.
- `~` means your home directory.

Pressing Tab can complete a partly typed command or filename. Ctrl+C asks a
running foreground command to stop and returns you to the prompt. Passwords
and SSH-key passphrases normally show no characters while you type them; the
terminal is still receiving the keystrokes.

## Start every session: log in to Ivan

Do this whenever you start a new Ivan session. Open Terminal on macOS or Linux,
or a suitable SSH terminal on Windows. Replace `username` below with your own
UiO username:

```bash
ssh username@ivan.uio.no
```

From outside the UiO network, the
[Ivan page](https://www.mn.uio.no/geo/english/services/it/help/using-servers/linux-servers/ivan.html)
currently specifies Morgoth as a jump host:

```bash
ssh -J username@morgoth.uio.no username@ivan.uio.no
```

See UiO's [access-from-outside
instructions](https://www.mn.uio.no/geo/english/services/it/help/using-linux/access-from-outside.html)
for the general procedure.

The first connection may ask whether to trust the server's host key. Check
that the hostname and fingerprint agree with UiO's current information before
typing `yes`. Then enter your UiO password. A welcome message followed by an
Ivan prompt means that the login succeeded. Run these commands to confirm
where you are:

```bash
hostname
pwd
```

`hostname` should identify Ivan. The remaining commands in this guide run on
Ivan, not on your own computer. Use `exit` when you eventually want to log out.

The host-key question normally appears only on the first login.

## One-time installation

Complete the following subsections once when creating your personal AtRIS
installation. Cloning, linking, building, and installing are not normal login
steps.

### Connect your Ivan account with your GitHub account

The AtRIS source code is currently stored in a private GitHub repository. Until
AtRIS is made public, your GitHub account must be given access to the repository
and your Ivan account needs an SSH key registered with that GitHub account.
Git records the project's history and lets you obtain later changes with
`git pull`.

This is separate from logging in to Ivan. The SSH key lets GitHub recognize
Git operations, such as cloning and pulling AtRIS, from your Ivan account.

Follow GitHub's official
[Connecting to GitHub with
SSH](https://docs.github.com/en/authentication/connecting-to-github-with-ssh)
instructions, selecting Linux because the key is being created on Ivan. Those
instructions are authoritative and cover checking for an existing key,
generating one, adding its public part to GitHub, and testing the connection.
The minimum steps are repeated here for convenience.

On a first login to Ivan, you will normally not have an SSH key yet. Check
before creating one only to avoid overwriting a key in the exceptional case
that one is already present:

```bash
ls -la ~/.ssh
```

If `id_ed25519` and `id_ed25519.pub` already exist, do not overwrite them. If
they do not exist, create them:

```bash
ssh-keygen -t ed25519 -C "${USER}@ivan.uio.no"
```

The value after `-C` is only a descriptive label; it does not have to be the
email address associated with GitHub. This example records the UiO username
and the computer on which the key is stored. Accept the suggested filename and
choose a passphrase. Display the public key:

```bash
cat ~/.ssh/id_ed25519.pub
```

Copy the complete line beginning with `ssh-ed25519` and add it to your GitHub
account as an authentication key. Never copy, upload, or share the private file
`~/.ssh/id_ed25519`.

Test the connection from Ivan:

```bash
ssh -T git@github.com
```

The first connection to GitHub may produce another host-key question. Verify
GitHub's published fingerprint before accepting it. A message saying that
GitHub authenticated you but does not provide shell access means the test
succeeded; the absence of shell access is expected.

### Create your personal work area

Simulation runs belong in Ivan's scratch storage rather than your home
directory. The steps below also place the AtRIS checkout and build there, and
will create this layout:

```text
/scratch/<your-username>/atris-work/
├── atris/                  your Git checkout, or a link to it
├── geant4-v11.4.2 -> ...   link to the shared Geant4 installation
└── runs/                   your simulations
```

The name in angle brackets illustrates what `${USER}` supplies. Do not type the
angle brackets in a command.

There are two concrete reasons for this recommended layout. First,
`setup_atris.sh` looks for exactly one sibling `geant4-v<version>` installation.
Second, the simulations are kept under `/scratch`, where their potentially
large generated outputs belong. AtRIS does not require `runs/` to be beside the
AtRIS installation. The general run guides start in your chosen working
directory and use `ATRIS_ROOT` only to locate installed example inputs.

The AtRIS checkout may physically live somewhere else, such as your home
directory. In that case, `atris` above can be a symbolic link to that checkout,
just as `geant4-v11.4.2` is a link to Geant4. The important requirement for
`setup_atris.sh` is that the directory entry named `atris` should be directly
beside the `geant4-v<version>` entry in `atris-work`. The simulations should
still remain under `/scratch`. Keeping the checkout directly in `atris-work` is
simpler, so that is the arrangement used in the commands below.

The AtRIS checkout records which source version you used and lets you obtain
updates with `git pull`. A simulation project's inputs, scripts, and notes can
also be kept in their own Git repository to record their history and share
them through GitHub. Large generated results should remain outside Git.

Create the parent directory and enter it:

```bash
mkdir -p "/scratch/${USER}/atris-work"
cd "/scratch/${USER}/atris-work"
pwd
```

`mkdir -p` creates missing directories and is harmless if they already exist.
`pwd` should now print `/scratch/` followed by your username and
`/atris-work`.

Clone AtRIS into a new directory named `atris`:

```bash
git clone git@github.com:svaberg/atris.git atris
```

Clone means create a new local copy that remains connected to the Git
repository. This checkout belongs to you, so the compiler and Python packaging
tools can write their generated files in it.

Create a symbolic link to the shared Geant4 installation, then create the run
directory:

```bash
ln -s /uio/hypatia/geofag-felles/phab/software/geant4/geant4-v11.4.2 geant4-v11.4.2
mkdir -p runs
ls -l
```

A symbolic link is a reference, not a copy. `atris` should remain directly
beside this link because `setup_atris.sh` looks for exactly one directory named
`geant4-v<version>` beside AtRIS. Each `ln -s` command is a one-time setup step
and does not need to be repeated on each login. If the command reports `File
exists`, inspect the existing link with `ls -l geant4-v11.4.2` instead of
creating another one.

Scratch storage is for working data, not the only copy of important results.
Read UiO's [Hypatia storage
guidance](https://www.mn.uio.no/geo/english/services/it/help/using-linux/hypatia.html)
and copy irreplaceable results to an appropriate backed-up location.

### Load Ivan's build tools

UiO uses environment modules to make particular software versions available.
Load the versions used by the current shared Geant4 installation:

```bash
module load CMake/3.27.6-GCCcore-13.2.0 \
  expat/2.5.0-GCCcore-13.2.0 \
  Python/3.11.5-GCCcore-13.2.0
module list
```

The backslash at the end of the first two lines means that the command
continues on the next line. `module list` shows the active modules. Module
settings last only for the current login shell and must be loaded again after
a new login.

These exact versions match the present Ivan installation. If Ivan reports
that one is unavailable, stop and ask which replacement is compatible with
the shared Geant4 build; choosing unrelated compiler versions can produce a
linking failure.

### Build AtRIS

Move into your checkout and load the AtRIS/Geant4 shell environment:

```bash
cd "/scratch/${USER}/atris-work/atris"
source setup_atris.sh
```

`source` runs the setup in the current shell so that its environment changes
remain in effect. It sets `ATRIS_ROOT`, adds the future executable directory
to `PATH`, and loads Geant4 through the sibling link.

Configure and compile AtRIS:

```bash
cmake -B build
cmake --build build
```

The first command creates a `build` directory and configures it from the
checkout's `CMakeLists.txt`. The second compiles the program. AtRIS is a small
build and does not need a parallel-build option.

### Install the Python tools

AtRIS also contains Python commands for preparing, running, processing, and
plotting simulations. While still inside your personal `atris` checkout, run:

```bash
python -m pip install ".[plot]"
```

- `python -m pip` uses pip belonging to the Python module loaded above.
- `[plot]` installs the supported plotting dependencies as well as the core
  tools.

An editable installation is needed only when you intend to modify the Python
code itself. In that case, add `--editable` to the command.

Check the installation:

```bash
atris-run --version
```

The command should report both the AtRIS executable version and the Python-tool
version. You are ready to prepare a simulation.

## After every login: prepare the shell

Files, builds, links, and Python packages remain after logout. Environment
modules and `source` settings do not. After each login that you will use for
AtRIS work, run:

```bash
cd "/scratch/${USER}/atris-work"
module load expat/2.5.0-GCCcore-13.2.0 \
  Python/3.11.5-GCCcore-13.2.0
source atris/setup_atris.sh
```

This is the complete repeated login setup for ordinary AtRIS work. CMake is not
needed unless you are building or updating AtRIS. Do not clone, recreate links,
rebuild, or reinstall merely because you logged in again.

## After installation: prepare and run a simulation

After [preparing each login shell](#after-every-login-prepare-the-shell), follow
[simulation preparation](prepare-simulation.md), then
[server/workstation execution](run-on-server.md). Physics preparation is the
same on Ivan as elsewhere. The sections below supply UiO-specific resource and troubleshooting details.

## Optional UiO operational reference

The remaining sections are UiO-specific operational and troubleshooting
reference. They are not additional installation steps.

## Choose a UiO machine and share it fairly

The Department's [Linux server
index](https://www.mn.uio.no/geo/english/services/it/help/using-servers/linux-servers/)
currently lists three machines suitable for parallel work:

| Machine | CPUs reported by UiO | Memory | Relevant characteristics |
| --- | ---: | ---: | --- |
| [Ivan](https://www.mn.uio.no/geo/english/services/it/help/using-servers/linux-servers/ivan.html) | 80 | 1.5 TiB | 40 physical cores with hyper-threading; large memory, but slower than Mimi for CPU-bound work |
| [Mimi](https://www.mn.uio.no/geo/english/services/it/help/using-servers/linux-servers/mimi.html) | 256 | 1 TiB | 128 physical cores with hyper-threading; approximately 250 GiB virtual-memory soft limit per process |
| [Victor](https://www.mn.uio.no/geo/english/services/it/help/using-servers/linux-servers/victor.html) | 256 | 4 TiB | 128 physical cores with hyper-threading and two H100 NVL GPUs; ordinary AtRIS runs do not use the GPUs |

The CPU totals include hyper-threading. None of these machines has a queue or
CPU quota. UiO therefore gives users the same rules of thumb on all three
machine pages:

- do not use more than half of the CPUs, memory, or scratch space;
- run unusually heavy work at night or during weekends; and
- check the load before starting and occasionally while the calculation runs,
  reducing or stopping work if resources become scarce.

On an otherwise idle machine, the half-CPU rule corresponds to at most 40
Geant4 worker threads on Ivan or 128 on Mimi and Victor. These are ceilings,
not default thread counts or reservations. Select a lower value when other
users are active, and remember that thread counts add when multiple AtRIS
processes run concurrently.

UiO's [running-programs
guide](https://www.mn.uio.no/geo/english/services/it/help/using-linux/running-programs.html)
recommends checking CPU load and available memory with:

```bash
uptime
free -h
top
```

Press `q` to leave `top`. UiO also recommends `nice`, which lowers CPU priority
when processes compete. `nice` does not limit the number of cores, so set
`G4FORCENUMBEROFTHREADS` as well.

For the launch command and instructions to monitor, stop, and resume a run,
use [Run on a server or workstation](run-on-server.md#keep-a-chunked-run-running-after-logout).
Apply the UiO resource limits above when choosing the thread count.

## Use Mimi or Victor

On Mimi or Victor, first check that the shared Geant4 directory is accessible
and which compiler modules match it. Then:

1. Log in to that machine and use its designated scratch or project storage.
2. Clone a personal AtRIS checkout there.
3. Create the compatible `geant4-v<version>` sibling link.
4. Load that machine's matching build and Python modules.
5. Build and install AtRIS from the personal checkout.

The server's linked UiO page is authoritative for its current hardware and
usage guidance.

## Diagnose common failures

### `Permission denied (publickey)` from GitHub

Test the GitHub connection again:

```bash
ssh -T git@github.com
```

Confirm that `~/.ssh/id_ed25519.pub` was added to the correct GitHub account.
Never upload or send the private `~/.ssh/id_ed25519` file.

### Setup cannot find exactly one Geant4 directory

Inspect the workspace:

```bash
cd "/scratch/${USER}/atris-work"
ls -ld atris geant4-v*
```

There must be exactly one matching Geant4 directory or link beside `atris`.
Its name must have the `geant4-v<version>` form.

### `cmake` or an `atris-*` command is not found

Open a new login shell only if necessary, then repeat
[After every login: prepare the shell](#after-every-login-prepare-the-shell). Use
`module list`, `command -v cmake`, and `command -v atris-run` to see what the
current shell can find.

### CMake reports that its cache belongs to another directory

A CMake build directory records the absolute path where it was configured.
This can happen after copying or moving a checkout. From your own AtRIS
checkout, remove only the generated build directory and recreate it:

```bash
cd "/scratch/${USER}/atris-work/atris"
rm -r build
cmake -B build
cmake --build build
```

Do not remove a shared directory or another user's build.

### A path still gives `Permission denied`

A directory requires traversal permission all the way from `/` to the target.
Display each path component with:

```bash
namei -l /full/path/to/the/failing/file
```

Only the file owner or a server administrator can repair permissions on a
shared path owned by another account.
