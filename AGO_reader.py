#!/usr/bin/env python3

import sys
import struct
import binascii
import os

def loadBlock(data, offset):
	headerID,length = struct.unpack('>2L', data[offset:offset+8])
	print('### %#06lx #%ld %ld' % (offset,headerID,length))
	offset += 8
	if headerID == 1003: # the 1003 segment is a BSS segment with no data
		length = 0
	offset += length * 4
	headerID, = struct.unpack('>L', data[offset:offset+4])
	print('### %#06lx #%ld' % (offset, headerID))
	offset += 4
	# 1004 = reloc data
	if headerID != 1010:
		length, = struct.unpack('>L', data[offset:offset+4])
		offset += 4
		while length != 0:
			blockIndex, = struct.unpack('>L', data[offset:offset+4])
			offset += 4
			print(blockIndex, struct.unpack('>%dL' % length, data[offset:offset+4 * length]))
			offset += 4 * length
			length, = struct.unpack('>L', data[offset:offset+4])
			offset += 4
		headerID, = struct.unpack('>L', data[offset:offset+4])
		print('### %#06lx #%ld' % (offset, headerID))
		offset += 4
	return offset

def processFile(filename):
	data = open(filename,'rb').read()
	fileLength = len(data)
	print('File length = %#06lx' % fileLength)
	offset = 0
	header = struct.unpack('>8L', data[offset:offset+32])
	offset += 32
	if header[0] != 1011:
		print('Header type is not 1011, it is %d' % header[0])
		sys.exit(1)
	print(header)

	offset = loadBlock(data, offset)
	offset = loadBlock(data, offset)
	offset = loadBlock(data, offset)
	headerID,length = struct.unpack('>2L', data[offset:offset+8])
	print('### %#06lx #%ld %ld' % (offset,headerID,length))
	offset += 8
	length += 1
	print(struct.unpack('>%dL' % length, data[offset:offset+4 * length]))
	offset += 4 * length
	magic, = struct.unpack('>L', data[offset:offset+4])
	offset += 4
	if magic == 0xabcdef67:
		addBlockSize, = struct.unpack('>L', data[offset:offset+4])
		offset += 4
		print('### %#06lx #%#lx %ld' % (offset-8, magic, addBlockSize))
	
#	headerID, = struct.unpack('>L', data[offset:offset+4])

	print()

basepath = "./STARFLIG.HT/"
processFile(basepath+'STARFLT.AGO')
