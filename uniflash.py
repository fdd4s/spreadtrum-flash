#!/usr/bin/env python

import usb
import sys, time
import os
import unicmd
import stoned

# global params

UNISOC_VID = 0x1782
UNISOC_PID = 0x4d00
UNISOC_FLASH_BASE_ADDR = 0x10000000
UNISOC_FLASH_BASE_ADDR_OLD = 0x30000000
MAX_PKT_SIZE = 1024
bSize = 512 # read block size
genTimeout = 120000

# all main procedures

def connect(vid, pid):
    while True:
        dev = usb.core.find(idVendor=vid, idProduct=pid)
        sys.stdout.write('.')
        sys.stdout.flush()
        if dev is not None:
            print('\nDevice connected')
            break
        time.sleep(0.1)
    dev.set_configuration()
    cfg = dev.get_active_configuration()
    intf = cfg[(0,0)]
    global bSize
    bSize = intf[0].wMaxPacketSize
    epIn = usb.util.find_descriptor(
        intf,
        custom_match = \
        lambda e: \
            usb.util.endpoint_direction(e.bEndpointAddress) == \
            usb.util.ENDPOINT_IN)
    epOut = usb.util.find_descriptor(
        intf,
        custom_match = \
        lambda e: \
            usb.util.endpoint_direction(e.bEndpointAddress) == \
            usb.util.ENDPOINT_OUT)
    assert epIn is not None
    assert epOut is not None
    return dev, epIn, epOut


def reqonly(packet, fdlBooted = False, noCrc = False):
    packet = unicmd.hdlc_encode(packet, fdlBooted, noCrc)
    dev.write(epOut, packet, genTimeout)

def reqresp(packet, fdlBooted = False, noCrc = False):
    reqonly(packet, fdlBooted, noCrc)
    resp = bytes(dev.read(epIn, bSize, genTimeout))
    return resp

def handshake(fdlBooted = False):
    resp = reqresp(unicmd.cmd_sync(), fdlBooted)
    rcode, rlen, r = unicmd.resp_decode(resp, fdlBooted)
    if len(r):
        print('>', r.decode())
    resp = reqresp(unicmd.cmd_connect(), fdlBooted)
    rcode, rlen, r = unicmd.resp_decode(resp, fdlBooted)
    if len(r):
        print('>', r.decode())

def send_file_to_addr(fname, faddr, fdlBooted = False, flashMode = False, fbs = 1024):
    pSize = MAX_PKT_SIZE
    print('Initializing data transfer...')
    dataCrc = 0
    if flashMode:
        # faddr is our flash offset in this case, and we directly pass the data buffer to the function
        pSize = fbs
        fdata = fname
        flen = len(fdata)
    else:
        f = open(fname, 'rb')
        fdata = f.read()
        f.close()
        flen = len(fdata)
        dataCrc = unicmd.chksum32(fdata)
    resp = reqresp(unicmd.cmd_data_start(faddr, flen, dataCrc), fdlBooted)
    rcode, rlen, r = unicmd.resp_decode(resp, fdlBooted)
    assert rcode == unicmd.BSL_REP_ACK, 'Could not start data transfer, response code is %X' % rcode
    if rcode == unicmd.BSL_REP_LOG:
        print(r)
    print('Starting data transfer...')
    while fdata:
        buf = fdata[:pSize]
        resp = reqresp(unicmd.cmd_data_send(buf), fdlBooted)
        rcode, rlen, r = unicmd.resp_decode(resp, fdlBooted)
        assert rcode == unicmd.BSL_REP_ACK, 'Something is wrong and response code is %X, block is %s' % (rcode, buf.hex())
        fdata = fdata[pSize:]
        sys.stdout.write('.')
        sys.stdout.flush()
    print('\nEnding data transfer...')
    resp = reqresp(unicmd.cmd_data_end(), fdlBooted)
    rcode, rlen, r = unicmd.resp_decode(resp, fdlBooted)
    if not flashMode or (rcode != unicmd.BSL_FLASH_CFG_ERROR and rcode != unicmd.BSL_WRITE_ERROR and rcode != 0xFF): # on flashing, ignore 0xA2, 0xA4 and 0xFF errors
        assert rcode == unicmd.BSL_REP_ACK, 'Could not finalize data transfer, response code is %X' % rcode
    print('Data transfer successful')

# readback code implementation

def read_partdata(partid, size, offset):
    t = b''
    reqonly(unicmd.cmd_read_flash(partid, size, offset), True)
    while True:
        xr = bytes(dev.read(epIn, bSize, genTimeout))
        t += xr
        if len(xr) < bSize:
            break
    return t

def read_partition(partid, partsize, partoffset, outfile, rbblocksize):
    outf = open(outfile, 'wb')
    psize = partsize
    offset = partoffset
    print('Dumping %d bytes from partition 0x%X at offset 0x%X to %s...' % (partsize, partid, partoffset, outfile))
    bufsize = rbblocksize
    while psize > 0:
        if psize < bufsize:
            bufsize = psize
        resp = read_partdata(partid, bufsize, offset)
        rcode, rlen, r = unicmd.resp_decode(resp, True)
        outf.write(r)
        sys.stdout.write('.')
        sys.stdout.flush()
        psize -= rlen
        offset += rlen
    outf.flush()
    print('\nPartition dumped!')

# memory eraser and writer

def erase_flash_mem(size, faddr):
    print('Erasing %d bytes in the flash memory at offset 0x%X...' % (size, faddr - UNISOC_FLASH_BASE_ADDR))
    resp = reqresp(unicmd.cmd_erase_flash(faddr, size), True)
    rcode, rlen, r = unicmd.resp_decode(resp, True)
    assert rcode == unicmd.BSL_REP_ACK, 'Could not erase flash memory, response code is %X' % rcode
    print('Flash range erased!')

def write_flash_mem(infile, offset, blocksize, forceErase):
    startAddr = UNISOC_FLASH_BASE_ADDR + offset
    f = open(infile, 'rb')
    fdata = f.read()
    f.close()
    flen = len(fdata)
    if forceErase:
        erase_flash_mem(flen, startAddr)
    send_file_to_addr(fdata, startAddr, True, True, blocksize)

# main code start

def auto_int(x):
    return int(x,0)

if __name__ == '__main__': # main app start
    from argparse import ArgumentParser
    rootdir = os.path.dirname(os.path.realpath(__file__))
    parser = ArgumentParser(description='UniFlash: an opensource Unisoc/Spreadtrum feature phone flash reader/writer', epilog='(c) Luxferre 2021 --- No rights reserved <https://unlicense.org>')
    parser.add_argument('mode', help='Operation mode (flash/dump/stone-unpack)')
    parser.add_argument('file', help='File to read the flash data from or write the dump into, or the stone file to unpack')
    parser.add_argument('-p','--partid', type=auto_int, default=0x80000003, help='Partition ID for readback (defaults to 0x80000003 that can address full flash space on SC6531E/F/M)')
    parser.add_argument('-s','--start', type=auto_int, default=0, help='Start position (in the partition when reading or in the flash memory when writing, defaults to 0)')
    parser.add_argument('-l', '--length', type=auto_int, default=0x400000, help='Data length in bytes to read/write, defaults to 0x400000')
    parser.add_argument('-t','--target', default='sc6531efm_generic', help='Preinstalled target (defaults to sc6531efm_generic, overridable with individual FDL parameters)')
    parser.add_argument('-d','--directory', default=None, help='Directory where component files will be written to in stone-unpack mode (defaults to the same where the main stone file resides)')
    parser.add_argument('-nr','--flash-noremap', action='store_true', help='Disable base address remapping for flashing')
    parser.add_argument('-e','--force-erase', action='store_true', help='Erase target flash memory area before flashing')
    parser.add_argument('-wf','--enable-write-flash', action='store_true', help='Send the write flash enable command before flashing (if necessary and supported)')
    parser.add_argument('-bs','--block-size', type=auto_int, default=4096, help='Readback/write block size (in bytes), defaults to 4096')
    parser.add_argument('-dv','--device-vid', type=auto_int, default=UNISOC_VID, help='Override device vendor ID')
    parser.add_argument('-dp','--device-pid', type=auto_int, default=UNISOC_PID, help='Override device product ID')
    parser.add_argument('-fdl1','--fdl1-file', default=None, help='Path to FDL1, overrides the target')
    parser.add_argument('-addr1','--fdl1-addr', type=auto_int, default=None, help='Address to load FDL1 into, overrides the target')
    parser.add_argument('-fdl2','--fdl2-file', default=None, help='Path to FDL2, overrides the target')
    parser.add_argument('-addr2','--fdl2-addr', type=auto_int, default=None, help='Address to load FDL2 into, overrides the target')
    parser.add_argument('-sfdl','--single-fdl-file', default=None, help='Path to a single FDL (for old Spreadtrum chipsets), overrides the target')
    parser.add_argument('-saddr','--single-fdl-addr', type=auto_int, default=None, help='Address to load the single FDL into, overrides the target')

    args = parser.parse_args()

    if args.mode.startswith('stone'): # stone-unpack mode
        imgfile = args.file
        imgdir = os.path.dirname(os.path.realpath(imgfile))
        if args.directory is not None:
            imgdir = os.path.realpath(args.directory)

        print('Unpacking %s to %s' % (imgfile, imgdir))
        stoned.unpack_stone(imgfile, imgdir)

    else: # flash/dump mode
        is_flash = False
        if args.mode == 'flash':
            is_flash = True

        # parse target and resolve the parameters from it first
        paramdelim = '_'
        target = args.target + paramdelim
        fdlDir = rootdir + '/fdls'
        fdlList = []
        for root, dirs, files in os.walk(fdlDir):
            for name in files:
                if name.startswith(target):
                    paramstr = os.path.splitext(name)[0].split(target)[1]
                    params = paramstr.split(paramdelim)
                    fdlList.append((params[1], params[0], fdlDir+'/'+name))
        # resulting fdl list: (tag, address, path)
        fdlSingleName = None
        fdlSingleAddr = None
        for tag, addr, path in fdlList:
            if tag == 'single':
                fdlSingleName = path
                fdlSingleAddr = auto_int(addr)
            elif tag == 'fdl1':
                fdl1Name = path
                fdl1Addr = auto_int(addr)
            elif tag == 'fdl2':
                fdl2Name = path
                fdl2Addr = auto_int(addr)

        # override target with the individual parameters if necessary
        UNISOC_VID = args.device_vid
        UNISOC_PID = args.device_pid
        if args.fdl1_addr is not None:
            fdl1Addr = args.fdl1_addr
        if args.fdl2_addr is not None:
            fdl2Addr = args.fdl2_addr
        if args.fdl1_file is not None:
            fdl1Name = args.fdl1_file
        if args.fdl2_file is not None:
            fdl2Name = args.fdl2_file
        if args.single_fdl_file is not None:
            fdlSingleName = args.single_fdl_file
        if args.single_fdl_addr is not None:
            fdlSingleAddr = args.single_fdl_addr
        outfile = args.file
        partitionId = args.partid
        readbs = args.block_size
        readoffset = args.start
        readlen = args.length
        forceErase = args.force_erase
        sendEnableWriteFlash = args.enable_write_flash
        singleFdlMode = False
        fdl1Label = 'FDL1'
        fdl2Label = 'FDL2'

        # override flash base addr based on the target

        if target.startswith('sc6530'):
            UNISOC_FLASH_BASE_ADDR = UNISOC_FLASH_BASE_ADDR_OLD

        if args.flash_noremap == True:
            print('Flash remapping disabled')
            UNISOC_FLASH_BASE_ADDR = 0

        if fdlSingleName is not None:
            singleFdlMode = True
            fdl1Addr = fdlSingleAddr
            fdl1Name = fdlSingleName
            fdl1Label = 'FDL'
            fdl2Label = 'FDL'
            print('Using a single FDL %s, loading to 0x%X' % (fdlSingleName, fdlSingleAddr))
        else:
            print('Using FDL1 %s, loading to 0x%X' % (fdl1Name, fdl1Addr))
            print('Using FDL2 %s, loading to 0x%X' % (fdl2Name, fdl2Addr))

        # initial connection
        print('Connect the device %X:%X while holding the bootkey...' % (UNISOC_VID, UNISOC_PID) )
        dev, epIn, epOut = connect(UNISOC_VID, UNISOC_PID)
        handshake()

        def reconnect():
            global dev
            if dev is not None:
                usb.util.dispose_resources(dev)
                time.sleep(0.5)
            dev, epIn, epOut = connect(UNISOC_VID, UNISOC_PID)

        print('Boot mode entered')

        print('Sending ' + fdl1Label)
        send_file_to_addr(fdl1Name, fdl1Addr)
        print('Starting ' + fdl1Label)
        resp = reqresp(unicmd.cmd_data_exec(fdl1Addr))
        rcode, rlen, r = unicmd.resp_decode(resp, False)
        if rcode == unicmd.BSL_REP_ACK:
            print(fdl1Label + ' started successfully, reconnecting...')
            reconnect()
            handshake(True)

            if singleFdlMode:
                rcode = unicmd.BSL_REP_ACK
            else:
                print('Protocol set up, sending FDL2')
                send_file_to_addr(fdl2Name, fdl2Addr, True)
                print('Starting FDL2')
                resp = reqresp(unicmd.cmd_data_exec(fdl2Addr), True)
                rcode, rlen, r = unicmd.resp_decode(resp, True)
            if rcode == unicmd.BSL_REP_ACK:
                print(fdl2Label + ' started successfully!')

                resp = reqresp(unicmd.cmd_sync_full(), True)
                rcode, rlen, r = unicmd.resp_decode(resp, True)
                assert rcode == unicmd.BSL_REP_ACK, 'Could not set the baudrate, response code is %X' % rcode

                print(fdl2Label + ' running, may start interacting with flash memory')

                if is_flash:

                    if sendEnableWriteFlash:
                        resp = reqresp(unicmd.cmd_enable_write_flash(), True)
                        rcode, rlen, r = unicmd.resp_decode(resp, True)
                        assert rcode == unicmd.BSL_REP_ACK, 'Could not send the flash write request, response code is %X' % rcode

                    print('Writing flash at offset 0x%X from %s...' % (readoffset, outfile))
                    write_flash_mem(outfile, readoffset, readbs, forceErase)
                    print('Flash memory written, disconnect the device!')
                else:
                    read_partition(partitionId, readlen, readoffset, outfile, readbs)
                    resp = reqresp(unicmd.cmd_reset(), True)
                    rcode, rlen, r = unicmd.resp_decode(resp, True)
                    assert rcode == unicmd.BSL_REP_ACK, 'Could not reset the device, response code is %X' % rcode

        if dev is not None: 
            usb.util.dispose_resources(dev)
