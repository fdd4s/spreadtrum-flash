# Command interface for Unisoc chipsets
# Created by Luxferre in 2021

from struct import pack, unpack

UNICMD_CRC_MISMATCH = 0xd00b

# HDLC frame encoding/decoding (Unisoc modification)

def crc16_xmodem(data: bytes): # xmodem used in boot mode 
    crc = 0
    data = bytearray(data)
    msb = crc >> 8
    lsb = crc & 255
    for c in data:
        x = (0xFF & c) ^ msb
        x ^= (x >> 4)
        msb = (lsb ^ (x >> 3) ^ (x << 4)) & 255
        lsb = (x ^ (x << 5)) & 255
    return (msb << 8) + lsb

def crc16_fdl(data: bytes): # used in FDL1/2 mode
    crc = 0
    data = bytearray(data)
    l = len(data)
    for i in range(0,l,2):
        if i+1 == l:
            crc += data[i]
        else:
            crc += (data[i]<<8)|data[i+1]
    crc = (crc >> 16) + (crc & 0xffff)
    crc += (crc >> 16)
    return ~crc & 0xffff

def chksum32(data: bytes): # used in flashing mode
    cksum = 0
    for c in data:
        cksum = (cksum + c) & 0xffffffff
    return cksum

def hdlc_encode(data, fdl = False, nocrc = False):
    if nocrc:
        crc = 0
    else:
        if fdl:
            crc = crc16_fdl(data)
        else:
            crc = crc16_xmodem(data)
    out = []
    rdata = bytearray(data + pack('>H', crc))
    for c in rdata:
        if c == 0x7e or c == 0x7d:
            out.append(0x7d)
            out.append(c ^ 0x20)
        else:
            out.append(c)
    out = bytes(out)
    return b'\x7e' + out + b'\x7e'

def hdlc_decode(data, fdl = False, ignoreCrc = False): # HDLC bug in Unisoc: CRC is also encoded!!!
    rawdata = bytearray(data[1:-1])
    out = []
    esc = False
    for c in rawdata:
        if esc:
            if c == 0x5e or c == 0x5d:
                out.append(c ^ 0x20)
                esc = False
            else:
                raise Exception("Invalid escape sequence while decoding HDLC frame")
        elif c == 0x7d:
            esc = True
        else:
            out.append(c)
    decoded = bytes(out)
    rawcrc = unpack('>H', decoded[-2:])[0]
    decoded = decoded[:-2]
    if fdl:
        calc_crc = crc16_fdl(decoded)
    else:
        calc_crc = crc16_xmodem(decoded)
    if ignoreCrc: # don't hard assert but return a special error code on CRC mismatch
        if rawcrc != calc_crc:
            return UNICMD_CRC_MISMATCH
    else:
        assert rawcrc == calc_crc, "Actual CRC16 value %04x does not match calculated value %04x after decoding HDLC frame" % (rawcrc, calc_crc)
    return decoded

def resp_decode(data, fdl = False, ignoreCrc = False):
    rawdata = hdlc_decode(data, fdl, ignoreCrc)
    if rawdata != UNICMD_CRC_MISMATCH:
        respcode, resplen = unpack('>HH', rawdata[:4])
        content = rawdata[4:4+resplen]
        return respcode, resplen, content
    else:
        return UNICMD_CRC_MISMATCH, 0, None

# Unisoc command set constants

FLAG_BYTE = 0x7E

BSL_PKT_TYPE_MIN = 0

# PC -> phone commands

BSL_CMD_CONNECT = BSL_PKT_TYPE_MIN

BSL_CMD_START_DATA = 1
BSL_CMD_MIDST_DATA = 2
BSL_CMD_END_DATA = 3
BSL_CMD_EXEC_DATA = 4

BSL_CMD_NORMAL_RESET = 5
BSL_CMD_READ_FLASH = 6
BSL_CMD_READ_CHIP_TYPE = 7
BSL_CMD_READ_NVITEM = 8
BSL_CMD_CHANGE_BAUD = 9
BSL_CMD_ERASE_FLASH = 0xa
BSL_CMD_REPARTITION = 0xb
BSL_CMD_READ_FLASH_TYPE = 0xc
BSL_CMD_READ_FLASH_INFO = 0xd
BSL_CMD_READ_SECTOR_SIZE = 0xf

BSL_CMD_READ_START = 0x10
BSL_CMD_READ_MIDST = 0x11
BSL_CMD_READ_END = 0x12

BSL_CMD_KEEP_CHARGE = 0x13
BSL_CMD_READ_FLASH_UID = 0x15
BSL_CMD_POWER_OFF = 0x17
BSL_CMD_READ_CHIP_UID = 0x1A
BSL_CMD_ENABLE_WRITE_FLASH = 0x1B
BSL_CMD_ENABLE_SECUREBOOT = 0x1C
BSL_CMD_EXEC_NAND_INIT = 0x21

BSL_CMD_CHECK_BAUD = FLAG_BYTE

BSL_CMD_END_PROCESS = 0x7F

# Phone -> PC responses

BSL_REP_TYPE_MIN = 0x80
BSL_REP_ACK = BSL_REP_TYPE_MIN
BSL_REP_VER = 0x81
BSL_REP_INVALID_CMD = 0x82
BSL_REP_UNKNOWN_CMD = 0x83
BSL_REP_OPERATION_FAILED = 0x84
BSL_REP_NOT_SUPPORT_BAUDRATE = 0x85

BSL_REP_DOWN_NOT_START = 0x86
BSL_REP_DOWN_MULTI_START = 0x87
BSL_REP_DOWN_EARLY_END = 0x88
BSL_REP_DOWN_DEST_ERROR = 0x89
BSL_REP_DOWN_SIZE_ERROR = 0x8A
BSL_REP_VERIFY_ERROR = 0x8B
BSL_REP_NOT_VERIFY = 0x8C

BSL_PHONE_NOT_ENOUGH_MEMORY = 0x8D
BSL_PHONE_WAIT_INPUT_TIMEOUT = 0x8E

BSL_PHONE_SUCCEED = 0x8F
BSL_PHONE_VALID_BAUDRATE = 0x90
BSL_PHONE_REPEAT_CONTINUE = 0x91
BSL_PHONE_REPEAT_BREAK = 0x92

BSL_REP_READ_FLASH = 0x93
BSL_REP_READ_CHIP_TYPE = 0x94
BSL_REP_READ_NVITEM = 0x95

BSL_REP_INCOMPATIBLE_PARTITION = 0x96 
BSL_REP_UNKNOWN_DEVICE = 0x97 
BSL_REP_INVALID_DEVICE_SIZE = 0x98 
BSL_REP_ILLEGAL_SDRAM = 0x99 
BSL_WRONG_SDRAM_PARAMETER = 0x9A 
BSL_REP_READ_FLASH_INFO = 0x9B 
BSL_REP_READ_SECTOR_SIZE = 0x9C 
BSL_REP_READ_FLASH_TYPE = 0x9D 
BSL_REP_READ_FLASH_UID = 0x9E 
BSL_REP_READ_SOFTSIM_EID = 0x9F 

BSL_ERROR_CHECKSUM = 0xA0
BSL_CHECKSUM_DIFF = 0xA1
BSL_WRITE_ERROR = 0xA2
BSL_CHIPID_NOT_MATCH = 0xA3
BSL_FLASH_CFG_ERROR = 0xA4
BSL_REP_DOWN_STL_SIZE_ERROR = 0xA5
BSL_REP_SECURITY_VERIFICATION_FAIL = 0xA6
BSL_REP_PHONE_IS_ROOTED = 0xA7
BSL_REP_SEC_VERIFY_ERROR = 0xAA
BSL_REP_READ_CHIP_UID = 0xAB
BSL_REP_NOT_ENABLE_WRITE_FLASH = 0xAC
BSL_REP_ENABLE_SECUREBOOT_ERROR = 0xAD
BSL_REP_FLASH_WRITTEN_PROTECTION = 0xB3
BSL_REP_FLASH_INITIALIZING_FAIL = 0xB4
BSL_REP_RF_TRANSCEIVER_TYPE = 0xB5

BSL_REP_UNSUPPORTED_COMMAND = 0xFE
BSL_REP_LOG = 0xFF
BSL_PKT_TYPE_MAX = 0x100

BSL_UART_SEND_ERROR = 0x101
BSL_REP_DECODE_ERROR = 0x102
BSL_REP_INCOMPLETE_DATA = 0x103
BSL_REP_READ_ERROR = 0x104
BSL_REP_TOO_MUCH_DATA = 0x105
BSL_USER_CANCEL = 0x106
BSL_REP_SIZE_ZERO = 0x107
BSL_REP_PORT_ERROR = 0x108

# Unisoc command packet interface

def shape_cmd_packet(command):
    return pack('>HH', command, 0)

def shape_data_packet(dtype, data, dlen = 0):
    if dlen == 0:
        dlen = len(data)
    #if dlen&1:
    #    dlen += 1
    packethdr = pack('>HH', dtype, dlen)
    return packethdr + data

def cmd_data_start(targetAddr, targetLen, externalCrc = 0):
    if externalCrc:
        datahdr = pack('>LLL', targetAddr, targetLen, externalCrc)
    else:
        datahdr = pack('>LL', targetAddr, targetLen)
    return shape_data_packet(BSL_CMD_START_DATA, datahdr)

def cmd_data_send(data):
    return shape_data_packet(BSL_CMD_MIDST_DATA, data)

def cmd_data_end():
    return shape_cmd_packet(BSL_CMD_END_DATA)

def cmd_data_exec(targetAddr):
    datahdr = pack('>L', targetAddr)
    return shape_data_packet(BSL_CMD_EXEC_DATA, datahdr)

def cmd_connect():
    return shape_cmd_packet(BSL_CMD_CONNECT)

def cmd_reset():
    return shape_cmd_packet(BSL_CMD_NORMAL_RESET)

def cmd_sync():
    return pack('>H', BSL_CMD_CHECK_BAUD)

def cmd_sync_full(baudrate = 921600):
    datahdr = pack('>L', baudrate)
    return shape_data_packet(BSL_CMD_CHANGE_BAUD, datahdr)

def cmd_read_chip_type():
    return shape_cmd_packet(BSL_CMD_READ_CHIP_TYPE)

def cmd_read_sector_size():
    return shape_cmd_packet(BSL_CMD_READ_SECTOR_SIZE)

def cmd_read_flash(targetAddr, targetLen, offset):
    return pack('>HHLLL', BSL_CMD_READ_FLASH, 12, targetAddr, targetLen, offset)

def cmd_erase_flash(targetAddr, targetLen):
    datahdr = pack('>LL', targetAddr, targetLen)
    return shape_data_packet(BSL_CMD_ERASE_FLASH, datahdr)

def cmd_enable_write_flash():
    return shape_cmd_packet(BSL_CMD_ENABLE_WRITE_FLASH)

def cmd_end_flash_process():
    return shape_cmd_packet(BSL_CMD_END_PROCESS)
