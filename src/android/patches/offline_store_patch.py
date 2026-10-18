"""Opt-in offline currency grants; no receipt, advertising or server emulation.

Use the original fixed pack quantities and original zero-price purchase path.
All other categories retain their original handler, prices and eligibility.
The retired video entry is a bounded code cave, reachable only by our hook.
"""
import copy
import gzip
import hashlib
import json
import struct

from arm import branch


def store_catalog(archive):
    path = 'assets/StoreResources.json.gzgz'
    before = archive.read(path)
    source = json.loads(gzip.decompress(before))
    revised = copy.deepcopy(source)
    packs = []
    hidden = []
    for item in revised:
        category = item.get('category_name')
        if category not in ('hard_currency', 'free_bucks'):
            continue
        if item['identifier'].startswith('VENDOR_'):
            # These rows are provider navigation, not fixed currency packs.
            # No quantity is invented for variable external offer rewards.
            item['visible_expression'] = 'FALSE'
            hidden.append(item['identifier'])
            continue
        counts = item['purchased_item']
        assert len(counts) == 1 and counts[0]['id'] == 'hard_currency'
        assert counts[0]['type'] == 'currency' and counts[0]['count'] > 0
        item.pop('app_store_identifier', None)
        item.pop('app_store_tier', None)
        item['price'] = {'currency': 'hard_currency', 'value': 0}
        packs.append({'identifier': item['identifier'], 'category': category,
                      'bucks': counts[0]['count']})
    assert [p['bucks'] for p in packs if p['category'] == 'hard_currency'] == [1800, 800, 195, 120, 55, 20]
    assert [p['bucks'] for p in packs if p['category'] == 'free_bucks'] == [10, 20, 55, 120, 195, 800]
    assert len(hidden) == 3
    for old, new in zip(source, revised):
        if old.get('category_name') not in ('hard_currency', 'free_bucks'):
            assert old == new
    payload = gzip.compress(json.dumps(revised, separators=(',', ':')).encode(), mtime=0)
    return {path: payload}, {'packs': packs, 'hidden_external_provider_rows': hidden,
                            'other_catalog_records_identical': True,
                            'input_sha256': hashlib.sha256(before).hexdigest(),
                            'output_sha256': hashlib.sha256(payload).hexdigest()}


def native_patches(elf, strcmp):
    """Currency-only trampoline; delegate grant, debit(0), notify and persist.

    GNU Objective-C dispatch uses objc_msg_lookup -> IMP. All original entry
    arguments and callee-saved registers are restored before the fallback.
    The shared dispatch routine and main hook both keep 8-byte stack alignment.
    Every pointer is PC relative to retain ELF relocation/ASLR behavior.
    """
    start = 0x15b6808
    words, labels, jumps, strings = [], {}, [], []
    def here(): return start + 4 * len(words)
    def emit(word): words.append(word)
    def label(name): labels[name] = here()
    def jump(name, condition=14, link=False):
        jumps.append((len(words), name, condition, link)); emit(0)
    def call(address): emit(branch(here(), address))
    def pointer(register, text):
        # LDR literal; ADD Rd,PC,Rd. Runtime base cancels in the delta.
        strings.append((len(words), register, text)); emit(0)
        emit(0xe08f0000 | (register << 12) | register)
    def selector(text):
        pointer(0, text); call(0x10d9d58); emit(0xe1a01000)
    def dispatch(): jump('dispatch', link=True)
    emit(0xe92d4ff7)  # push r0-r2,r4-r11,lr (48 bytes)
    emit(0xe1a04002)  # item
    selector('categoryName'); emit(0xe1a00004); dispatch()
    emit(0xe3500000); jump('original', 0)
    emit(0xe1a05000)
    selector('UTF8String'); emit(0xe1a00005); dispatch()
    emit(0xe3500000); jump('original', 0)
    emit(0xe1a05000)
    pointer(1, 'hard_currency'); emit(0xe1a00005); call(strcmp)
    emit(0xe3500000); jump('grant', 0)
    pointer(1, 'free_bucks'); emit(0xe1a00005); call(strcmp)
    emit(0xe3500000); jump('original', 1)
    label('grant')
    selector('purchaseWithContext:')
    emit(0xe1a00004); emit(0xe3a02000); dispatch()
    emit(0xe8bd8ff7)  # original handler returns void
    label('original')
    emit(0xe8bd4ff7)
    emit(0xe92d4ff0)  # displaced purchaseItem: first instruction
    emit(branch(here(), 0x15bde44, link=False))
    label('dispatch')
    emit(0xe92d4070)  # push r4-r6,lr
    emit(0xe1a04000); emit(0xe1a05001); emit(0xe1a06002)
    call(0x10da16c)
    emit(0xe1a03000); emit(0xe1a00004); emit(0xe1a01005); emit(0xe1a02006)
    emit(0xe12fff33); emit(0xe8bd8070)
    payload = bytearray(struct.pack('<' + 'I' * len(words), *words))
    for index, register, text in strings:
        position = start + len(payload)
        payload.extend(text.encode() + b'\0')
        payload.extend(b'\0' * (-len(payload) % 4))
        literal = start + len(payload)
        load = start + index * 4
        delta = literal - (load + 8)
        assert 0 <= delta < 4096
        struct.pack_into('<I', payload, index*4, 0xe59f0000 | (register << 12) | delta)
        payload.extend(struct.pack('<I', (position - (load + 12)) & 0xffffffff))
    for index, name, condition, link in jumps:
        word = branch(start + index*4, labels[name], link=link)
        struct.pack_into('<I', payload, index*4, (word & 0x0fffffff) | (condition << 28))
    assert start + len(payload) <= 0x15b6be8, 'Stay inside retired video method'
    patches = []
    def add(address, expected, replacement, reason):
        assert elf.data[address:address+len(expected)] == expected
        patches.append({'address': hex(address),
                        'before': elf.data[address:address+len(replacement)].hex(),
                        'after': replacement.hex(), 'reason': reason})
    def redirect(address, target, expected, reason):
        add(address, bytes.fromhex(expected), struct.pack('<I', branch(address, target, link=False)), reason)
    redirect(0x15bde40, start, 'f04f2de9',
             'Offline Bucks/Free Bucks only: original zero-price purchaseWithContext:, no billing; all other categories resume original handler')
    add(start, bytes.fromhex('f04f2de91cb08de25cd04de25c129fe5'), bytes(payload),
        'Replace retired video-ad method with bounded position-independent currency-only trampoline')
    redirect(0x15b5804, 0x15b4ea4, 'f04f2de9',
             'Free Bucks fixed packs use original standard store-cell renderer')
    redirect(0x15b61f8, 0x15b4f58, 'f04f2de9',
             'Free Bucks fixed packs use original base category handler instead of GetJar/video/offer SDK')
    redirect(0x1429390, 0x14293d4, '0f00000a',
             'Free Bucks uses original ordinary visibility filter without provider-availability filtering')
    return patches
