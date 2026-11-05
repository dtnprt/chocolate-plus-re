#!/usr/bin/env python3
"""
fwsctool.py - unwrap / inspect / fix-CRC / rewrap for Sinco .fwsc  (JieLi AC636N .ufw)
Reversed from com.sinco.ota (Tools.unpackFWSCFile) + libjl_ota_auth.so (parse_fw_info / CRC16).
All constants are baked-in; no device secret is required.
"""
import sys, os, struct

# ---- JieLi .ufw header/dir obfuscation cipher (LFSR, seed 0xffff) ----
def lfsr_next(v):
    w10=v&0xffffffff
    w16=(w10>>0xf)&1
    w15=((w10&0xffff)>>0xb)&1 ^ w16
    w1=(w10<<1)&0xffffffff
    w2=(w10>>0xa)&0xffffffff
    w3=w1&0xffffe000
    w4=w1&0x40
    w1=(w1&~1)|((w10>>0xf)&1)
    w3=(w3&~(1<<0xc))|((w15&1)<<0xc)
    w15b=w10&0xff
    w10b=(w15b>>7)&1
    w15=((w15b>>4)&1)^w16
    w3=(w3&~(1<<0xb))|(((w10>>0xa)&1)<<0xb)
    w4=(w4&~0b11)|(w1&0b11)
    w3=(w3&~(1<<0xa))|(((w10>>9)&1)<<0xa)
    w4=(w4&~(1<<4))|(((w10>>3)&1)<<4)
    w3=(w3&~(1<<9))|(((w10>>8)&1)<<9)
    w4=(w4&~(1<<3))|(((w10>>2)&1)<<3)
    w3=(w3&~(1<<8))|((w10b&1)<<8)
    w4=(w4&~(1<<2))|(((w10>>1)&1)<<2)
    w3=(w3&~(1<<7))|(((w10>>6)&1)<<7)
    w4=(w4&~(1<<5))|((w15&1)<<5)
    return (w4|w3)&0xffffffff

def xcode_block(buf, seed=0xffff, invert_first=True):
    """Reversible: byte0=~byte0 ; bytes1.. ^= lfsr keystream. XOR is its own inverse."""
    b=bytearray(buf); v=seed
    if invert_first and b: b[0]=(~b[0])&0xff
    for i in range(1,len(b)):
        v=lfsr_next(v); b[i]^=(v&0xff)
    return b

# ---- CRC-16/CCITT (XMODEM), nibble table 0x1021 ----
_T=[0x0,0x1021,0x2042,0x3063,0x4084,0x50a5,0x60c6,0x70e7,
    0x8108,0x9129,0xa14a,0xb16b,0xc18c,0xd1ad,0xe1ce,0xf1ef]
def crc16(data, crc=0):
    for byte in data:
        crc=(_T[((crc>>12)^(byte>>4))&0xf]^(crc<<4))&0xffff
        crc=(_T[((crc>>12)^(byte&0xf))&0xf]^(crc<<4))&0xffff
    return crc

# ---- Member payload cipher (exact port of libjl_ota_auth.so). XOR -> self-inverse. ----
# seed_k = key ^ ((pos + 32*k) >> 2)  ; `pos` is a per-member base (flash-addr-like),
# NOT the .ufw file offset. Verified working params (key, pos):
#   code / app-area member (flash.bin[0x1000:], also flash2.bin): key=0x180f pos=0x20000
#     (CORRECTED: the old 0x9d0f/0x1400 garbled ~60% of blocks; app.bin internal CRC now verifies)
#   isd_config member                    : key=0x180f pos=0x7a00   (fully clean text)
# (The (key,pos) decomposition is not unique per member, but these reproduce the exact streams.)
GLOBAL_KEY = 0x180f  # correct app-area key (use pos=0x20000 for flash.bin[0x1000:])
def member_decrypt(buf, key=GLOBAL_KEY, pos=0):
    """`decrypt` @0x2250: 32-byte blocks, reseed each block seed=key^(pos>>2), pos+=32."""
    out=bytearray(buf); n=len(out); i=0
    while i<n:
        blk=min(32,n-i); st=(key^(pos>>2))&0xffffffff; out[i]^=st&0xff
        for j in range(1,blk):
            st=lfsr_next(st); out[i+j]^=st&0xff
        i+=blk; pos+=blk
    return bytes(out)
def member_cd03(buf, key=GLOBAL_KEY, pos=0):
    """`cd03_crc_encode` @0x2190: seed ONCE (key^(pos>>2), or key if pos==0), continuous LFSR."""
    out=bytearray(buf); n=len(out)
    st=(key ^ ((pos>>2) if pos!=0 else 0))&0xffffffff
    if n: out[0]^=st&0xff
    for i in range(1,n):
        st=lfsr_next(st); out[i]^=st&0xff
    return bytes(out)
# Verified flash addresses: code/app-area member = 0x1400 ; isd_config member = 0x7a00

# ---- .fwsc wrapper (Sinco): 20 metadata bytes, one per 48-byte group over first 960 bytes ----
def fwsc_unwrap(data, namenoext):
    length=len(data); out=bytearray(); i2=0
    for i4 in range(20):
        out+=data[i2:i2+47]; i2+=48
    out+=data[i2:length]
    return bytes(out)  # == the raw .ufw

def fwsc_wrap(ufw, name, version, suffix=''):
    """Rebuild a .fwsc from a raw .ufw. Reproduces the original layout exactly (suffix='').

    The 20 metadata bytes hold "<name>_<version:03d><suffix>" (padded with '@'). SincoOTA descrambles
    stored = plain + i + 1 for i < len(file name without extension), so the file must be named
    "<name>_<version:03d><suffix>.fwsc" for the metadata to decode cleanly.
    """
    hdr = f"{name}_{version:03d}{suffix}"[:20]
    meta = [ord(c) for c in hdr] + [ord('@')] * (20 - len(hdr))
    out = bytearray(); p = 0
    for i4 in range(20):
        out += ufw[p:p+47]; p += 47
        b = meta[i4]
        if i4 < len(hdr): b = (b + i4 + 1) & 0xff
        out.append(b)
    out += ufw[p:]
    return bytes(out)

# ---- high-level ----
def decode_header(ufw):
    hdr=xcode_block(ufw[:0x40])
    stored_crc=struct.unpack_from('<H',hdr,0)[0]
    calc_crc=crc16(hdr[2:0x40])
    tbl_crc=struct.unpack_from('<H',hdr,2)[0]
    total=struct.unpack_from('<I',hdr,4)[0]
    count=struct.unpack_from('<H',hdr,8)[0]
    chip=hdr[0x10:0x18].split(b'\0')[0].decode('latin1')
    return dict(hdr=hdr,stored_crc=stored_crc,calc_crc=calc_crc,
                tbl_crc=tbl_crc,total=total,count=count,chip=chip)

def fix_header_crc(ufw):
    """Recompute header CRC16 + chunk-table CRC16 after a payload/table edit, re-encode header."""
    ufw=bytearray(ufw)
    hdr=xcode_block(ufw[:0x40])              # decode
    count=struct.unpack_from('<H',hdr,8)[0]
    tbl=ufw[0x40:0x40+count*0x50]            # chunk table is NOT header-encoded in-place; it's dir-encoded per entry
    # table CRC is computed over the on-disk (encoded) table bytes:
    struct.pack_into('<H',hdr,2,crc16(tbl))
    struct.pack_into('<H',hdr,0,crc16(hdr[2:0x40]))  # header CRC over bytes 2..0x40
    enc=xcode_block(hdr)                     # re-encode (XOR+invert is self-inverse)
    ufw[:0x40]=enc
    return bytes(ufw)

def main():
    if len(sys.argv)<2:
        print(__doc__); print("commands: info <ufw|fwsc>  unwrap <fwsc> <ufw>  wrap <ufw> <fwsc> <name> <ver>  fixcrc <ufw_in> <ufw_out>  selftest <orig.fwsc>")
        return
    cmd=sys.argv[1]
    if cmd=="unwrap":
        src,dst=sys.argv[2],sys.argv[3]
        data=open(src,'rb').read()
        ufw=fwsc_unwrap(data, os.path.splitext(os.path.basename(src))[0])
        open(dst,'wb').write(ufw); print(f"wrote {dst} ({len(ufw)} bytes)")
    elif cmd=="wrap":
        src,dst,name,ver=sys.argv[2],sys.argv[3],sys.argv[4],int(sys.argv[5])
        ufw=open(src,'rb').read()
        open(dst,'wb').write(fwsc_wrap(ufw,name,ver)); print(f"wrote {dst}")
    elif cmd=="info":
        data=open(sys.argv[2],'rb').read()
        if sys.argv[2].endswith('.fwsc'):
            data=fwsc_unwrap(data, os.path.splitext(os.path.basename(sys.argv[2]))[0])
        h=decode_header(data)
        ok="OK" if h['stored_crc']==h['calc_crc'] else f"MISMATCH(calc {h['calc_crc']:#06x})"
        print(f"chip={h['chip']} total_size={h['total']} chunks={h['count']}")
        print(f"header_crc stored={h['stored_crc']:#06x} {ok}")
        print(f"chunk_table_crc(stored)={h['tbl_crc']:#06x} calc={crc16(data[0x40:0x40+h['count']*0x50]):#06x}")
    elif cmd=="fixcrc":
        ufw=open(sys.argv[2],'rb').read()
        open(sys.argv[3],'wb').write(fix_header_crc(ufw)); print(f"wrote {sys.argv[3]} with fixed CRCs")
    elif cmd=="selftest":
        orig=open(sys.argv[2],'rb').read()
        nm=os.path.splitext(os.path.basename(sys.argv[2]))[0]  # FootCtrlPlus_012
        ufw=fwsc_unwrap(orig, nm)
        # derive name/version from the embedded header (robust), then rewrap
        base=nm.rsplit('_',1); name=base[0]; ver=int(base[1])
        rebuilt=fwsc_wrap(ufw, name, ver)
        print("unwrap+rewrap identical to original :", rebuilt==orig)
        h=decode_header(ufw)
        print("header CRC verifies                 :", h['stored_crc']==h['calc_crc'])
        print(f"   chip={h['chip']} size={h['total']} chunks={h['count']}")
if __name__=="__main__": main()
