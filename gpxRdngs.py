# gpxRdngs.py -- general utility for gpx (GPS Exchange Format) xml data
# v0.90 crh 05-may-15 -- under development
# v1.00 crh 06-may-15 -- initial release (elevation functionality)
# v2.00 crh 08-may-15 -- v2, providing enhancements & BSV functionality
# v2.11 crh 11-may-15 -- deal elegantly with <ele> elements missing
# v2.21 crh 19-may-15 -- delta processing added & output prettified
# v2.31 crh 08-jun-15 -- process times, allow various way-point element tags & remove bsv dups
# v3.05 crh 20-jun-15 -- remove gpx class to library, significantly revamp program capability
# v3.12 crh 05-sep-15 -- provide output file path based on input file path, also give absolute path option
# v3.20 crh 16-jan-16 -- minor mods & setParser() added

# written on a windows platform using python v2.7

#!/usr/local/bin/python

## notes
# input file assumed to be gpx xml data consisting of way-points defining route
# currently catering specifically for OS getaMap gpx export files
#
# <gpx>
#   <rte>
#     <name>xxx</name>
#     <rtept lat="yyy.yyyyy" lon="zzz.zzzzz">
#       <ele>xxx.x</ele>
#       <time>timestamp</time>
#     </rtept>
#   </rte>
# </gpx>
#
# the <rtept> (route point)/<ele> (elevation)/<time> (timestamp) element group is repeated for each way-point
# sometimes the <ele> &/or <time> elements are missing &/or different way-point elements are used.
# other flavours of gpx are available, possibly holding much more data per way-point :-)
#
# the BSV record fields are the latitude, longitude and elevation float values from the GPX file
# together with the easting & northings (int value in m) & the 1/10/100m NGR
# very close easting & northing values in adjacent records are treated as duplicates
# if delta values required then deltaL & deltaH fields (m) appended

import argparse
import re
from sys import stdout, stderr, exit

from crhDebug import *  # debug & messaging
from crhFile import *   # file handling
from crhString import * # string utilities
import crhTimer         # timer
from crhMap import *    # mapping utilities
import crhGPX           # gpx class

## essential variables
progName = 'gpxRdngs'
compact = False  # generate compact (ie: not pretty) xml output (reduce output file size)
quiet = False   # less output (quiet & verbose are not mutually exclusive)
verbose = False # more output
stats = False   # generate route statistics
xml1 = False    # generate xml markup from gpx file
xml2 = False    # generate xml markup from bsv records
route = False   # generate route xml markup from bsv records
bsv = False     # generate bar separated value records
auto = False    # output file name based on input file name (.txt extension)
all = False     # process all *.gpx files in given directory
delta = False   # include delta values in bsv records
time = True     # process time data
#tolerT = gpx.tolerT # gpx way-point delta time tolerance (sec)
#tolerL = gpx.tolerL # bsv delta length tolerance (m)
#tolerV = gpx.tolerV # cumulative height delta gain/loss tolerance (m)
tolerZ = False  # set all tolerances to zero (ie, disable them) initially if true
tolerT = 12 # minimum acceptable time difference between consecutive gpx way-points
tolerL = 5  # minimum acceptable length difference between consecutive BSV way-points
tolerV = 10 # minimum height difference between gpx way-points used in cumulative gain/loss
inputFile = None
outputFile = None
outputH = None
gpxData = None

precision = crhGPX.gpx.precision   # precision of ngr (6, 8 or 10 digits)
# exceeding the following values generates warning/informational messages
# overwrite initial values set in crhGPX (used instantiating a gpx object)...
crhGPX.maxDeltaL = 400.0  # default: 400.0
crhGPX.maxDeltaV = 30.0   # default: 30.0
crhGPX.maxDeltaS = 250.0  # default: 250.0

## define functions
def setParser():
    '''
    set up argparser object & return it
    '''
    parse = argparse.ArgumentParser(description="process map route gpx (GPS Exchange Format xml) data")
    parse.add_argument('-i', '--input', action="store", dest="infile",
        help="input filename (eg: d:\\data\\in.gpx)", required=True)
    outfile = parse.add_mutually_exclusive_group() # use either or none of -o, -O, -a & -A
    outfile.add_argument('-o', '--output', action="store", dest="outfile",
        help="relative output filename (eg: out.txt)")
    outfile.add_argument('-O', '--Output', action="store", dest="absoutfile",
        help="full output filename path (eg: d:\\out.txt)")
    outfile.add_argument('-a', '--auto', action="store_true", dest="automode",
        help="use output file derived from input file name")
    outfile.add_argument('-A', '--all', action="store_true", dest="allmode",
        help="process all files in directory (use wildcard filter)")
    parse.add_argument('-s', '--stats', action="store_true", dest="statsmode",
        help="generate route statistics")
    parse.add_argument('-b', '--bsv', action="store_true", dest="bsvmode",
        help="generate bsv records")
    xmlDoc = parse.add_mutually_exclusive_group() # use either or neither -x & -X
    xmlDoc.add_argument('-x', '--xmlbsv', action="store_true", dest="xmlmode1",
        help="generate gpx xml records from bsv records")
    xmlDoc.add_argument('-X', '--xmlgpx', action="store_true", dest="xmlmode2",
        help="generate gpx xml records from gpx file")
    parse.add_argument('-c', '--compact', action="store_true", dest="compactmode",
        help="generate compact gpx xml output (reduce file size)")
    parse.add_argument('-d', '--delta', action="store_true", dest="deltamode",
        help="include delta values in bsv records")
    parse.add_argument('-r', '--route', action="store_true", dest="routemode",
        help="generate route gpx xml records from bsv records")
    parse.add_argument('-t', '--time', action="store_true", dest="timemode",
        help="ignore gpx time data")
    parse.add_argument('-p', '--precision', action="store", dest="precisionmode",
        help="set national grid reference precision", choices=['l','m','h'], default='m')
    parse.add_argument('-q', '--quiet', action="store_true", dest="quietmode",
        help="suppress some program messages")
    parse.add_argument('-v', '--verbose', action="store_true", dest="verbosemode",
        help="generate additional program messages")
    parse.add_argument('-T', '--timetoler', action="store", dest="ttmode",
        help="way-point time delta tolerance (0: disable)",
        default = tolerT, type = int)
    parse.add_argument('-L', '--lengthtoler', action="store", dest="ltmode",
        help="bsv length delta tolerance (0: disable)",
        default = tolerL, type = int)
    parse.add_argument('-H', '--heighttoler', action="store", dest="htmode",
        help="cumulative height gain/loss tolerance (0: disable)",
        default = tolerV, type = int)
    parse.add_argument('-Z', '--zerotoler', action="store_true", dest="zerotoler",
        help="set all tolerances to zero initially")
    return parse

def openOutFile(outputF = None):
    '''
    open output file for write (ie: overwrite) access,
    if not already open
    '''
    global outputH
    if outputF is None:
        outputF = outputFile
    if outputH is None:   # not open
        outputH = openFile(outputF, 'w')
        if outputH is None:
            statusErrMsg('fatal', 'openOutFile()', 'error opening output file {}'.format(outputF))
            exit(1)
        else:
            statusErrMsg('info', 'openOutFile()', 'output file opened: {}'.format(outputF), quiet)

def closeOutFile():
    '''
    close output file, if open
    '''
    global outputH
    if outputH is not None:
        outputH.close()
        outputH = None

def printStrIO(sio):
    '''
    write contents of sio to stdout and/or file
    '''
    global outputH
    if outputFile is None:
        print sio.getvalue()
        msg('')
    else:
        if verbose:
            print sio.getvalue()
            msg('')
            openOutFile()
            outputH.write(sio.getvalue())
        else:
            openOutFile()
            outputH.write(sio.getvalue())
        outputH.write('\n')
    sio.close()

def processInputfile(inputFile):
    '''
    process gpx input file
    '''
    gpxData = crhGPX.gpx(inputFile, time, delta, tolerT = tolerT, tolerV = tolerV, tolerL = tolerL, precision = precision)
    if gpxData.validData():
        if xml1:
            printStrIO(gpxData.genXML(not compact, bsv = True, track = not route))
        if xml2:
            printStrIO(gpxData.genXML(not compact, bsv = False))
        if bsv:
            printStrIO(gpxData.genBSV())
        if stats or ((not xml1) and (not xml2) and (not bsv)):  # always do something!
            printStrIO(gpxData.genStats())
        closeOutFile()
    else:
        statusErrMsg('warn', 'main', 'unable to process gpx file: {}'.format(inputFile))

## main program
setProgName(progName)
errTMsg('{} -- process gpx data file'.format(getProgName()), quiet)

## process arguments
parser = setParser()
args = parser.parse_args()
quiet = args.quietmode

if quiet:
    crhGPX.gpx.quiet = True
verbose = args.verbosemode
xml1 = args.xmlmode1
xml2 = args.xmlmode2
route = args.routemode
bsv = args.bsvmode
stats = args.statsmode
auto = args.automode
all = args.allmode
compact = args.compactmode
delta = args.deltamode
time = not args.timemode
tolerT = args.ttmode
tolerL = args.ltmode
tolerV = args.htmode
tolerZ = args.zerotoler

if verbose:
    errMsg('verbose mode set', quiet)
    crhGPX.gpx.verbose = True
if xml1: 
    errMsg('xml mode set (bsv records)', quiet)
    if verbose:
        if compact:
            errMsg('output compact xml markup for bsv records', quiet)
        else:
            errMsg('output pretty xml markup for bsv records', quiet)
    if route:
        errMsg('xml route mode set (bsv records)', quiet)
        if verbose:
            if compact:
                errMsg('output compact route gpx xml markup', quiet)
            else:
                errMsg('output pretty route gpx xml markup', quiet)
    else:
        if verbose:
            if compact:
                errMsg('output compact track gpx xml markup', quiet)
            else:
                errMsg('output pretty track gpx xml markup', quiet)
elif xml2:
    errMsg('xml mode set (gpx file)', quiet)
    if verbose:
        if compact:
            errMsg('output compact xml markup for gpx file', quiet)
        else:
            errMsg('output pretty xml markup for gpx file', quiet)
    if route:
        if compact:
            errMsg('xml route mode ignored (gpx file)', quiet)
        else:
            errMsg('xml route mode ignored (gpx file)', quiet)
        if verbose:
            errMsg('output will be as used in gpx file', quiet)
if stats:
    errMsg('statistics mode set', quiet)
    if verbose: errMsg('output route statistics', quiet)
if bsv:
    errMsg('bsv mode set', quiet)
    if verbose: errMsg('output bsv records', quiet)
if delta and bsv:
    errMsg('delta values mode set', quiet)
    if verbose: errMsg('output delta fields in bsv records', quiet)
elif delta:
    statusErrMsg('warn', 'args', 'delta switch ignored (no bsv switch specified)', quiet)
    delta = False
    if verbose: errMsg('delta mode only applies if bsv records generated', quiet)
if not time:
    errMsg('ignore time mode set', quiet)
    if verbose: errMsg('do not process gpx time data', quiet)
if tolerT:
    errMsg('gpx way-point time delta tolerance: {} sec'.format(tolerT), quiet)
    if verbose: errMsg('way-point time delta mode discards closer adjacent readings', quiet)
else:
    errMsg('way-point time delta tolerance disabled', quiet)
    if verbose: errMsg('do not discard gpx way-point readings', quiet)
if tolerZ:
    tolerL = 0
    tolerT = 0
    tolerV = 0
    statusErrMsg('info', 'args', 'all tolerance values set to 0 (disabled)', quiet)
    if verbose: errMsg('can be overruled by setting individual tolerance values', quiet)
if tolerL and delta and bsv:
    tolerL = 0
    statusErrMsg('warn', 'args', 'delta values mode active: BSV length delta mode disabled', quiet)
    if verbose: errMsg('bsv length delta mode incompatible with delta values mode', quiet)
elif tolerL and bsv:
    errMsg('bsv length delta tolerance: {}m'.format(tolerL), quiet)
    if verbose: errMsg('bsv length delta mode discards duplicate bsv records', quiet)
elif tolerL:    # ineffective: bsv mode not set
    pass
elif bsv:
    errMsg('bsv length delta tolerance disabled'.format(tolerL))
    if verbose: errMsg('do not discard bsv readings', quiet)
if tolerV:
    errMsg('bsv cumulative height gain/loss tolerance: {}m'.format(tolerV), quiet)
    if verbose: errMsg('bsv cumulative height gain/loss mode ignores smaller values', quiet)
else:
    errMsg('cumulative height gain/loss tolerance disabled')
    if verbose: errMsg('do not igore any bsv cumulative height gain/loss values', quiet)
if args.precisionmode == 'l':
    precision = 6
    errMsg('low precision set', quiet)
    if verbose: errMsg('national grid reference precision is 100m', quiet)
elif args.precisionmode == 'h':
    precision = 10
    errMsg('high precision set', quiet)
    if verbose: errMsg('national grid reference precision is 1m', quiet)
else:
    errMsg('medium precision set (default)', quiet)
    if verbose: errMsg('national grid reference precision is 10m', quiet)

inputFile = osPath(args.infile)
(inDrive, inPath, inName, inExt) = splitFileCmpnt(inputFile)
if inExt == '': # assume .gpx file, make it so
    statusErrMsg('info', 'args', 'assume input file {} has .gpx extension'.format(inName), quiet)
    inExt= '.gpx'
inputFile = osPath(inDrive + inPath + '/' + inName + inExt)
if all:
    fileglob = inName + inExt
    errMsg('all mode (process all {} files) triggered'.format(fileglob), quiet)
    if verbose: errMsg('process all {} files in {}'.format(fileglob, inDrive + inPath), quiet)
    # note that output file derived from input param so may vary in case from input file name
else:   # test inputFile
    if not accessFile(inputFile, 'fOK'):
        statusErrMsg("fatal", "args", "file does not exist (1): {}".format(inputFile))
        exit(1)
    elif not accessFile(inputFile, 'rOK'):
        statusErrMsg('fatal', 'args', 'file cannot be opened for read access: {}'.format(bsvFile))
        exit(1)
    errMsg('input file: {}'.format(inputFile), quiet)
if auto:
    errMsg('auto mode (output file name) triggered', quiet)
    if verbose: errMsg('output file derived from input file name', quiet)
    # note that output file derived from input param so may vary in case from input file name
    (outDrive, outPath, outName, outExt) = splitFileCmpnt(inputFile)
    outputFile = osPath(outDrive + outPath + '/' + outName + '.txt')
elif args.absoutfile:
    outputFile = osPath(args.absoutfile)
    (outDrive, outPath, outName, outExt) = splitFileCmpnt(outputFile)
    if outPath[-1] == '/' or outPath[-1] == '\\':
        outputFile = osPath(outDrive + outPath + outName + outExt)
    else:
        outputFile = osPath(outDrive + outPath + '/' + outName + outExt)
    
elif args.outfile:
    outputFile = osPath(args.outfile)
    (outDrive, outPath, outName, outExt) = splitFileCmpnt(outputFile)
    (inDrive, inPath, inName, inExt) = splitFileCmpnt(inputFile)
    outputFile = osPath(inDrive + inPath + '/' + outName + outExt)
if auto or args.outfile or args.absoutfile:
    errMsg('output file: {}'.format(outputFile), quiet)
    if inputFile == outputFile:
        statusErrMsg("fatal", "args", "input and output file names identical")
        exit(1)
    if verbose:
        if not accessFile(outputFile, 'fOK'):
            statusErrMsg("info", "args", "file does not exist (2): {}".format(outputFile), quiet)
        else:
            if not accessFile(outputFile, 'wOK'):
                statusErrMsg("fatal", "args", "file not writeable: {}".format(outputFile))
                exit(1)
            statusErrMsg("warn", "args", "overwriting file: {}".format(outputFile), quiet)

## process gpx file(s)
if all: # process multiple files in directory
    fileCount = 0
    for filename in getFileIter(fileglob, inDrive + inPath,):
        inputFile = osPath(filename)
        (inDrive, inPath, inName, inExt) = splitFileCmpnt(inputFile)
        (outDrive, outPath, outName, outExt) = (inDrive, inPath, inName, inExt)
        outputFile = osPath(outDrive + outPath + '/' + outName + '.txt')
        if inputFile == outputFile:
            statusErrMsg("warn", "args", "input and output file names identical")
            continue
        if verbose:
            if not accessFile(outputFile, 'fOK'):
                statusErrMsg("info", "args", "file does not exist (3): {}".format(outputFile), quiet)
            else:
                if not accessFile(outputFile, 'wOK'):
                    statusErrMsg("error", "args", "file not writeable: {}".format(outputFile))
                    continue
                statusErrMsg("warn", "args", "overwriting file: {}".format(outputFile), quiet)
        if not accessFile(inputFile, 'fOK'):
            statusErrMsg("fatal", "args", "file does not exist (4): {}".format(inputFile))
            exit(1)
        elif not accessFile(inputFile, 'rOK'):
            statusErrMsg('error', 'args', 'file cannot be opened for read access: {}'.format(bsvFile))
            continue
        errMsg('input file : {}'.format(inputFile), quiet)
        errMsg('output file: {}'.format(outputFile), quiet)
        processInputfile(inputFile)
        fileCount += 1
else:   # process single gpx file
    processInputfile(inputFile)

## tidy up
if all:
    errMsg(singural(fileCount, ' file', ' files', '\n', ' processed'), quiet)
errTMsg('{} ending normally ({:06.2f}sec)'.format(getProgName(), crhTimer.timer.stop()), quiet)
