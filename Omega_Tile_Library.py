#!/usr/bin/env python3

import sys
import struct
import os
from PIL import Image, ImageDraw

class OmegaTile:
	image = None
	xOffset = 0
	yOffset = 0
	version = 0
	def __init__(self, image, xOffset, yOffset, version):
		self.image = image
		self.xOffset = xOffset
		self.yOffset = yOffset

class OmegaTileLibrary:

	DEBUG = True

	tileLibraries = {}
	currentColorTable = []

	def setup_colors(self, filename, tileIndex):
		colors = self.loadTileLibrary(filename, tileIndex)
		self.currentColorTable = []
		for cc in colors:
			col = [] # alpha (no transparency)
			for rgb in cc:
				col.append(rgb)
			col.append(0xFF) # nothing is transparent by default
			self.currentColorTable.append(tuple(col))
		self.currentColorTable = tuple(self.currentColorTable)
	
	def decompressRLE(self, data):
		buf = []
		offset = 0
		while offset < len(data):
			b = data[offset]
			offset += 1
			if offset == len(data):
				break
			if b & 0x80:
				count = (256 - b)
				while count >= 0:
					buf.append(data[offset])
					count -= 1
				offset += 1
			else:
				count = b
				while count >= 0:
					buf.append(data[offset])
					offset += 1
					if offset == len(data):
						break
					count -= 1
		return bytes(buf)
	
	def processEntry(self, indent, index, entries,entryCount,blobData, inputY, inputX, img):
		entryStart = entries[index]
		if index + 1 < entryCount:
			data = blobData[entryStart:entries[index+1]]
		else:
			data = blobData[entryStart:]
		height,yOffset,xOffset,widthInBytes,version = struct.unpack('>hhhBB', data[:8])
		inputX -= xOffset
		data = data[8:]
		if version == 0 or version == 1: # 4 planes: 4-bit color
			inputY -= yOffset
			if self.DEBUG:
				print(' ' * indent + 'Index #%d : Version:%d %dx%d, x:%d,y:%d' % (index, version, widthInBytes * 8, height, inputX,inputY))
			planeOffset = widthInBytes * height
			bitsPerPixel = 4
			if not img:
				img = Image.new('RGBA', (widthInBytes * 8, height), color = 'white')
				inputY = 0
				inputX = 0
			draw = ImageDraw.Draw(img)
			for y in range(0, height):
				for x in range(0, widthInBytes * 8):
					xo = x >> 3
					xm = 1 << (7 - (x & 7))
					col = 0
					for plane in range(0, bitsPerPixel):
						if data[y * widthInBytes + (x >> 3) + plane * planeOffset] & xm:
							col |= 1 << plane
					draw.point([(x + inputX, y + inputY)], self.currentColorTable[col])
		elif version == 2 or version == 3: # 5 planes: 1-bit mask, 4-bit color
			inputY -= yOffset
			if self.DEBUG:
				print(' ' * indent + 'Index #%d : Version:%d %dx%d x:%d,y:%d' % (index, version, widthInBytes * 8, height, inputX,inputY))
			planeOffset = widthInBytes * height
			bitsPerPixel = 5
			if not img:
				img = Image.new('RGBA', (widthInBytes * 8, height), color = 'white')
				inputY = 0
				inputX = 0
			draw = ImageDraw.Draw(img)
			for y in range(0, height):
				for x in range(0, widthInBytes * 8):
					xo = x >> 3
					xm = 1 << (7 - (x & 7))
					col = 0
					for plane in range(0, bitsPerPixel):
						if data[y * widthInBytes + (x >> 3) + plane * planeOffset] & xm:
							col |= 1 << plane
					c = self.currentColorTable[col >> 1]
					if col & 1:
						c = (c[0],c[1],c[2],0x00)
					draw.point([(x + inputX, y + inputY)], (c))
		elif version == 5: # RLE compressed 4-bit/pixel image, no planes
			inputY -= yOffset
			if self.DEBUG:
				print(' ' * indent + 'Index #%d : Version:%d %dx%d, x:%d,y:%d' % (index, version, widthInBytes * 8, height, inputX,inputY))
			data = self.decompressRLE(data)
			if len(data) != height * int(widthInBytes * 8 / 2):
				print(' ' * indent + '### WRONG LENGTH %d != %d ###' % (len(data), height * int(widthInBytes * 8 / 2)))
				sys.exit(0)
			if not img:
				img = Image.new('RGBA', (widthInBytes * 8, height), color = 'white')
				inputY = 0
				inputX = 0
			draw = ImageDraw.Draw(img)
			for y in range(0, height):
				for x in range(0, widthInBytes * 8):
					col = data[y * int(widthInBytes * 8 / 2) + (x >> 1)]
					if (x & 1) == 0:
						col >>= 4
					col &= 0xF
					draw.point([(x + inputX, y + inputY)], self.currentColorTable[col])
		elif version == 7: # skip-header: 4 planes: 4-bit color
			inputY -= yOffset
			if self.DEBUG:
				print(' ' * indent + 'Index #%d : Version:%d %dx%d, x:%d,y:%d' % (index, version, widthInBytes * 8, height, inputX,inputY))
			imgOffset,planeSize = struct.unpack('>hh', data[:4])
			planeCount = int((len(data) - 4 - imgOffset) / planeSize)
			if not img:
				img = Image.new('RGBA', (widthInBytes * 8, height), color = 'white')
				inputY = 0
				inputX = 0
			draw = ImageDraw.Draw(img)
			lines = []
			for plane in range(0,planeCount):
				compressedData = data[4:4+imgOffset]
				planeData = data[4 + imgOffset + plane * planeSize:]
				poffset = 0
				offset = 0
				lineCount = 0
				newLine = True
				while offset < len(compressedData):
					if newLine:
						newLine = False
						output = []
						outputMask = []
					b = compressedData[offset]
					offset += 1
					if b == 0x00: # line end marker
						newLine = True
						str = ''
						for a in output:
							str += ('0' * 8 + bin(a)[2:])[-8:]
						while len(str) < widthInBytes * 8:
							str += '0'
						while lineCount >= len(lines):
							lines.append(['','','',''])
						lines[lineCount][plane] = str
						lineCount += 1
						continue
					clow6 = b & 0x3F
					codeType = b >> 6
					if codeType == 0: # 0x00…0x3F
						for _ in range(0,b):
							output.append(0x00)
							outputMask.append(0x00)
					elif codeType == 1: # 0x40…0x7F
						for i in range(0,clow6):
							output.append(planeData[i+poffset])
							if i+offset < len(compressedData):
								outputMask.append(compressedData[i+offset])
						poffset += clow6
						offset += clow6
					elif codeType == 2: # 0x80…0xBF
						for i in range(0,clow6):
							output.append(planeData[poffset])
							outputMask.append(0xFF)
						poffset += 1
					elif codeType == 3: # 0xC0…0xFF
						for i in range(0,clow6):
							if i+offset < len(planeData):
								output.append(planeData[i+poffset])
							else:
								output.append(0x00)
							outputMask.append(0xFF)
						poffset += clow6
			for y in range(0,len(lines)):
				for x in range(0,len(lines[y][0])):
					col = 0
					for plane in range(0,planeCount):
						if lines[y][plane][x] == '1':
							col |= 1 << plane
					alpha = 0
					if col != 0:
						alpha = 255
					c = self.currentColorTable[col]
					draw.point([(x + inputX, y + inputY)], (c[0],c[1],c[2],alpha))
		elif version == 9: # multi-element
			elementCount = yOffset >> 8
			yOffset &= 0xFF
			inputY -= yOffset
			if self.DEBUG:
				print(' ' * indent + 'Index #%d : Version:%d %dx%d x:%d,y:%d' % (index, version, widthInBytes * 8, height, inputX, inputY))
			for element in range(0, elementCount):
				subIndex,yOffs,xOffs = struct.unpack('>BBH', data[element * 4:element * 4+4])
				if self.DEBUG:
					print(' ' * indent + ' Sub Index #%d : x:%d,y:%d' % (subIndex,inputX + xOffs,inputY + yOffs))
				self.processEntry(indent + 2, subIndex, entries,entryCount,blobData, inputY + yOffs,inputX + xOffs, img) # "render" at Y=0, X=0
		elif version == 10: # color palette
			col = {}
			for index in range(0, len(data), 4):
				col[data[index]] = (data[index+1],data[index+2],data[index+3])
			if self.DEBUG:
				print(' ' * indent + 'Index #%d : PALETTE %s' % (index, col))
			colors = []
			for i in col:
				colors.append(col[i])
			return colors
		else:
			print(' ' * indent + '### Unknown Index #%2d : Version:%d %dx%d, x:%+d,y:%+d len:%d %s' % (index, version, widthInBytes * 8, height, xOffset,yOffset,len(data), binascii.hexlify(data).decode('utf8')))
		if img != None:
			return OmegaTile(img, xOffset, yOffset, version)
		else:
			return None
	
	
	def loadTileLibrary(self, filename, tileIndex=-1):
		data = open('./STARFLIG.HT/' + filename,'rb').read()
		offset = 0
		magic,fileSize,entryCount = struct.unpack('>4sLH', data[offset:offset+10])
		if magic != b'TLBR':
			print('Magic is not TLBR, it is %s' % magic)
			sys.exit(1)
		if fileSize != len(data):
			print('File size in the header does not match the actual file size (%d != %d)' % (fileSize, len(data)))
		if entryCount & 0x8000:
			entryCount &= 0x7FFF
			print('Huffman encoded data, TABLE.DEC is needed.')
			sys.exit(0)
		entryCount += 1
		offset += struct.calcsize('>4sLH')
		if self.DEBUG:
			print('%s has #%d entries' % (filename,entryCount-1))
		entryListSize = struct.calcsize('>%dI' % entryCount)
		entries = list(struct.unpack('>%dI' % entryCount, data[offset:offset+entryListSize]))
		offset += entryListSize
		# the entry offsets are relative to the end of the header and the upper word is ignored
		entries = [(entry & 0xFFFF) + offset for entry in entries]
		if self.DEBUG:
			print(entries)

		if tileIndex >= 0:
			if tileIndex >= entryCount - 1:
				printf('tileIndex %d > entryCount-1 %d' % (tileIndex, entryCount-1))
				return
			return self.processEntry(0, tileIndex, entries,entryCount,data , 0,0, 0) # "render" at Y=0, X=0
		l = []
		for index in range(0, entryCount-1):
			img = self.processEntry(0, index, entries,entryCount,data , 0,0, 0) # "render" at Y=0, X=0
			l.append(img)
		return l
	
	def __init__(self, tlbFiles):
		for filename in tlbFiles:
			if filename == 'CREDITS.TLB':
				self.setup_colors(filename, 0)
			elif filename == 'SPLASH.TLB':
				self.setup_colors(filename, 0)
			else:
				self.setup_colors('ALWAYS.TLB', 0)
			self.tileLibraries[filename] = self.loadTileLibrary(filename)

	def __getitem__(self, filename):
		return self.tileLibraries[filename]

if True:
	tlbFiles = []
	for filename in os.listdir('./STARFLIG.HT'):
		if filename.endswith('.TLB'):
			tlbFiles.append(filename)
	tileLibraries = OmegaTileLibrary(tlbFiles)
	for filename in tileLibraries.tileLibraries:
		tileList = tileLibraries.tileLibraries[filename]
		print('# %s' % filename)
		basename = os.path.splitext(filename)[0]
		try:
			os.mkdir(basename)
		except:
			pass
		for index in range(len(tileList)):
			tile = tileList[index]
			if not tile: # unused tile
				continue
			if isinstance(tile, dict):
				img = tile['IMG']
				xOffset = tile['X']
				yOffset = tile['Y']
				if isinstance(img, Image.Image):
					print('#%d [%d] %s %s' % (index, tile['VERSION'], img.size, (xOffset, yOffset)))
					# using image transform method
					#img = img.transform((16, 16), Image.AFFINE, data =[1,0,-xOffset, 0,1,-(16-yOffset)])
					img.save('./AA/%d.png' % index)
			else:
				print(tile)
				pass
				