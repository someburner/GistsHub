#!/usr/bin/env python
# coding=utf-8
#
# Converts netxml files from Kismet Newcore into KML or KMZ files for Google Earth
#
# Author: Patrick Salecker
# URL: http://www.salecker.org/software/netxml2kml/en
# Last modified: 13.06.2011

import os
import time
import zipfile

import xml.parsers.expat
import optparse

class WirelessNetwork:
	def __init__(self,type,firsttime,lasttime):
		self.type=type
		self.firsttime=firsttime
		self.lasttime=lasttime
		self.bssid=""
		self.manuf=""
		self.ssid=[]
		self.freqmhz={}
		self.maxrate=0
		self.maxseenrate=0
		self.packets={}
		self.snr={} # Signal-to-noise ratio
		self.datasize=0
		self.channel=0
		self.carrier=""
		self.bsstimestamp=0
		self.gps={}
		self.ipaddress={}
	
	def get_from_ssid(self,key):
		result=[]
		for ssid in self.ssid:
			if key in ssid and ssid[key]!="":
				if type(ssid[key])!=type({}):
					return ssid[key]
				else:
					for bla in ssid[key]:
						if bla not in result:
							result+=[bla,]
		if len(result)>0:
			return result
		else:
			return ""
		
	def update(self,new):
		"""Update a network
		Compare a existing network with a new and update the existing
		"""
		if len(self.gps)==0 and len(new.gps)>0:
			self.gps=new.gps
		return True
			
KML_PLACEMARK="""
<Placemark><styleUrl>#%s</styleUrl>%s
<Point><coordinates>%s,%s</coordinates></Point>
<description><![CDATA[
SSID: %s<br />
MAC: %s<br />
Manuf: %s<br />
Type: %s<br />
Channel: %s<br />
Encryption: <FONT color=%s>%s</FONT><br />
Last time: %s<br />
GPS: %s,%s]]></description></Placemark>
"""

KML_FOLDER = """
<Folder>
<name>%s: %s APs</name>
<Style id="%s"><IconStyle><scale>0.5</scale>
<Icon>")
<href>http://files.salecker.org/netxml2kml/images/%s.gif</href>
</Icon></IconStyle></Style>
%s
</Folder>
"""

class netxml:
	def __init__(self):
		self.networks={}
		self.outputname=""
		self.target=None
		self.disable_names = False

	def main(self):
		usage=self.main_usage()
		parser = optparse.OptionParser(usage)
		parser.add_option("-o", dest="outputname",
			help="Filename without extension")
		parser.add_option("--kml", dest="kml", action="store_true",
			help="Create a KML file for Google Earth <outputname>.kml")
		parser.add_option("--kmz", dest="kmz", action="store_true",
			help="Create a KMZ file for Google Earth <outputname>.kmz")
		parser.add_option("--disable-names", dest="names", action="store_true",
			help="Disable names in KML/KMZ")
		
		(options, args) = parser.parse_args()
				
		# Input
		if len(args)>0:
			for filename in args:
				if os.path.isdir(filename):
					self.parse_dir(filename)
				elif os.path.isfile(filename):
					self.parse(filename)
				else:
					print "Invalid name: %s"%filename
		if options.outputname==None:
			print "Output name not defined, try '-h'"
		else:
			self.outputname=options.outputname
			print "Outputfile: %s.*" % self.outputname
			
		print ""
		if options.names is True:
			self.disable_names = True
		
		# Output
		if len(self.networks)>0:
			if self.outputname!="":
				if options.kml is True:
					self.output_kml()
				if options.kmz is True:
					self.output_kml(kmz=True)
		else:
			print "No networks"
			
	def main_usage(self):
		return """
python netxml [options] [file1] [file2] [dir1] [dir2] [...]
./netxml [options] [dir1] [dir2] [file1] [file2] [...]

Example:
python netxml.py --kmz --kml -o today somefile.netxml /mydir"""
	
	def parse_dir(self,parsedir):
		"""Parse all files in a directory
		"""
		print "Parse .netxml files in Directory:",parsedir
		starttime=time.time()
		files=0
		if not parsedir.endswith(os.sep):
			parsedir+=os.sep
		for filename in os.listdir(parsedir):
			if os.path.splitext(filename)[1]==".netxml":
				self.parse(parsedir + filename)
				files+=1
				
		print "Directory done, %s sec, %s files" % (
			round(time.time()-starttime,2),files)
	
	def parse(self,filename):
		"""Parse a netxml file generated by Kismet Newcore
		"""
		
		self.parser={
			"update":0,
			"new":0,
			"laststart":"",
			"parents":[],
			"wn":None,
			"ssid":None
			}
		
		p = xml.parsers.expat.ParserCreate()
		p.buffer_text=True #avoid chunked data
		p.returns_unicode=False #disabled Unicode support is much faster
		p.StartElementHandler = self.parse_start_element
		p.EndElementHandler = self.parse_end_element
		p.CharacterDataHandler = self.parse_char_data
		if os.path.isfile(filename):
			p.ParseFile(open(filename))
		else:
			print "Parser: filename is not a file:" % filename

		print "Parser: %s, %s new, %s old" % (
			filename,self.parser["new"],self.parser["update"])
	
	def parse_start_element(self,name, attrs):
		"""<name attr="">
		"""
		#print 'Start element:', name, attrs
		if name=="wireless-network":
			self.parser["wn"]=WirelessNetwork(
				attrs["type"],
				attrs["first-time"],
				attrs["last-time"])
		elif name=="essid" and 'cloaked' in attrs:
			self.parser["ssid"]['cloaked']=attrs['cloaked']
		elif name=="SSID":
			self.parser["ssid"]={"encryption":{}}
			
		self.parser["parents"].insert(0,self.parser["laststart"])
		self.parser["laststart"]=name
			
	def parse_end_element(self,name):
		"""</name>
		"""
		#print 'End element:', name
		if name=="wireless-network":
			if self.parser["wn"].bssid in self.networks:
				self.networks[self.parser["wn"].bssid].update(self.parser["wn"])
				self.parser["update"]+=1
			else:
				self.networks[self.parser["wn"].bssid]=self.parser["wn"]
				self.parser["new"]+=1
		elif name=="SSID":
			if len(self.parser["ssid"])>0 and "type" in self.parser["ssid"]:
				if self.parser["parents"][0]=="wireless-network":
					self.parser["wn"].ssid.append(self.parser["ssid"])
			del self.parser["ssid"]
			
		self.parser["laststart"]=self.parser["parents"].pop(0)
			
	def parse_char_data(self,data):
		"""<self.parser["laststart"]>data</self.parser["laststart"]>
		"""
		if data.strip()=="":
			return
		
		if self.parser["parents"][0]=="SSID":
			if self.parser["laststart"]=="encryption":
				self.parser["ssid"]["encryption"][data]=True
			elif self.parser["laststart"] in("type","ssid","essid","max-rate","packets","beaconrate","info"):
				self.parser["ssid"][self.parser["laststart"]]=data
		elif self.parser["parents"][1]=="wireless-network":
			if self.parser["parents"][0]=="gps-info":
				self.parser["wn"].gps[self.parser["laststart"]]=float(data)
			"""elif self.parser["parents"][0]=="packets":
				self.parser["wn"].packets[self.parser["laststart"]]=data
			elif self.parser["parents"][0]=="snr-info":
				self.parser["wn"].snr[self.parser["laststart"]]=data
			elif self.parser["parents"][0]=="ip-address":
				self.parser["wn"].ipaddress[self.parser["laststart"]]=data"""
		elif self.parser["parents"][0]=="wireless-network":
			if self.parser["laststart"]=="BSSID":
				self.parser["wn"].bssid=data
			elif self.parser["laststart"]=="channel":
				self.parser["wn"].channel=int(data)
			elif self.parser["laststart"]=="manuf":
				self.parser["wn"].manuf=data
			"""elif self.parser["laststart"]=="freqmhz":
				self.parser["wn"].freqmhz[data]=True
			elif self.parser["laststart"]=="carrier":
				self.parser["wn"].carrier=data
			elif self.parser["laststart"]=="maxseenrate":
				self.parser["wn"].maxseenrate=data
			elif self.parser["laststart"]=="bsstimestamp":
				self.parser["wn"].bsstimestamp=data
			elif self.parser["laststart"]=="datasize":
				self.parser["wn"].datasize=data"""
			
		
	def output_kml(self,kmz=False):
		"""Output KML for Google Earth
		"""
		print "%s export..." % ("KML" if not kmz else "KMZ")
		#starttime=time.time()
		
		if kmz is True:
			target=CreateKMZ(self.outputname)
		else:
			target=CreateKML(self.outputname)
		
		target.add("<?xml version='1.0' encoding='UTF-8'?>\r\n")
		target.add("<kml xmlns='http://earth.google.com/kml/2.1'>\r\n")
		target.add("<Document>\r\n")
		target.add("<name>netxml2kml</name>\r\n")
		target.add("<open>1</open>")
		
		count={"WPA":0,"WEP":0,"None":0,"Other":0}
		folders, route = self.output_kml_fill_folders(count)

		for crypt in ("WPA","WEP","None","Other"):
			if crypt=="WPA":
				pic="WPA"
			elif crypt=="WEP":
				pic="WEP"
			else:
				pic="Open"
			
			target.add(KML_FOLDER %(
				crypt,
				count[crypt],
				crypt,
				pic,
				"".join(folders[crypt])
			))

			print "%s\t%s" % (crypt,count[crypt])
		
		target.add(self.output_kml_route(route))
		target.add("\r\n</Document>\r\n</kml>")
		target.close()
		
		print "Done. %s networks" % sum(count.values())
		#round(time.time()-starttime,2)
		
	def output_kml_fill_folders(self,count):
		folders={"WPA":[],"WEP":[],"None":[],"Other":[]}
		colors={"WPA":"red","WEP":"orange","None":"green","Other":"grey"}
		route = {}
		for net in self.networks:
			wn=self.networks[net]
			if len(wn.gps)==0:
				continue
			
			essid = wn.get_from_ssid('essid').replace("<","&lt;").replace(">","&gt;").replace("&","&amp;")
			if not self.disable_names:
				name = "<name>%s</name>" % essid
			else:
				name = ""
			encryption=wn.get_from_ssid('encryption')
			crypt=self.categorize_encryption(encryption)
			if len(encryption)!=0:
				encryption.sort(reverse=True)
				encryption=" ".join(encryption)
			
			folders[crypt].append(KML_PLACEMARK %(
				crypt,name,wn.gps['avg-lon'],wn.gps['avg-lat'],
				essid,wn.bssid,wn.manuf,wn.type,
				wn.channel,colors[crypt],encryption,wn.lasttime,
				wn.gps['avg-lat'],wn.gps['avg-lon'],
			))
			count[crypt]+=1
			sec_first = int(time.mktime(time.strptime(wn.firsttime)))
			sec_last = int(time.mktime(time.strptime(wn.lasttime)))
			if sec_last - sec_first < 300:
				route[sec_last] = (wn.gps['avg-lat'],wn.gps['avg-lon'])
			
		return folders, route
		
	def output_kml_route(self, route):
		output = []
		num = 1
		last_second = 0
		output.append("<Folder><name>Routes</name>")
		for second in sorted(route):
			lat, lon = route[second]
			if second - last_second > 1800:
				if len(output) > 1:
					output.append("</coordinates></LineString><name>Route %s (end %s)</name></Placemark>\n" % (num, time.strftime("%a %b %d %H:%M:%S %Y", time.gmtime(last_second))))
					num += 1
				output.append("<Placemark><Style><LineStyle><color>7f00ff00</color><width>3</width></LineStyle></Style><LineString><coordinates>\n")
				
			last_second = second
			output.append("%s,%s \n" % (lon, lat))
		
		output.append("</coordinates></LineString><name>Route %s (end %s)</name></Placemark>\n" % (num, time.strftime("%a %b %d %H:%M:%S %Y", time.gmtime(last_second))))
		output.append("</Folder>")
		return "".join(output)
		
	def categorize_encryption(self,encryption):
		for c in encryption:
			if c.startswith("WPA"):
				return "WPA"
				
		if "WEP" in encryption:
			return "WEP"
		elif "None" in encryption:
			return "None"
		else:
			return "Other"
	
class CreateKML:
	"""Write the KML data direct into a file
	"""
	def __init__(self,outputname):
		self.file=open("%s.kml" % outputname, 'w')
		
	def add(self,data):
		self.file.write(data)
		
	def close(self):
		self.file.close()
		
class CreateKMZ:
	"""Store the KML data in a list and write it into a zipfile in close()
	"""
	def __init__(self,outputname):
		self.data=[]
		self.zip=zipfile.ZipFile("%s.kmz" % outputname, "w")
		
	def add(self,data):
		self.data.append(data)
		
	def close(self):
		zinfo = zipfile.ZipInfo("netxml2kml.kml")
		zinfo.compress_type = zipfile.ZIP_DEFLATED
		self.zip.writestr(zinfo,"".join(self.data))
		self.zip.close()
		
if __name__ == "__main__":
	converter=netxml()
	converter.main()