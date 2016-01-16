# latLon2Ngr.py -- convert lat/long readings to NGR
# v0.95 crh 28-dec-15 -- under development
# v1.02 crh 31-dec-15 -- intial release
# v1.10 crh 16-jan-16 -- minor mods & setParser() added

# written on a windows platform using python v2.7

#!/usr/local/bin/python

import argparse
import re
import csv
from sys import stdout, stderr, exit

from crhDebug import *  # debug & messaging
from crhFile import *   # file handling
from crhString import * # string utilities
import crhTimer         # timer
import crhMap           # mapping utilities

## essential variables
progName = 'latLon2Ngr'
crhMap.fatalException = False   # handle invalid lat/lon values
brief = False   # generate reduced output data
extend = False  # generate extended output data
quiet = False   # less output (quiet & verbose are not mutually exclusive)
verbose = False # more output
bsv = True      # generate bar separated value records
auto = False    # output file name based on input file name (.txt extension)
autoExt = '.txt'
inputFile = None
outputFile = None
outputH = None
precision = 8   # ngr precision (default: medium precision)
startField = 1  # file record start field for lat/lon values (default: 1)
lineTtl = ignoreTtl = 0

## define functions
def tuple2csv(tpl):
    '''
    return csv string generated from tuple of string values
    '''
    csv = ''
    for value in tpl:
        if ',' in value:
            csv += '"' + value + '",'
        else:
            csv += value + ','
    return csv[:-1]

def tuple2bsv(tpl):
    '''
    return bsv string generated from tuple of string values
    '''
    csv = ''
    for value in tpl:
        csv += value + '|'
    return csv[:-1]

def setParser():
    '''
    set up argparser object & return it
    '''
    parse = argparse.ArgumentParser(description="convert lat/long readings to NGR")
    inputMode = parse.add_mutually_exclusive_group(required = True) # use either -i or -l
    inputMode.add_argument('-i', '--input', action="store", dest="infile",
        help="input filename (eg: d:\\data\\in.bsv)", default='')
    inputMode.add_argument('-l', '--latlon', action="store", dest="latlon",
        help="input lan/lon readings (eg: 53.3399,-1.7774)", default = '')
    outfile = parse.add_mutually_exclusive_group() # use either one or none of -o, -O, -a & -A
    outfile.add_argument('-o', '--output', action="store", dest="outfile",
        help="relative output filename (eg: out.txt)")
    outfile.add_argument('-O', '--Output', action="store", dest="absoutfile",
        help="full output filename path (eg: d:\\out.txt)")
    outfile.add_argument('-a', '--auto', action="store_true", dest="automode",
        help="use output file derived from input file name")
    outputLevel = parse.add_mutually_exclusive_group() # use either one or none of -b & -e
    outputLevel.add_argument('-b', '--brief', action="store_true", dest="briefmode",
        help="brief output data generated")
    outputLevel.add_argument('-e', '--extend', action="store_true", dest="extendmode",
        help="extended output data generated")
    parse.add_argument('-c', '--csv', action="store_true", dest="csvmode",
        help="generate csv output records (default: bsv records)")
    parse.add_argument('-s', '--start', action="store", dest="startfield", type=int,
        help="file record start field (lat)")
    parse.add_argument('-p', '--precision', action="store", dest="precisionmode",
        help="set national grid reference precision", choices=['l','m','h'], default='m')
    parse.add_argument('-q', '--quiet', action="store_true", dest="quietmode",
        help="suppress some program messages")
    parse.add_argument('-v', '--verbose', action="store_true", dest="verbosemode",
        help="generate additional program messages")
    return parse

def setInputFile():
    '''
    set & check input file
    '''
    global inputFile
    inputFile = osPath(args.infile)
    (inDrive, inPath, inName, inExt) = splitFileCmpnt(inputFile)
    if inExt == '': # no extension given so give it one
        if bsv:
            statusErrMsg('info', 'args', 'assume input file {} has .bsv extension'.format(inName), quiet)
            inExt= '.bsv'
        else:
            statusErrMsg('info', 'args', 'assume input file {} has .csv extension'.format(inName), quiet)
            inExt= '.csv'
    inputFile = osPath(inDrive + inPath + '/' + inName + inExt)
    if not accessFile(inputFile, 'fOK'):
        statusErrMsg("fatal", "args", "file does not exist: {}".format(inputFile))
        exit(1)
    elif not accessFile(inputFile, 'rOK'):
        statusErrMsg('fatal', 'args', 'file cannot be opened for read access: {}'.format(bsvFile))
        exit(1)
    errMsg('input file: {}'.format(inputFile), quiet)

def setOutputFile():
    '''
    set & check output file
    '''
    global outputFile
    if auto:
        errMsg('auto mode (output file name) triggered', quiet)
        if verbose: errMsg('output file derived from input file name', quiet)
        # note that output file derived from input param so may vary in case from input file name
        (outDrive, outPath, outName, outExt) = splitFileCmpnt(inputFile)
        outputFile = osPath(outDrive + outPath + '/' + outName + autoExt)
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
                statusErrMsg("info", "args", "file does not exist: {}".format(outputFile), quiet)
            else:
                if not accessFile(outputFile, 'wOK'):
                    statusErrMsg("fatal", "args", "file not writeable: {}".format(outputFile))
                    exit(1)
                statusErrMsg("warn", "args", "overwriting file: {}".format(outputFile), quiet)
    elif verbose:
        errMsg('no output file specified', quiet)

def processInputFile(inputFile, lonField = 0):
    '''
    process lat/lon input file
    assumed in csv or bsv format
    extracts fields lonField & lonfield +1 to calculate east, west & ngr values
    returns tuple of tuples, total line count and ignored line count
    actual elements in tuples depends on which of brief, standard (default) or extended is set
    '''
    lineCount = ignoreCount = 0
    lineLst = list()
    currentLineList = list()
    processedLineLst = list()
    latLonLst = list()
    inputLst = list()
    bsvInput = True
    for line in fileLineGen(inputFile): # crude bsv/csv check
        bsvInput = '|' in line
        if not bsvInput:
            if not ',' in line:
                statusErrMsg('fatal', 'processInputFile', 'unable to process input file: {}'.format(inputFile))
                exit(1)
        if bsvInput:
            errMsg('bsv input file...', quiet)
            sepChar = '|'
        else:
            errMsg('csv input file...', quiet)
            sepChar = ','
        break
    with open(inputFile, 'rb') as f:
        inputReader = csv.reader(f, delimiter = sepChar)
        for lineLst in inputReader:
            lineCount += 1
            lineTpl = tuple(lineLst)
            if not brief:
                currentLineList = lineLst
            if len(lineTpl) > startField:
                latLon = [float(lineTpl[lonField - 1]), float(lineTpl[lonField])]
                eastWest = crhMap.wgs2osgb(latLon)
                try:
                    ngr = crhMap.osgb2ngr(eastWest, precision)
                except RuntimeError as re:
                    if verbose:
                        errMsg('NGR >>>> Invalid input (line {})!'.format(lineCount), quiet)
                    ngr = 'n/a'
                if extend:
                    currentLineList.extend([str(eastWest[0]), str(eastWest[1]), ngr])
                elif brief:
                    currentLineList = [lineTpl[lonField - 1], lineTpl[lonField], ngr]
                else:
                    currentLineList.append(ngr)
                processedLineLst.append(tuple(currentLineList))
            else:
                ignoreCount += 1
                continue
    return tuple(processedLineLst), lineCount, ignoreCount

def processOutputFile(lineLst):
    '''
    put contents of lineLst into output file
    '''
    global outputH
    outputH = openFile(outputFile, 'wt')
    if outputH is None:
        statusErrMsg('fatal', 'processOutputFile()', 'error opening output file {}'.format(outputFile))
        exit(1)
    else:
        statusErrMsg('info', 'processOutputFile()', 'output file opened: {}'.format(outputFile), quiet)
    for line in lineLst:
        if bsv:
            outputH.write(tuple2bsv(line) + '\n')
        else:
            outputH.write(tuple2csv(line) + '\n')
    outputH.close()
    outputH = None

## main program
setProgName(progName)
errTMsg('{} -- process latitude, longitude data to provide OS NGR data'.format(getProgName()), quiet)

## process arguments
parser = setParser()
args = parser.parse_args()
quiet = args.quietmode
verbose = args.verbosemode
brief = args.briefmode
extend = args.extendmode
auto = args.automode

if verbose:
    errMsg('verbose mode set', quiet)
if args.csvmode and args.infile != '':
    bsv = False
    errMsg('csv mode set', quiet)
    if verbose:
        errMsg('output csv records', quiet)
elif args.infile != '':
    errMsg('bsv mode set (default)', quiet)
    if verbose:
        errMsg('output bsv records', quiet)
if brief:
    errMsg('brief mode set', quiet)
    if verbose:
        errMsg('output limited field records', quiet)
elif extend:
    errMsg('extended mode set', quiet)
    if verbose:
        errMsg('output extended field records', quiet)
elif verbose:
    errMsg('output default field records', quiet)
if args.startfield:
    startField = args.startfield
    errMsg('start field set', quiet)
if verbose:
    if startField == 1:
        errMsg('file record start field for lat/lon values is 1 (default)', quiet)
    else:
        errMsg('file record start field for lat/lon values is {}'.format(startField), quiet)
if args.precisionmode == 'l':
    precision = 6
    errMsg('low ngr precision set', quiet)
    if verbose:
        errMsg('national grid reference precision is 100m', quiet)
elif args.precisionmode == 'h':
    precision = 10
    errMsg('high ngr precision set', quiet)
    if verbose:
        errMsg('national grid reference precision is 1m', quiet)
else:
    errMsg('medium ngr precision set (default)', quiet)
    if verbose:
        errMsg('national grid reference precision is 10m', quiet)
if args.infile != '':   # input file (i) argument provided
    setInputFile()
    setOutputFile()

## process data
errMsg('')

if args.latlon != '':   # lat/lon (l) argument provided
    errMsg('single lat/log reading provided...', quiet)
    latLon = args.latlon.split('|')
    if len(latLon) == 1:    # not bsv record
        latLon = args.latlon.split(',')
        if len(latLon) == 1:    # not csv record either
            statusErrMsg('fatal', 'args', 'lat/lon value must be either a csv or bsv pair: {}'.format(args.latlon))
            exit(1)
    latLon = tuple([float(latLon[0]), float(latLon[1])])
    errMsg('Lat, Lon   >>>> {}'.format(latLon))
    eastWest = crhMap.wgs2osgb(latLon)
    msg('East, West >>>> {}'.format(eastWest), quiet)
    try:
        ngr = crhMap.osgb2ngr(eastWest, precision)
        msg('NGR        >>>> {}'.format(ngr))
    except RuntimeError as re:
        msg('NGR        >>>> Invalid input!')
else:   # input file argument provided
    processed, lineTtl, ignoreTtl = processInputFile(inputFile, startField)
    if outputFile is None:
        msg('\n>>>>no output file specified...')
        for line in processed:
            if bsv:
                msg(tuple2bsv(line))
            else:
                msg(tuple2csv(line))
    else:   # output to stdErr (possibly) & then to file
        if verbose: # output to stdErr
            errMsg('')
            for line in processed:
                if bsv:
                    errMsg(tuple2bsv(line))
                else:
                    errMsg(tuple2csv(line))
        processOutputFile(processed)    # output to file

## tidy up
if args.infile != '':
    errMsg(singural(lineTtl, ' file line', ' file lines', '\n', ' processed'), quiet)
    if ignoreTtl:
        errMsg(singural(lineTtl, ' file line', ' file lines', '\n', ' ingored'), quiet)
errMsg('')
errTMsg('{} ending normally ({:06.2f}sec)'.format(getProgName(), crhTimer.timer.stop()), quiet)
