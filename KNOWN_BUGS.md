# Known bugs

This file records confirmed defects that have not yet been fixed.

## Source position and direction histograms omit half of the sphere

The `h2.dir` and `h2.pos` histograms use global `cos(theta)` values but accept
only the range from 0 to 1. Global `cos(theta)` spans -1 to 1, so values from
the southern half of the source-position sphere and momentum-direction sphere
are placed in the histogram underflow bins. The quick-look plots omit those
underflow bins.

The source itself is generated correctly. This defect affects only the source
position and direction diagnostic CSV files and plots; it does not change
particle trajectories, atmospheric ionization, or phantom responses.

Correcting the histogram limits in `src/HistoManager.cc` requires rebuilding
AtRIS and rerunning a simulation to produce complete angular diagnostics.
