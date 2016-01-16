# ngrLatLon.py -- convert lat/long readings to NGR, or vice versa
# v0.95 crh 07-jan-16 -- under development, based on latLon2Ngr
# v1.00 crh 15-jan-16 -- initial release

# written on a windows platform using python v2.7

#!/usr/local/bin/python


#### add code to use extend argument
#### by appending input value to output

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
progName = 'ngrLatLon'
crhMap.fatalException = False   # handle invalid lat/lon values
extend = False  # generate extended output data
quiet = False   # less output (quiet & verbose are not mutually exclusive)
verbose = False # more output
bsv = True      # generate bar separated value records, or csv records if false
auto = False    # output file name based on input file name (.txt extension)
inputFile = None
outputFile = None
outputH = None
precision = 8   # output ngr precision (default: medium precision)
lineTtl = ignoreTtl = 0
ngr2LatLon = None   # set True or False when processing input file

gridRef  = re.compile(r'^[A-Za-z]{2}(\d{4}|\d{6}|\d{8}|\d{10})$')

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
            csv += str(value) + ','
    return csv[:-1]

def tuple2bsv(tpl):
    '''
    return bsv string generated from tuple of string values
    '''
    bsv = ''
    for value in tpl:
        bsv += str(value) + '|'
    return bsv[:-1]

def setParser():
    '''
    set up argparser object & return it
    '''
    parse = argparse.ArgumentParser(description="convert lat/long readings to NGR, or vice versa")
    inputMode = parse.add_mutually_exclusive_group(required = True) # use either -i or -l
    inputMode.add_argument('-i', '--input', action = "store", dest = "infile",
        help="input filename (eg: d:\\data\\in.bsv)", default='')
    inputMode.add_argument('-l', '--latlon', action = "store", dest = "latlon",
        help="input lan/lon (eg: 53.3399,-1.7774)", default = '')
    inputMode.add_argument('-n', '--ngr', action = "store", dest = "ngr",
        help="input ngr (eg: SK1491882580)", default = '')
    outfile = parse.add_mutually_exclusive_group() # use either one or none of -o, -O, -a & -A
    outfile.add_argument('-o', '--output', action = "store", dest = "outfile",
        help="relative output filename (eg: out.txt)")
    outfile.add_argument('-O', '--Output', action = "store", dest = "absoutfile",
        help="full output filename path (eg: d:\\out.txt)")
    outfile.add_argument('-a', '--auto', action = "store_true", dest = "automode",
        help="use output file derived from input file name")
    parse.add_argument('-e', '--extend', action="store_true", dest="extendmode",
        help="extended output data generated")
    parse.add_argument('-c', '--csv', action = "store_true", dest = "csvmode",
        help="generate csv output records (default: bsv records)")
    parse.add_argument('-p', '--precision', action = "store", dest = "precisionmode",
        help="set output national grid reference precision", choices = ['l','m','h'], default = 'm')
    parse.add_argument('-q', '--quiet', action = "store_true", dest = "quietmode",
        help="suppress some program messages")
    parse.add_argument('-v', '--verbose', action = "store_true", dest = "verbosemode",
        help = "generate additional program messages")
    return parse

def setInputFile():
    '''
    set & check input file
    '''
    global inputFile
    inputFile = osPath(args.infile)
    (inDrive, inPath, inName, inExt) = splitFileCmpnt(inputFile)
    if inExt == '': # no extension given
        statusErrMsg('fatal', 'args', 'input file {} has no extension'.format(inName), quiet)
        exit(1)
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
                statusErrMsg("info", "args", "file does not exist: {}".format(outputFile), quiet)
            else:
                if not accessFile(outputFile, 'wOK'):
                    statusErrMsg("fatal", "args", "file not writeable: {}".format(outputFile))
                    exit(1)
                statusErrMsg("warn", "args", "overwriting file: {}".format(outputFile), quiet)
    elif verbose:
        errMsg('no output file specified', quiet)

def processInputFile(inputFile):
    '''
    determine whether lat/lon or ngr input file & process it
    assumed in csv or bsv format for lat/lon values
    returns tuple of lat/long values tuples or tuple of ngr values, total line count and ignored line count
    actual elements in tuples depends on whether ngr or lat/long values given in input file
    '''
    global ngr2LatLon
    lineCount = ignoreCount = 0
    lineLst = list()
    currentLineLst = list()
    bsvInput = True
    for line in fileLineGen(inputFile): # crude ngr or lat/lon bsv/csv check
        if gridRef.match(line):
            ngr2LatLon = True
            errMsg('ngr input file...', quiet)
        else:
            ngr2LatLon = False
            bsvInput = '|' in line
            if not bsvInput:
                if not ',' in line:
                    statusErrMsg('fatal', 'processInputFile', 'unable to process input file: {}'.format(inputFile))
                    exit(1)
            if bsvInput:
                errMsg('lat/lon input file (bsv)...', quiet)
                sepChar = '|'
            else:
                errMsg('lat/lon input file (csv)...', quiet)
                sepChar = ','
        break
    if ngr2LatLon:  # process the ngr input file
        for line in fileLineGen(inputFile):
            lineCount += 1
            if gridRef.match(line):
                if crhMap.validNGR(line):
                    latLonTpl = crhMap.osgb2wgs(line)
                    if extend:
                        latLonTpl = (line, str(latLonTpl[0]), str(latLonTpl[1]))
                    else:
                        latLonTpl = (str(latLonTpl[0]), str(latLonTpl[1]))
                else:
                    if verbose:
                        errMsg('East, West >>>> Invalid input ({})'.format(lineCount), quiet)
                    if extend:
                        latLonTpl = (line, 'n/a', 'n/a')
                    else:
                        latLonTpl = ('n/a', 'n/a')
            else:
                ignoreCount += 1
                if extend:
                    latLonTpl = (line, 'n/a', 'n/a')
                else:
                    latLonTpl = ('n/a', 'n/a')
            currentLineLst.append(latLonTpl)
    else:   # process the lan/lon input file
        with open(inputFile, 'rb') as f:
            inputReader = csv.reader(f, delimiter = sepChar)
            for lineLst in inputReader:
                lineCount += 1
                if len(lineLst) == 2:
                    latLonLst = [float(lineLst[0]), float(lineLst[1])]
                    eastWest = crhMap.wgs2osgb(latLonLst)
                    try:
                        outputNgr = crhMap.osgb2ngr(eastWest, precision)
                    except RuntimeError as re:
                        if verbose:
                            errMsg('invalid input (line {}): {}'.format(lineCount, str(lineLst), quiet))
                        outputNgr = 'n/a'
                    if extend:
                        currentLineLst.append((lineLst[0], lineLst[1], outputNgr))
                    else:
                        currentLineLst.append((outputNgr,))
                else:
                    ignoreCount += 1
                    errMsg('invalid input (line {}): {}'.format(lineCount, str(lineLst), quiet))
                    if extend:
                        lineLst.append('n/a')
                        currentLineLst.append(tuple(lineLst))
                    else:
                        currentLineLst.append(('n/a',))
    return tuple(currentLineLst), lineCount, ignoreCount

def processOutputFile(outputLineLst):
    '''
    put contents of outputLineLst into output file
    '''
    global outputH, outputFile, bsv
    outputH = openFile(outputFile, 'wt')
    if outputH is None:
        statusErrMsg('fatal', 'processOutputFile()', 'error opening output file {}'.format(outputFile))
        exit(1)
    else:
        statusErrMsg('info', 'processOutputFile()', 'output file opened: {}'.format(outputFile), quiet)
    for line in outputLineLst:
        if bsv:
            outputH.write(tuple2bsv(line) + '\n')
        else:
            outputH.write(tuple2csv(line) + '\n')
    outputH.close()
    outputH = None

## main program
setProgName(progName)
errTMsg('{} -- process latitude, longitude data to provide OS NGR data, or vice versa'.format(getProgName()), quiet)

## process arguments
parser = setParser()
args = parser.parse_args()
quiet = args.quietmode
errTMsg('{} -- convert latitude, longitude data to OS NGR data, or vice versa'.format(getProgName()), quiet)
verbose = args.verbosemode
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
if extend:
    errMsg('extended mode set', quiet)
    if verbose:
        errMsg('output extended field records', quiet)
elif verbose:
    errMsg('output default field records', quiet)
if args.ngr == '' and args.precisionmode == 'l':
    precision = 6
    errMsg('low ngr precision set', quiet)
    if verbose:
        errMsg('output national grid reference precision is 100m', quiet)
elif args.ngr == '' and args.precisionmode == 'h':
    precision = 10
    errMsg('high ngr precision set', quiet)
    if verbose:
        errMsg('output national grid reference precision is 1m', quiet)
elif args.ngr == '':
    errMsg('medium ngr precision set (default)', quiet)
    if verbose:
        errMsg('output national grid reference precision is 10m', quiet)
else:
    errMsg('ngr precision ignored', quiet)
    if verbose:
        errMsg('ngr precision applies to ngr output only', quiet)
if args.infile != '':   # input file (i) argument provided
    setInputFile()
    setOutputFile()
elif args.automode or args.absoutfile or args.outfile:
    errMsg('output file arguments ignored', quiet)
    if verbose:
        errMsg('output sent to screen (stdout)', quiet)    

## process data
errMsg('')

if args.latlon != '':   # lat/lon (l) argument provided
    errMsg('single lat/lon reading provided...', quiet)
    latLon = args.latlon.split('|')
    if len(latLon) == 1:    # not bsv record
        latLon = args.latlon.split(',')
        if len(latLon) == 1:    # not csv record either
            statusErrMsg('fatal', 'args', 'lat/lon value must be either a csv or bsv pair: {}'.format(args.latlon))
            exit(1)
    latLon = tuple([float(latLon[0]), float(latLon[1])])
    msg('Lat, Lon   >>>> {}'.format(latLon))
    eastWest = crhMap.wgs2osgb(latLon)
    msg('East, West >>>> {}'.format(eastWest), quiet)
    try:
        outputNgr = crhMap.osgb2ngr(eastWest, precision)
        msg('NGR        >>>> {}'.format(outputNgr))
    except RuntimeError as re:
        msg('NGR        >>>> Invalid input!')
elif args.ngr != '':   # ngr (n) argument provided
    errMsg('single ngr provided...', quiet)
    ngr = args.ngr
    msg('NGR          >>>> {}'.format(ngr))
    try:
        eastWest = crhMap.ngr2osgb(ngr)
        msg('East, West   >>>> {}'.format(eastWest), quiet)
    except RuntimeError as re:
        msg('East, West   >>>> Invalid input!')
        eastWest = None
    if eastWest is not None:
        outputLatLon = crhMap.osgb2wgs(ngr)
        msg('Lat, Lon     >>>> {}'.format(outputLatLon))
else:   # input file argument provided
    processed, lineTtl, ignoreTtl = processInputFile(inputFile)
    if outputFile is None:
        msg('\n>>>>no output file specified...')
        for line in processed:
            if not ngr2LatLon:
                if extend:
                    if bsv:
                        msg(tuple2bsv(line))
                    else:
                        msg(tuple2csv(line))
                else:
                    msg(line[0])
            elif bsv:
                msg(tuple2bsv(line))
            else:
                msg(tuple2csv(line))
    else:   # output to stdErr (possibly) & then to file
        if verbose: # output to stdErr
            errMsg('')
            for line in processed:
                if not ngr2LatLon:
                    if extend:
                        if bsv:
                            errMsg(tuple2bsv(line))
                        else:
                            errMsg(tuple2csv(line))
                    else:
                        msg(line[0])
                elif bsv:
                    errMsg(tuple2bsv(line))
                else:
                    errMsg(tuple2csv(line))
        processOutputFile(processed)    # output to file

## tidy up
if args.infile != '':
    errMsg(singural(lineTtl, ' file line', ' file lines', '\n', ' processed'), quiet)
    if ignoreTtl:
        errMsg(singural(ignoreTtl, ' file line', ' file lines', '', ' ignored'), quiet)
errMsg('')
errTMsg('{} ending normally ({:06.2f}sec)'.format(getProgName(), crhTimer.timer.stop()), quiet)
