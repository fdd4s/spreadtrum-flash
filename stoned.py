# StoneD (Stone Depacker) - unpack Unisoc SC6531 stone images (part of UniFlash)
# Created by Luxferre in 2021, released into public domain

import os
import sys
import struct
import lzma
from custlzma.frenchlzma import DecodeurLZMASPD # (for LZMA_SPD decompression)

# common utils

def readFile(fname):
    f = open(fname, 'rb')
    fdata = f.read()
    f.close()
    return fdata

def writeFile(fname, fdata):
    outf = open(fname, 'wb')
    outf.write(fdata)
    outf.close()

# unpack part

CMP_NONE=0
CMP_LZMA_SPRD=1
CMP_LZMA=2

def getCompType(data):
    if (data[0] == 0x5d or data[0] == 0x67) and data[1] == 0:
        return CMP_LZMA
    elif data[0] == 0x5a and data[1] == 0:
        return CMP_LZMA_SPRD
    else:
        return CMP_NONE

def getTblOffset(blocksOffTbl, index):
    tind = index << 2
    return struct.unpack('<L', blocksOffTbl[tind:tind+4])[0]

def unpack_block(blkData, blkPacSize, targetFile):
    print('Extracting %s...' % targetFile)
    blocksOffTbl = None
    compData = blkData
    npacHdr = blkData[:16]
    (npacHdrMagic, npacHdrFlags, compDataSize, lzmaBlocksAmount) = struct.unpack('<LLLL', npacHdr)
    # npacHdrMagic must be CAPN if using offsets
    if npacHdrMagic == 0x4E504143:
        blocksOffTbl = blkData[compDataSize:]
        compData = blkData[getTblOffset(blocksOffTbl,0):]
    else:
        lzmaBlocksAmount = 1
    cType = getCompType(compData)
    assert cType == CMP_LZMA or cType == CMP_LZMA_SPRD, 'Only LZMA compression type is implemented as of now'
    print('Found LZMA blocks: %d, decompressing...' % lzmaBlocksAmount)
    dest = b''
    inSizePure = blkPacSize * 2
    lzmaDec = DecodeurLZMASPD()
    for i in range(lzmaBlocksAmount):
        if blocksOffTbl is not None:
            dataOffset = getTblOffset(blocksOffTbl,i)
        else:
            dataOffset = 0
        compData = blkData[dataOffset:]
        lzData = compData[0:inSizePure]
        if cType == CMP_LZMA_SPRD:
            outdata = lzmaDec.decode(lzData)
            dest += outdata
        else:
            dest += lzma.decompress(lzData, format=lzma.FORMAT_ALONE)
        sys.stdout.write('.')
        sys.stdout.flush()
    writeFile(targetFile, dest)
    print('\n%s decompressed!' % targetFile)

def unpack_section(sectionData, targetDir):
    bzpFileHdr = sectionData[:16]
    (bzpFileHdrMagic, bzpType, blocksOffset, blocksAmount) = struct.unpack('<LLLL', bzpFileHdr)
    # bzpFileHdrMagic must be DRPS or RRPS
    assert bzpFileHdrMagic == 0x53505244 or bzpFileHdrMagic == 0x53505252, 'Invalid BZP header: 0x%X' % bzpFileHdrMagic
    bzpSize = blocksOffset + blocksAmount * 20
    for i in range(blocksAmount):
        blkHdrStart = blocksOffset + i*20
        blkHdr = sectionData[blkHdrStart:blkHdrStart+20]
        (blkHdrMagic, blkId, blkDataOffset, blkPackedSize, blkPacSize) = struct.unpack('<LLLLL', blkHdr)
        # blkHdrMagic must be COLB
        assert blkHdrMagic == 0x424C4F43, 'Invalid BZP block header: 0x%X' % blkHdrMagic
        if bzpSize < blkDataOffset + blkPackedSize:
            bzpSize = blkDataOffset + blkPackedSize
        if blkId == 0x494D4147: # GAMI -> kernel image
            targetFile = targetDir + '/kern.bin'
        elif blkId == 0x75736572: # resu -> user image
            targetFile = targetDir + '/user.bin'
        elif blkId == 0x7253736F: # resources
            targetFile = targetDir + '/rsrc.bin'
        else:
            targetFile = targetDir + ('/blk_%X.bin' % blkId)
        unpack_block(sectionData[blkDataOffset:], blkPacSize, targetFile)

def unpack_stone(fname, targetDir):
    fdata = readFile(fname)
    flen = len(fdata)
    assert flen >= 0x10, 'Input file %s is too small' % fname

    # check for security header
    sectionOffset = 0
    if fdata[0:15] == b'SPRD-SECUREFLAG':
        sectionOffset = 1024
        print('Signed image detected, using section offset %d' % sectionOffset)

    # look for TRAPGAMI header
    startPos = -1
    for i in range(flen):
        if fdata[i:i+8] == b'TRAPGAMI':
            startPos = i
            break
    assert startPos > 0, 'No stone header found in %s' % fname
    print('Stone header found at 0x%X' % startPos)

    psImageEnd = 0xffffffff # PS (protocol station) image is the first in the flash backup and not compressed

    dfcStruct = fdata[startPos+8:startPos+120]
    for i in range(0,112,4):
        targetAddr = struct.unpack('<L', dfcStruct[i:i+4])[0]
        if targetAddr < 0xffffffff:
            if targetAddr < psImageEnd:
                psImageEnd = targetAddr
            print('Target section address found: 0x%X' % targetAddr)
            unpack_section(fdata[sectionOffset+targetAddr:], targetDir)
            print('Section 0x%X unpacked!' % targetAddr)

    if psImageEnd > 0:
        psPath = targetDir + '/ps.bin'
        writeFile(psPath, fdata[:psImageEnd])
        print('Protocol station image %s written!' % psPath)

# main code start

if __name__ == '__main__': # main app start
    from argparse import ArgumentParser
    rootdir = os.path.dirname(os.path.realpath(__file__))
    parser = ArgumentParser(description='StoneD: an opensource Unisoc/Spreadtrum stone image unpacker', epilog='(c) Luxferre 2021 --- No rights reserved <https://unlicense.org>')
    parser.add_argument('file', help='Stone image file to unpack')
    parser.add_argument('-d','--directory', default=None, help='Directory where component files will be written to (defaults to the same where the main stone file resides)')

    args = parser.parse_args()

    imgfile = args.file
    imgdir = os.path.dirname(os.path.realpath(imgfile))
    if args.directory is not None:
        imgdir = os.path.realpath(args.directory)

    print('Unpacking %s to %s' % (imgfile, imgdir))
    unpack_stone(imgfile, imgdir)

