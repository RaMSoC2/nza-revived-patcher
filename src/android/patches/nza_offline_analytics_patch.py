"""Minimal version-locked DEX patch: skip only the Fiksu upload invocation.

EventUploader.run retains its original monitor/notifyAll and exception handlers.
Six bytes become three valid nop instructions; no DEX offsets or game methods
change. The complete input digest guards the fixed method/code coordinates.
"""
import hashlib
import struct
import zlib

BEFORE_SHA256='34f3fd8770029de12e8cb3b3eba9260e55ade2c8c06d1fc9e7287d38cf115f11'
OFFSET=0x9ca90
BEFORE=bytes.fromhex('701076170100')

def patch(dex):
    if hashlib.sha256(dex).hexdigest()!=BEFORE_SHA256:
        raise ValueError('Unknown original DEX; offline analytics patch refused')
    if dex[OFFSET:OFFSET+6]!=BEFORE:
        raise ValueError('Unexpected EventUploader.run instruction')
    # invoke-direct {p0}, EventUploader.uploadToTracking()V -> nop; nop; nop.
    changed=bytearray(dex)
    changed[OFFSET:OFFSET+6]=b'\0'*6
    changed[12:32]=hashlib.sha1(changed[32:]).digest()
    struct.pack_into('<I',changed,8,zlib.adler32(changed[12:])&0xffffffff)
    output=bytes(changed)
    record={'patch':'skip Fiksu EventUploader.run upload invocation',
            'input_sha256':BEFORE_SHA256,'output_sha256':hashlib.sha256(output).hexdigest(),
            'offset':OFFSET,'before_hex':BEFORE.hex(),'after_hex':'00'*6,
            'method':'Lcom/fiksu/asotracking/EventUploader;->run()V',
            'preserves_monitor_notify_and_handlers':True,
            'internet_permission_added':False}
    return output,record
