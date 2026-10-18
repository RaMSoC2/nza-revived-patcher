"""Build isolated local-resource trials, using original parser/cache and assets.

The local manifest is explicitly derived, not a preserved backend response.
Authentication remains the PATCH-001 diagnostic omission. The opt-in offline
store adaptation makes only currency packs free, as explicitly requested.
Original inputs and earlier trial outputs are never overwritten.
"""
import argparse
import copy
import gzip
import hashlib
import json
import struct
import xml.etree.ElementTree as ET
import zipfile
import zlib
from pathlib import Path
from arm import APK_SHA, ELF_SHA, branch, ENTRY
from elf import Elf32

def plt_address(elf, name):
    header = struct.unpack_from('<16sHHIIIIIHHHHHH', elf.data)
    section = elf.sections[header[-1]]
    names = elf.data[section[4]:section[4] + section[5]]
    section_name = lambda off: names[off:names.find(b'\x00', off)].decode()
    reloc = next((s for s in elf.sections if section_name(s[0]) == '.rel.plt'))
    imports = [elf.dynamic_symbol_names[struct.unpack_from('<II', elf.data, o)[1] >> 8] for o in range(reloc[4], reloc[4] + reloc[5], 8)]
    plt = next((s for s in elf.sections if section_name(s[0]) == '.plt'))
    return plt[3] + 20 + imports.index(name) * 12

def static_texture_metadata(archive, basename_keys=False, extra_names=()):
    descriptions = {}
    for path in ['assets/textures-hd.imm.catalog.btc.gzgz', 'assets/business_textures-hd.st.catalog.btc.gzgz']:
        data = gzip.decompress(archive.read(path))
        assert data[:4] == b'CTB\x00'
        strings = struct.unpack_from('<I', data, 24)[0]
        count, pool = struct.unpack_from('<II', data, strings)
        names = []
        for index in range(count):
            offset, length = struct.unpack_from('<II', data, strings + 8 + index * 8)
            name = data[strings + pool + offset:strings + pool + offset + length]
            assert name.endswith(b'\x00')
            names.append(name[:-1].decode('utf-8'))
        table = struct.unpack_from('<I', data, 20)[0]
        count = struct.unpack_from('<H', data, 14)[0]
        for index in range(count):
            descriptor = data[table + index * 12:table + (index + 1) * 12]
            assert len(descriptor) == 12
            descriptions[names[struct.unpack_from('<H', descriptor)[0]]] = descriptor
    files = sorted((n.removeprefix('assets/') for n in archive.namelist() if n.endswith('.pvr.ccz')))
    assert len(files) == 82 and all((n in descriptions for n in files))
    assert all((n not in files and n in descriptions for n in extra_names))
    files = sorted(files + list(extra_names))
    if basename_keys:
        assert len({n.rsplit('/', 1)[-1] for n in files}) == len(files), 'Ambiguous texture basename'
    blob = bytearray(b'NZTD' + struct.pack('<I', len(files)) + b'\x00' * (16 * len(files)))
    for index, name in enumerate(files):
        struct.pack_into('<I', blob, 8 + index * 16, len(blob))
        blob[12 + index * 16:24 + index * 16] = descriptions[name]
        key = name.rsplit('/', 1)[-1] if basename_keys else name
        blob.extend(key.encode() + b'\x00')
    return bytes(blob)

def add_metadata_segment(patched, metadata, legacy_writable=False):
    """Use obsolete build-id note space for the additional program-header row."""
    header = struct.unpack_from('<16sHHIIIIIHHHHHH', patched)
    phoff, phsize, phnum = (header[5], header[9], header[10])
    headers = [struct.unpack_from('<8I', patched, phoff + i * phsize) for i in range(phnum)]
    note = next((p for p in headers if p[0] == 4))
    assert phsize == 32 and note[1] == phoff + phnum * 32 and (note[4] >= 32)
    align = lambda n: n + 4095 & ~4095
    offset = align(len(patched))
    address = align(max((p[2] + p[5] for p in headers if p[0] == 1)))
    new_headers = [(6, phoff, phoff, phoff, (phnum + 1) * 32, (phnum + 1) * 32, 4, 4)]
    new_headers.extend((p for p in headers if p[0] != 4))
    flags = 6 if legacy_writable else 4
    new_headers.append((1, offset, address, address, len(metadata), len(metadata), flags, 4096))
    assert len(new_headers) == phnum + 1
    for index, p in enumerate(new_headers):
        struct.pack_into('<8I', patched, phoff + index * 32, *p)
    struct.pack_into('<H', patched, 44, len(new_headers))
    for index in range(header[12]):
        at = header[6] + index * header[11]
        section = struct.unpack_from('<10I', patched, at)
        if section[1] == 7 and section[4] == note[1]:
            struct.pack_into('<10I', patched, at, *[0] * 10)
    patched.extend(b'\x00' * (offset - len(patched)))
    patched.extend(metadata)
    count = struct.unpack_from('<I', metadata, 4)[0]
    return (address, {'address': hex(address), 'file_offset': hex(offset), 'bytes': len(metadata), 'sha256': hashlib.sha256(metadata).hexdigest(), 'program_headers': len(new_headers), 'stale_build_id_note_removed': True, 'permissions': 'read/write for API16 linker compatibility' if legacy_writable else 'read only', 'source': f'Exact descriptor bytes and names from original CTB catalogs; {count} matched original or explicitly labeled overlay PVR files', 'texture_count': count})

def static_descriptor_fallback(elf, table_address):
    start = 20054676
    words = []
    labels = {}
    jumps = []

    def here():
        return start + len(words) * 4

    def emit(w):
        words.append(w)

    def label(s):
        labels[s] = here()

    def jump(s, c=14):
        jumps.append((len(words), s, c))
        emit(0)

    def call(a):
        emit(branch(here(), a))
    emit(3796750344)
    emit(3785383936)
    emit(branch(here(), 18436388, link=False))
    fallback = here()
    emit(3813670912)
    jump('return', 1)
    emit(3912058624)
    adr_index = len(words)
    emit(0)
    call(17669464)
    emit(3785400320)
    emit(3785359364)
    emit(3785363466)
    call(17670508)
    emit(3785371648)
    emit(3785359364)
    emit(3785363466)
    emit(3778019123)
    emit(3785392128)
    emit(3814195200)
    jump('none', 0)
    literal_index = len(words)
    emit(0)
    emit(3767504905)
    emit(3852038148)
    emit(3800649736)
    label('loop')
    emit(3851747328)
    emit(3767074816)
    emit(3785363464)
    call(plt_address(elf, 'strcmp'))
    emit(3813670912)
    jump('found', 0)
    emit(3800387600)
    emit(3797381121)
    jump('loop', 1)
    label('none')
    emit(3818913792)
    jump('pop')
    label('found')
    emit(3800367108)
    label('pop')
    emit(3904718592)
    label('return')
    emit(3796619280)
    emit(3904735472)
    payload = bytearray(struct.pack('<' + 'I' * len(words), *words))
    text = here()
    payload.extend(b'UTF8String\x00')
    payload.extend(b'\x00' * (-len(payload) % 4))
    delta = text - (start + adr_index * 4 + 8)
    assert 0 <= delta <= 255
    struct.pack_into('<I', payload, adr_index * 4, 3801022464 | delta)
    literal = start + len(payload)
    delta = literal - (start + literal_index * 4 + 8)
    struct.pack_into('<I', payload, literal_index * 4, 3852439552 | delta)
    payload.extend(struct.pack('<I', table_address - (start + (literal_index + 1) * 4 + 8) & 4294967295))
    for index, name, condition in jumps:
        value = branch(start + index * 4, labels[name], link=False)
        struct.pack_into('<I', payload, index * 4, value & 268435455 | condition << 28)
    assert start + len(payload) <= 20055032
    return [(18436376, struct.pack('<I', 3912059120)), (18436380, struct.pack('<I', 3800936464)), (18436384, struct.pack('<I', branch(18436384, start, link=False))), (18436472, struct.pack('<I', branch(18436472, fallback, link=False))), (start, bytes(payload))]

def build(source, output, root):
    source = Path(source).resolve()
    output = Path(output).resolve()
    root = Path(root).resolve()
    output.mkdir(parents=True, exist_ok=False)
    if hashlib.sha256(source.read_bytes()).hexdigest() != APK_SHA:
        raise ValueError('Unsupported original APK')
    overlay = []
    overlay_path = (root / 'manifests/resources.json').resolve()
    assert overlay_path.is_relative_to(root)
    overlay = json.loads(overlay_path.read_text(encoding='utf-8'))
    assert isinstance(overlay, list) and 0 < len(overlay) <= 256
    assert len({r['resource_name'] for r in overlay}) == len(overlay)
    aliases = []
    alias_path = (root / 'manifests/aliases.json').resolve()
    assert alias_path.is_relative_to(root)
    aliases = json.loads(alias_path.read_text(encoding='utf-8'))
    assert isinstance(aliases, list) and 0 < len(aliases) <= 16
    elf_input = output / 'original-engine.elf'
    with zipfile.ZipFile(source) as original_apk:
        elf_input.write_bytes(original_apk.read('lib/armeabi/libverde.so'))
    elf = Elf32(elf_input)
    assert hashlib.sha256(elf.data).hexdigest() == ELF_SHA
    start = 20058148
    words = []
    fixups = []

    def emit(word):
        words.append(word)

    def call(target):
        emit(branch(start + len(words) * 4, target))

    def adr(name):
        fixups.append((len(words), name))
        emit(0)
    emit(3912057328)
    emit(3785375744)
    call(20040484)
    adr('BResourceCache')
    call(17668360)
    call(18599276)
    emit(3785379840)
    adr('NSBundle')
    call(17668360)
    emit(3785392128)
    adr('mainBundle')
    call(17669464)
    emit(3785388032)
    emit(3785363463)
    emit(3785359368)
    call(17670508)
    emit(3785371648)
    emit(3785359368)
    emit(3785363463)
    emit(3778019123)
    emit(3785367552)
    emit(3785359365)
    call(18610564)
    emit(3785359364)
    call(20040700)
    emit(3904733680)
    payload = bytearray(struct.pack('<' + 'I' * len(words), *words))
    strings = {}
    for name in ['BResourceCache', 'NSBundle', 'mainBundle']:
        strings[name] = start + len(payload)
        payload.extend(name.encode() + b'\x00')
    payload.extend(b'\x00' * (-len(payload) % 4))
    for index, name in fixups:
        delta = strings[name] - (start + index * 4 + 8)
        assert 0 <= delta <= 255
        struct.pack_into('<I', payload, index * 4, 3801022464 | delta)
    assert len(payload) < 20058592 - start, 'Do not overwrite original literal pool/callbacks'
    with zipfile.ZipFile(source) as archive:
        original = archive.read('lib/armeabi/libverde.so')
        first = {'before': original[ENTRY:ENTRY + 24].hex(), 'after': struct.pack('<6I', 3912056848, 3785375744, branch(ENTRY + 8, 20040484), 3785359364, branch(ENTRY + 16, 20040700), 3904733200).hex()}
        patched = bytearray(original)
        assert patched[20056952:20056952 + 24].hex() == first['before']
        patched[20056952:20056952 + 24] = bytes.fromhex(first['after'])
        patched[start:start + len(payload)] = payload
        auxiliary_patches = []
        empty = json.loads(gzip.decompress(archive.read('assets/art/frame_animations.json.gzgz')))
        assert empty == []
        address = 20054668
        replacement = struct.pack('<II', 3818913792, 3778019102)
        auxiliary_patches.append({'address': hex(address), 'before': original[address:address + 8].hex(), 'after': replacement.hex(), 'reason': 'Accept verified empty original frame-animation collection; experimental, not recovered remote definitions'})
        patched[address:address + 8] = replacement
        slots = [21530176, 21530180, 21530184]
        old = [bytes(original[a:a + 4]) for a in slots]
        for address, replacement in zip(slots, [old[1], old[2], old[0]]):
            auxiliary_patches.append({'address': hex(address), 'before': original[address:address + 4].hex(), 'after': replacement.hex(), 'reason': 'Load original immediate/streaming texture catalogs before BUIView; retain all original stages'})
            patched[address:address + 4] = replacement
        pvr_files = [n for n in archive.namelist() if n.endswith('.pvr.ccz')]
        assert pvr_files and all(('/textures-hd/' in n or '/business_textures-hd/' in n for n in pvr_files))
        for address, source_address in [(21543192, 21543188), (21537060, 21537056)]:
            replacement = original[source_address:source_address + 4]
            auxiliary_patches.append({'address': hex(address), 'before': original[address:address + 4].hex(), 'after': replacement.hex(), 'reason': 'Select original HD texture catalog matching the packaged PVR variant'})
            patched[address:address + 4] = replacement
        address = 18436844
        replacement = struct.pack('<I', 3778019102)
        auxiliary_patches.append({'address': hex(address), 'before': original[address:address + 4].hex(), 'after': replacement.hex(), 'reason': 'Experimental retention of original catalog dictionaries/data until deferred texture consumers finish; preserve all native loading/rendering code'})
        patched[address:address + 4] = replacement
        metadata_segment = None
        table_address, metadata_segment = add_metadata_segment(patched, static_texture_metadata(archive, basename_keys=int('trial-67'[6:]) >= 14, extra_names=[r['resource_name'] for r in overlay]), legacy_writable=int('trial-67'[6:]) >= 13)
        for address, replacement in static_descriptor_fallback(elf, table_address):
            auxiliary_patches.append({'address': hex(address), 'before': original[address:address + len(replacement)].hex(), 'after': replacement.hex(), 'reason': 'Fallback to immutable original descriptors by exact file name when normal lookup returns nil'})
            patched[address:address + len(replacement)] = replacement
        site = 18436312
        helper = 20054912
        assert struct.unpack_from('<I', original, site)[0] == 3851239424
        code = struct.pack('<4I', 3813670912, branch(helper + 4, 18436356, link=False) & 268435455, 3851239424, branch(helper + 12, site + 4, link=False))
        for address, replacement in [(site, struct.pack('<I', branch(site, helper, link=False))), (helper, code)]:
            auxiliary_patches.append({'address': hex(address), 'before': original[address:address + len(replacement)].hex(), 'after': replacement.hex(), 'reason': 'Return nil for an absent sprite record; preserve original handling of all existing sprites'})
            patched[address:address + len(replacement)] = replacement
        site = 18442888
        helper = 20058288
        assert helper >= start + len(payload) and helper + 20 < 20058592
        assert struct.unpack_from('<I', original, site)[0] == 3851493420
        code = struct.pack('<5I', 3813736448, 60817408, branch(helper + 8, 18443628, link=False) & 268435455, 3851493420, branch(helper + 16, site + 4, link=False))
        for address, replacement in [(site, struct.pack('<I', branch(site, helper, link=False))), (helper, code)]:
            auxiliary_patches.append({'address': hex(address), 'before': original[address:address + len(replacement)].hex(), 'after': replacement.hex(), 'reason': 'PVR parser returns its existing failure result for null payload; no image or decoded data synthesized'})
            patched[address:address + len(replacement)] = replacement
        site = 18401144
        helper = 20054928
        assert struct.unpack_from('<I', original, site)[0] == 3842703408
        text = helper + 64
        words = [3814129664, branch(helper + 4, helper + 56, link=False) & 268435455 | 268435456, 3912060943, 3852009480, 3813670935, branch(helper + 20, helper + 44, link=False) & 268435455 | 268435456, 3852009476, 3801026588, 3818922007, branch(helper + 36, plt_address(elf, 'memcmp')), 3813670912, 3904720911, 60817408, branch(helper + 52, 18401668, link=False) & 268435455, 3842703408, branch(helper + 60, site + 4, link=False)]
        assert helper + 28 + 8 + 28 == text
        code = struct.pack('<16I', *words) + b'gate_tower_top_junkyard\x00'
        assert helper + len(code) <= 20055032
        for address, replacement in [(site, struct.pack('<I', branch(site, helper, link=False))), (helper, code)]:
            auxiliary_patches.append({'address': hex(address), 'before': original[address:address + len(replacement)].hex(), 'after': replacement.hex(), 'reason': 'For the exact captured absent gate sprite only, return nil before filename fallback; experimental visual omission, no substitute asset'})
            patched[address:address + len(replacement)] = replacement
        site = 18444492
        helper = 20058308
        assert helper >= start + len(payload) and helper + 16 < 20058592
        assert struct.unpack_from('<I', original, site)[0] == 3852300564
        code = struct.pack('<4I', 3813670912, branch(helper + 4, 18445716, link=False) & 268435455, 3852300564, branch(helper + 12, site + 4, link=False))
        for address, replacement in [(site, struct.pack('<I', branch(site, helper, link=False))), (helper, code)]:
            auxiliary_patches.append({'address': hex(address), 'before': original[address:address + len(replacement)].hex(), 'after': replacement.hex(), 'reason': 'Stop original texture upload on failed PVR parse before using uninitialized dimensions or mip pointers'})
            patched[address:address + len(replacement)] = replacement
        address = 17871620
        assert struct.unpack_from('<I', original, address)[0] == 167772171
        replacement = struct.pack('<I', branch(address, 17871672, link=False))
        auxiliary_patches.append({'address': hex(address), 'before': original[address:address + 4].hex(), 'after': replacement.hex(), 'reason': 'Use original DJBHash getCharacters:range: fallback instead of reading UTF8String bytes as UTF-16 units'})
        patched[address:address + 4] = replacement
        site = 18295024
        helper = 20058324
        assert struct.unpack_from('<I', original, site)[0] == 3800395602
        assert helper + 20 < 20058592
        code = struct.pack('<5I', 3813670912, branch(helper + 4, 18295072, link=False) & 268435455, 3785375744, 3800395602, branch(helper + 16, site + 4, link=False))
        for address, replacement in [(site, struct.pack('<I', branch(site, helper, link=False))), (helper, code)]:
            auxiliary_patches.append({'address': hex(address), 'before': original[address:address + len(replacement)].hex(), 'after': replacement.hex(), 'reason': 'Propagate failed image initializer and use returned receiver instead of messaging a released texture object'})
            patched[address:address + len(replacement)] = replacement
        site = 20089264
        helper = 20058344
        assert struct.unpack_from('<I', original, site)[0] == 3884449799
        selector = elf.words(20166504, 1)[0] + 20165956 + elf.words(20166496, 1)[0] + 248 & 4294967295
        assert elf.cstring(elf.words(selector, 1)[0]) == 'retain'
        words = [3912056944, 3785375744, 3852423204, 3767488517, 3785363461, branch(helper + 20, plt_address(elf, 'objc_msg_lookup')), 3785371648, 3785359364, 3785363461, 3778019123, 3884449799, 3904716912, branch(helper + 48, site + 4, link=False), selector - (helper + 20) & 4294967295]
        code = struct.pack('<14I', *words)
        assert helper + len(code) < 20058592
        for address, replacement in [(site, struct.pack('<I', branch(site, helper, link=False))), (helper, code)]:
            auxiliary_patches.append({'address': hex(address), 'before': original[address:address + len(replacement)].hex(), 'after': replacement.hex(), 'reason': 'Retain the original platform MACAddress string once when caching it, preserving the original save identifier derivation'})
            patched[address:address + len(replacement)] = replacement
        site = 22859536
        helper = 20058400
        assert struct.unpack_from('<I', original, site)[0] == 3852279852
        words = [3852279852, 3813801984, branch(helper + 8, site + 4, link=False) & 268435455 | 268435456, 3813867520, branch(helper + 16, site + 4, link=False) & 268435455 | 268435456, 3852410884, 3852414980, branch(helper + 28, site + 4, link=False), 1125515264, 1112801280]
        code = struct.pack('<10I', *words)
        assert helper + len(code) < 20058592
        for address, replacement in [(site, struct.pack('<I', branch(site, helper, link=False))), (helper, code)]:
            auxiliary_patches.append({'address': hex(address), 'before': original[address:address + len(replacement)].hex(), 'after': replacement.hex(), 'reason': 'Experimental missing-image nameplate hit area uses existing layout target150x53 only for zero dimensions; no graphics synthesized'})
            patched[address:address + len(replacement)] = replacement
        replacement = struct.pack('<I', 3818923202)
        assert struct.unpack('<f', struct.pack('<I', 3254779904))[0] == -32
        for site in [23251024, 23251144, 23251224]:
            assert struct.unpack_from('<I', original, site)[0] == 3818921984
            auxiliary_patches.append({'address': hex(site), 'before': original[site:site + 4].hex(), 'after': replacement.hex(), 'reason': 'Construction-only local horizontal offset -32 to keep cost and SPECIAL clear of the right HUD; preserve original Y positions, prices and actions'})
            patched[site:site + 4] = replacement
        helper = 20058464
        words = [3912056851, 3778019123, 3852271616, 3852410884, branch(helper + 16, 19619544), 3904733203]
        reason = 'User-requested 30 percent uniform reduction of construction cost and SPECIAL nodes only; preserve original tag, price, availability and action; use original CCNode scale setter'
        restore = helper + 68
        conditional = lambda site, condition: branch(site, restore, link=False) & 268435455 | condition << 28
        words = [3912056851, 3778019123, 3852271616, branch(helper + 12, 19637996), 3813670912, conditional(helper + 20, 0), 3785375744, branch(helper + 28, 19933436), 3813670913, conditional(helper + 36, 1), 3785359364, 3818921984, branch(helper + 48, 19933612), 3813670912, conditional(helper + 56, 0), 3852410884, branch(helper + 64, 19619544), 3904733203]
        reason = 'User-requested 30 percent scale on the sole original CCMenuItem child of each construction menu; wrapper and building anchors remain original; preserve tags, prices and actions; guard child count before indexing'
        code = struct.pack('<' + 'I' * len(words) + 'f', *words, 0.7)
        assert helper + len(code) < 20058592
        sites = [23253300, 23253360]
        for site in sites:
            assert struct.unpack_from('<I', original, site)[0] == 3778019123
        for address, replacement in [(site, struct.pack('<I', branch(site, helper))) for site in sites] + [(helper, code)]:
            auxiliary_patches.append({'address': hex(address), 'before': original[address:address + len(replacement)].hex(), 'after': replacement.hex(), 'reason': reason})
            patched[address:address + len(replacement)] = replacement
        site = 18183516
        assert struct.unpack_from('<I', original, site)[0] == 3767144457
        replacement = struct.pack('<I', 3851882520)
        auxiliary_patches.append({'address': hex(site), 'before': original[site:site + 4].hex(), 'after': replacement.hex(), 'reason': 'Use verified allocated atlas bytes at r7+0x18 for glBufferData; avoid truncating live vertices to the current dirty range, preserve CPU backing data and native capacity growth'})
        patched[site:site + 4] = replacement
        site = 19958548
        helper = 20058544
        assert struct.unpack_from('<2I', original, site) == (3796619276, 3904735344)
        disable = plt_address(elf, 'glDisableVertexAttribArray')
        words = []
        for attribute in [3, 4, 5]:
            words.append(3818913792 | attribute)
            words.append(branch(helper + len(words) * 4, disable))
        words.extend([3796619276, 3904735344])
        code = struct.pack('<8I', *words)
        assert helper + len(code) <= 20058592
        for address, replacement in [(site, struct.pack('<I', branch(site, helper, link=False))), (helper, code)]:
            auxiliary_patches.append({'address': hex(address), 'before': original[address:address + len(replacement)].hex(), 'after': replacement.hex(), 'reason': 'Reset stale BG-only GL attributes 3..5 at original Cocos attribute-mask return; preserve virtual VAOs, original pixels and gameplay'})
            patched[address:address + len(replacement)] = replacement
        store_changes = {}
        store_evidence = None
        from offline_store_patch import store_catalog, native_patches
        store_changes, store_evidence = store_catalog(archive)
        for patch in native_patches(elf, plt_address(elf, 'strcmp')):
            address = int(patch['address'], 16)
            before = bytes.fromhex(patch['before'])
            after = bytes.fromhex(patch['after'])
            assert bytes(patched[address:address + len(before)]) == before, 'Overlapping native patch'
            patched[address:address + len(after)] = after
            auxiliary_patches.append(patch)
        ui_changes = {}
        ui_evidence = []
        from town_name_credit_patch import ui_resources, native_patches as town_patches
        ui_changes, ui_evidence = ui_resources(archive, True, 'Patched by RaMsOc2')
        for patch in town_patches(elf, plt_address(elf, 'class_addMethod'), plt_address(elf, 'NSLog')):
            address = int(patch['address'], 16)
            before = bytes.fromhex(patch['before'])
            after = bytes.fromhex(patch['after'])
            assert bytes(patched[address:address + len(before)]) == before, 'Overlapping native UI patch'
            patched[address:address + len(after)] = after
            auxiliary_patches.append(patch)
        bundle_changes = store_changes | ui_changes
        catalog = ET.fromstring(archive.read('assets/assets.xml'))
        manifest = {}
        unresolved = []
        additions = {}
        for asset in catalog:
            name = asset.attrib['orig_path']
            path = 'assets/' + name
            candidates = [n for n in archive.namelist() if n.startswith('assets/') and n.rsplit('/', 1)[-1] == name.rsplit('/', 1)[-1] and (archive.getinfo(n).file_size == int(asset.attrib['size']))]
            if len(candidates) != 1:
                unresolved.append(name)
                continue
            path = candidates[0]
            content = bundle_changes.get(path, archive.read(path))
            if path in bundle_changes:
                asset.attrib['size'] = str(len(content))
            resource_path = path.removeprefix('assets/')
            if 'trial-67' != 'trial-01' and resource_path.endswith('.gzgz'):
                resource_path = resource_path[:-2]
                additions['assets/' + resource_path] = content
            entry = {'path': resource_path, 'md5': hashlib.md5(content).hexdigest(), 'size': len(content)}
            manifest[name] = entry
            if name.endswith('.gzgz') and 'trial-67' != 'trial-01':
                manifest[name[:-2]] = entry
            manifest[resource_path] = entry
            manifest[path.removeprefix('assets/')] = entry
        manifest = {k: v for k, v in manifest.items() if not k.endswith('.catalog.btc.gzgz')}
        overlay_evidence = []
        for item in overlay:
            name = item['resource_name']
            path = 'assets/' + name
            assert name.startswith('business_textures-hd/') and name.endswith('.pvr.ccz')
            assert '..' not in name and '\\' not in name and (path not in archive.namelist()) and (path not in additions)
            assert item['kind'] in ['diagnostic_control', 'recreated_experimental']
            assert bool(item.get('source_archive_entry')) != bool(item.get('source_file'))
            if item.get('source_archive_entry'):
                content = archive.read(item['source_archive_entry'])
            else:
                resource_source = (root / item['source_file']).resolve()
                assert resource_source.is_relative_to(root)
                content = resource_source.read_bytes()
            assert hashlib.sha256(content).hexdigest() == item['sha256']
            assert content[:4] == b'CCZ!' and len(content) < 32 * 1024 * 1024
            reader = zlib.decompressobj()
            decoded = reader.decompress(content[16:], 32 * 1024 * 1024 + 1)
            assert reader.eof and len(decoded) <= 32 * 1024 * 1024
            pvr = struct.unpack_from('<13I', decoded)
            assert pvr[0] == 52 and pvr[11] == 559044176
            assert pvr[2] == item['width'] and pvr[1] == item['height']
            additions[path] = content
            entry = {'path': name, 'md5': hashlib.md5(content).hexdigest(), 'size': len(content)}
            manifest[name] = entry
            manifest[name.rsplit('/', 1)[-1]] = entry
            ET.SubElement(catalog, 'asset', {'url': '', 'orig_path': name.rsplit('/', 1)[-1], 'hash_path': name, 'size': str(len(content)), 'source': 'apk'})
            overlay_evidence.append(item | {'payload_bytes': len(content), 'original_asset_recovered': False})
        alias_evidence = []
        for item in aliases:
            name = item['resource_name']
            path = 'assets/' + name
            source_name = item['source_archive_entry']
            assert name.startswith('ui_assets-hd/') and name.endswith('.png') and ('..' not in name) and ('\\' not in name)
            assert path not in archive.namelist() and path not in additions and (name not in manifest)
            assert item['kind'] == 'original_asset_reuse_experimental' and item['reason']
            assert source_name.startswith('assets/ui_assets-hd/') and source_name.endswith('.png')
            content = archive.read(source_name)
            assert content.startswith(b'\x89PNG\r\n\x1a\n') and hashlib.sha256(content).hexdigest() == item['sha256']
            source_path = source_name.removeprefix('assets/')
            transform = {}
            if 'resample_size' in item:
                import io
                from PIL import Image
                dimensions = item['resample_size']
                assert len(dimensions) == 2 and all((type(n) is int and 0 < n <= 2048 for n in dimensions))
                with Image.open(io.BytesIO(content)) as source_image:
                    transform = {'source_size': list(source_image.size), 'resample_size': dimensions, 'filter': 'LANCZOS'}
                    adapted = source_image.convert('RGBA').resize(tuple(dimensions), Image.Resampling.LANCZOS)
                    encoded = io.BytesIO()
                    adapted.save(encoded, format='PNG')
                    content = encoded.getvalue()
                source_path = name
                additions[path] = content
            entry = {'path': source_path, 'md5': hashlib.md5(content).hexdigest(), 'size': len(content)}
            short = name.rsplit('/', 1)[-1]
            assert short not in manifest
            manifest[name] = entry
            manifest[short] = entry
            ET.SubElement(catalog, 'asset', {'url': '', 'orig_path': short, 'hash_path': source_path, 'size': str(len(content)), 'source': 'apk'})
            alias_evidence.append(item | {'original_art_source': True, 'original_pixels': not bool(transform), 'original_asset_recovered': False, 'no_pixel_edits': not bool(transform), 'packaging_transform': transform, 'output_sha256': hashlib.sha256(content).hexdigest()})
        manifest_data = json.dumps(manifest, separators=(',', ':')).encode()
        ET.SubElement(catalog, 'asset', {'url': '', 'orig_path': 'manifest.json', 'hash_path': 'manifest.json', 'size': str(len(manifest_data)), 'source': 'apk'})
        catalog_data = ET.tostring(catalog, encoding='utf-8', xml_declaration=True)
        changes = {'lib/armeabi/libverde.so': bytes(patched), 'assets/assets.xml': catalog_data}
        changes.update(bundle_changes)
        foundation_patch = None
        foundation = archive.read('lib/armeabi/libfoundation.so')
        foundation_sha = hashlib.sha256(foundation).hexdigest()
        assert foundation_sha == '422694a02adb7968a283d35893e38e8b2c809d5b89e1035e991d301da3849a7b'
        address = 1617632
        assert struct.unpack_from('<I', foundation, address)[0] == 3850727432
        replacement = struct.pack('<I', 3850719240)
        replacement = struct.pack('<I', 3850731528)
        revised = bytearray(foundation)
        revised[address:address + 4] = replacement
        changes['lib/armeabi/libfoundation.so'] = bytes(revised)
        foundation_patch = {'address': hex(address), 'input_sha256': foundation_sha, 'output_sha256': hashlib.sha256(revised).hexdigest(), 'before': foundation[address:address + 4].hex(), 'after': replacement.hex(), 'reason': 'Generic NSArray enumeration uses a valid state cursor address instead of treating item count as a pointer; experimental immutable-array compatibility, no added mutation detection'}
        foundation_patch['reason'] = 'Generic NSArray enumeration uses the retained receiver class-word address, stable across batches; fixes the verified false 16-to-32 mutation check. Generic fallback still has no real mutation detection; mutable overrides remain unchanged.'
        apk = output / 'local-resources-unsigned.apk'
        with zipfile.ZipFile(apk, 'w') as destination:
            for info in archive.infolist():
                name = info.filename
                if name.startswith('META-INF/') and (name == 'META-INF/MANIFEST.MF' or name.upper().endswith(('.SF', '.RSA', '.DSA', '.EC'))):
                    continue
                destination.writestr(copy.copy(info), changes.get(name, archive.read(name)))
            destination.writestr('assets/manifest.json', manifest_data, compress_type=zipfile.ZIP_DEFLATED)
            for name, content in additions.items():
                assert name not in archive.namelist()
                destination.writestr(name, content, compress_type=zipfile.ZIP_DEFLATED)
        with zipfile.ZipFile(apk) as verify:
            assert verify.testzip() is None
            for name in verify.namelist():
                if name in changes or name == 'assets/manifest.json':
                    continue
                if name in additions:
                    assert verify.read(name) == additions[name]
                    continue
                assert verify.read(name) == archive.read(name)
        record = {'profile': 'revived-0.1', 'input_apk_sha256': APK_SHA, 'manifest_entries': len(manifest), 'unresolved_catalog_paths': unresolved, 'manifest_provenance': 'Derived from original assets and explicitly labeled experimental additions/aliases' if overlay_evidence or alias_evidence else 'Derived from original assets, identity names only; not a server response', 'manifest_stage_patch': {'address': hex(start), 'length': len(payload), 'before': original[start:start + len(payload)].hex(), 'after': payload.hex()}, 'original_entry_changes': list(changes), 'added_entries': ['assets/manifest.json'] + list(additions), 'auxiliary_patches': auxiliary_patches, 'metadata_segment': metadata_segment, 'foundation_patch': foundation_patch, 'offline_store': store_evidence, 'experimental_ui': ui_evidence, 'resource_overlay': overlay_evidence, 'resource_aliases': alias_evidence, 'output_elf_sha256': hashlib.sha256(patched).hexdigest(), 'output_unsigned_apk_sha256': hashlib.sha256(apk.read_bytes()).hexdigest()}
        (output / 'patch.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
        (output / 'manifest-derived.json').write_bytes(manifest_data)
    print(json.dumps({'profile': 'revived-0.1', 'manifest_entries': len(manifest), 'unresolved_count': len(unresolved), 'stub_bytes': len(payload)}))
