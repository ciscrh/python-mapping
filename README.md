# python-mapping
Mapping command line scripts

These mapping utilities are command line scripts for processing GPX XML data, latitude & longitude readings (Lat/Lon), & OS National Grid References (NGR). All the scripts have many optional arguments for fine tuning their behaviour. The scripts make use of several of my custom modules, including crhGPX and crhMap, with the latter being derived from Python scripts produced by others. These two custom modules can be used to write other mapping scripts.

gpxRdngs.py
-----------
Satellite navigation (satnav) devices typically use GPX XML data to import and export route data. I use my satnav on walks & it generates waypoint data at the rate of about one reading per second whilst in motion. My current device  generates a gpx file of size about 2000 waypoints/100kB per hour of walking. The current script is the result of a development process lasting several months.

GPX files have far more data than I need for my purposes, which include importing them into the OS Maps application for showing the routes overlaid onto OS mapping. This application currently has a limit of 2MB file size/3000 waypoints for GPX files used to import routes; the limits were much lower when I originally developed the gpxRdngs script. The OS Maps application does not provide a mechanism for trimming GPX files to satify their limits, advising users to use third party applications for this functionality. I wanted to retain more control on how my GPX data was trimmed to size, which was the why the script was written originally.

The script offers several functions:
1. Reduce the number of waypoints & simplify the GPX data.
2. Output summary of GPX data & route statistics.
3. Output simplified GPX XML data.
4. Output bar separated value (BSV) records for each waypoint, including National Grid References.
5. Fine-tuning of how the GPX data is processed. 
6. Provide an estimate of actual ascent for the route.

All the output can be output to screen, file or both. The script includes a batch mode to process multiple GPX files. The NGR data is generated for my convenience; UK maps are not optimised for using latitude/longitude readings.

The default values of the many optional arguments are set to those which experimentation has shown give the best results for my requirements of analysing hill walks lasting several hours.

The estimate of ascent is produced because personal satnav devices usually give greatly over-estimated values for this statistic. It's probably a result of too many waypoints and the inherent large variation of elevation values between successive waypoints. In my experience satnav devices are reasonably accurate in location (East & North values), once they have achieved their initial fix, but much more suspect in their elevation data.

latLon2Ngr.py
-------------
This script takes a single latitude/longitude reading as an input argument and generates the corresponding NGR value. Alternatively, it accepts a file of CSV/BSV records and generates the corresponding list of NGR values, outputting them to screen, file or both. It was written to satisfy a specific requirement. The output file gives BSV or CSV records, as required.

ngrLatlon.py
------------
This is a simple general conversion script for processing Lat/Lon readings to NGR, & vice versa. It accepts a single Lat/Lon or NGR input argument & outputs the corresponding NGR or Lat/Lon as output. Alternatively it accepts a file of CSV/BSV Lat/Lon readings or NGR values and outputs CSV/BSV records, as required.
