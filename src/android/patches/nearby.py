"""Hash-guarded cache adapter at the original places-failure callback; reversible RX segment."""
import argparse,base64,hashlib,json,struct
from pathlib import Path
from arm import branch
from town_name_credit_patch import Arm

BASE_SHA='5bd39aa97d496e36e3a27f84911ee4298caac74324a0cb38a093d509a18d7d6e'
HOOK=0x15263ac
def make_patch(data, symbol_elf):
    if hashlib.sha256(data).hexdigest()!=BASE_SHA:raise ValueError('Unexpected saved-engine checkpoint')
    header=struct.unpack_from('<16sHHIIIIIHHHHHH',data)
    assert header[5]==52 and header[9]==32 and header[10]==7
    ph=[struct.unpack_from('<8I',data,52+i*32) for i in range(7)]
    assert ph[5][0]==0x6474e551 and ph[6][0]==1
    va=(max(p[2]+p[5] for p in ph if p[0]==1)+4095)&~4095
    off=(len(data)+4095)&~4095
    from elf import Elf32
    # Original import slots; confirm names from the preserved inventory before use.
    original=Elf32(symbol_elf)
    slots={}
    for i in range(4544//8):
        target,info=struct.unpack_from('<II',data,0x10d83b0+i*8)
        slots[original.dynamic_symbol_names[info>>8]]=0x10d9570+20+i*12
    a=Arm(va);a.mark('start');a.enter();a.mov(4,0);a.mov(5,2);a.emit(0xe58d5014);a.emit(0xe58d101c)
    a.ptr(1,'nza-nearby-delivery');a.mov(0,4);a.call(slots['objc_getAssociatedObject'])
    a.emit(0xe3500000);a.jump('fallback',cond=1)
    a.ptr(0,'NSDictionary');a.call(0x10d9908);a.mov(6,0)
    a.string('/data/data/com.ramsoc2.nzarevived/files/plugins/com.booyah.zombie/data/files/LocalFiles/nza-nearby.plist',7)
    a.send(6,'dictionaryWithContentsOfFile:',7);a.mov(6,0)
    a.emit(0xe3500000);a.jump('fallback',cond=0)
    a.string('placeSearchResults',8);a.send(6,'objectForKey:',8);a.mov(7,0)
    a.send(7,'count');a.emit(0xe3500000);a.jump('fallback',cond=0)
    a.emit(0xe58d6018)
    a.send(4,'curSearchString');a.mov(8,0);a.send(8,'lowercaseString');a.mov(8,0)
    a.singleton('NSMutableArray','array',9);a.imm(10,0)
    a.string('name',6)
    a.mark('loop');a.send(7,'count');a.emit(0xe15a0000);a.jump('ready',cond=2)
    a.send(7,'objectAtIndex:',10);a.emit(0xe58d0010)
    a.send(8,'length');a.emit(0xe3500000);a.jump('add',cond=0)
    a.emit(0xe59d5010);a.send(5,'objectForKey:',6);a.mov(5,0)
    a.send(5,'lowercaseString');a.mov(5,0)
    a.mov(0,5);a.mov(2,8);a.jump('contains',link=True)
    a.emit(0xe3500000);a.jump('next',cond=0)
    a.mark('add');a.emit(0xe59d5010);a.send(9,'addObject:',5)
    a.mark('next');a.emit(0xe28aa001);a.jump('loop')
    a.mark('ready');a.send(9,'count');a.emit(0xe3500000);a.jump('fallback',cond=0)
    a.emit(0xe59d6018);a.send(6,'mutableCopy');a.mov(6,0)
    a.string('placeSearchResults',7);a.send(6,'setObject:forKey:',9,7)
    a.send(4,'searchFrame');a.mov(7,0);a.send(7,'textField');a.mov(7,0)
    a.string('Nearby: Â© OpenStreetMap contributors',8);a.send(7,'setPlaceholder:',8)
    a.ptr(1,'nza-nearby-delivery');a.mov(0,4);a.mov(2,4);a.imm(3,1);a.call(slots['objc_setAssociatedObject'])
    a.send(4,'placeSearchSucceeded:',6)
    a.ptr(1,'nza-nearby-delivery');a.mov(0,4);a.imm(2,0);a.imm(3,1);a.call(slots['objc_setAssociatedObject'])
    a.send(6,'release');a.leave()
    a.mark('fallback');a.mov(0,4);a.emit(0xe59d2014);a.emit(0xe59d101c);a.leave()
    # leave() returns; fallback must instead restore then replay the original prologue.
    a.words[-1]=0xe8bd47f0
    original=struct.unpack_from('<I',data,HOOK)[0];assert original==0xe92d4ff0
    a.emit(original);a.call(HOOK+4);a.words[-1]=branch(a.here()-4,HOOK+4,link=False)
    a.mark('contains')
    a.emit(0xe92d41f0);a.emit(0xe24dd010);a.mov(4,0);a.mov(5,2)
    a.sel('rangeOfString:');a.mov(6,1);a.mov(0,4);a.call(0x10da16c);a.mov(7,0)
    a.mov(0,13);a.mov(1,4);a.mov(2,6);a.mov(3,5);a.emit(0xe12fff37)
    a.emit(0xe59d0004);a.emit(0xe3500000);a.imm(0,0);a.emit(0x13a00001)
    a.emit(0xe28dd010);a.emit(0xe8bd81f0)
    a.mark('nsstring');a.emit(0xe92d4070);a.mov(4,0)
    a.ptr(0,'NSString');a.call(0x10d9908);a.mov(5,0);a.send(5,'stringWithUTF8String:',4);a.emit(0xe8bd8070)
    a.mark('send');a.emit(0xe92d41f0);a.emit(0xe24dd010)
    for d,s in [(4,0),(5,1),(6,2),(7,3)]:a.mov(d,s)
    a.call(0x10da16c);a.mov(8,0)
    a.emit(0xe28dc028);a.emit(0xe89c000f);a.emit(0xe88d000f)
    for d,s in [(0,4),(1,5),(2,6),(3,7)]:a.mov(d,s)
    a.emit(0xe12fff38);a.emit(0xe28dd010);a.emit(0xe8bd81f0)
    code=a.finish();assert len(code)<=4096
    changes=[{'offset':HOOK,'before':data[HOOK:HOOK+4].hex(),'after':struct.pack('<I',branch(HOOK,va,False)).hex()},
             {'offset':52+5*32,'before':data[52+5*32:52+7*32].hex(),
              'after':(struct.pack('<8I',*ph[6])+struct.pack('<8I',1,off,va,va,len(code),len(code),5,4096)).hex()}]
    tail=b'\0'*(off-len(data))+code
    patched=bytearray(data+tail)
    for c in changes:patched[c['offset']:c['offset']+len(bytes.fromhex(c['after']))]=bytes.fromhex(c['after'])
    recipe={'before_sha256':BASE_SHA,'after_sha256':hashlib.sha256(patched).hexdigest(),'original_bytes':len(data),
        'changes':changes,'append_base64':base64.b64encode(tail).decode(),'rx_segment_va':hex(va),
        'schema_evidence':'ZTBuildOutpostViewController placeSearchSucceeded and tableView callbacks: placeSearchResults/name/latitude/longitude/poiId',
        'fallback':'Replay original placeSearchFailed when own cache missing/empty; original game logic retained'}
    return bytes(patched),recipe