#!/usr/bin/env python3

import sys
import struct
import binascii
import os

def processFile(filename):
	data = open(filename,'rb').read()
	offset = 0
	magic,fileSize,entryCount = struct.unpack('>4sLL', data[offset:offset+12])
	if magic != b'TEXT':
		print('Magic is not TEXT, it is %s' % magic)
		sys.exit(1)
	if fileSize != len(data):
		print('File size in the header does not match the actual file size (%d != %d)' % (fileSize, len(data)))
	offset += struct.calcsize('>4sLL')
	print('%s has #%d entries' % (filename,entryCount))
	entryListSize = struct.calcsize('>%dI' % entryCount)
	entries = list(struct.unpack('>%dI' % entryCount, data[offset:offset+entryListSize]))
	offset += entryListSize
	
	for index in range(0, entryCount):
		entryStart = entries[index]
		if index + 1 < entryCount:
			entryData = data[entryStart:entries[index+1]]
		else:
			entryData = data[entryStart:]
		print('#%d: [%s]' % (index, entryData.decode('utf8')))
	print()

basepath = "./STARFLIG.HT/"
for filename in os.listdir(basepath):
	if filename.endswith(".BTX"):
		processFile(basepath+filename)
