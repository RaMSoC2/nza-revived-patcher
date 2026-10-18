"""Original-client identity and ARM branch encoder."""
import struct
APK_SHA='167a4ac5d2fe653e3403212d37959b954d5f07dd6505456ea85aeb9d7d222312'
ELF_SHA='a0143eec74e3e0fe67b20ac97f3050fd0d3ef2aeafa00c1a73891590f9fc4f73'
ENTRY=0x1320b78

def branch(source,target,link=True):
    distance=target-source-8
    assert distance%4==0 and -(1<<25)<=distance<(1<<25)
    return (0xeb000000 if link else 0xea000000)|((distance//4)&0xffffff)
