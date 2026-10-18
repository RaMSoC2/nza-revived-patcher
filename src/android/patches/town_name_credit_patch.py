"""Reversible local sign-name preference and loading annotation.

Keep GPS locality and gameplay saves original. Only the sign's display reads
the separate NSUserDefaults key. The hidden development button is reused as
an explicitly experimental local editor. No server response is fabricated.
"""
import base64
import copy
import hashlib
import struct
import xml.etree.ElementTree as ET

from arm import branch

KEY = 'nza.customTownSignName.v1'


def ui_resources(archive, town_name=False, credit=None):
    changes, evidence = {}, []
    if credit:
        assert len(credit) <= 80 and all(ord(c) >= 32 for c in credit)
        name = 'assets/ZTLoading.xib'
        before = archive.read(name)
        tree = ET.fromstring(before)
        ids = {x.get('id'): x for x in tree.iter() if x.get('id')}
        root = ids['723828237']
        label = copy.deepcopy(ids['401656793'])
        label.set('id', '900100001')
        for x in label.iter():
            if x is not label and x.get('id'):
                x.set('id', '900100002')
        label.find("string[@key='NSFrame']").text = '{{175, 294}, {245, 22}}'
        label.find("string[@key='IBUIText']").text = credit
        label.find("int[@key='IBUITextAlignment']").text = '1'
        label.find("object[@key='IBUIFontDescription']/double[@key='pointSize']").text = '12'
        label.find("object[@key='IBUIFont']/double[@key='NSSize']").text = '12'
        color = label.find("reference[@key='IBUITextColor']")
        index = list(label).index(color); label.remove(color)
        color = ET.Element('object', {'class': 'NSColor', 'key': 'IBUITextColor'})
        ET.SubElement(color, 'int', {'key': 'NSColorSpace'}).text = '1'
        ET.SubElement(color, 'bytes', {'key': 'NSRGB'}).text = base64.b64encode(b'1 1 1\0').decode().rstrip('=')
        label.insert(index, color)
        root.find("*[@key='NSSubviews']").append(label)
        records = next(x for x in tree.iter('object') if x.get('key') == 'objectRecords')
        ordered = records.find("*[@key='orderedObjects']")
        assert ordered is not None
        record = ET.SubElement(ordered, 'object', {'class': 'IBObjectRecord'})
        ET.SubElement(record, 'int', {'key': 'objectID'}).text = '9001'
        ET.SubElement(record, 'reference', {'key': 'object', 'ref': '900100001'})
        ET.SubElement(record, 'reference', {'key': 'parent', 'ref': '723828237'})
        root_record = next(x for x in ordered if x.find("reference[@key='object'][@ref='723828237']") is not None)
        ET.SubElement(root_record.find("object[@key='children']"), 'reference', {'ref': '900100001'})
        changes[name] = ET.tostring(tree, encoding='utf-8', xml_declaration=True)
        evidence.append({'entry': name, 'input_sha256': hashlib.sha256(before).hexdigest(),
                         'output_sha256': hashlib.sha256(changes[name]).hexdigest(),
                         'change': 'Additional transparent UILabel; original version, tips, progress and artwork retained',
                         'credit': credit})
    if town_name:
        name = 'assets/ZTSettingsView.xib'
        before = archive.read(name)
        tree = ET.fromstring(before)
        ids = {x.get('id'): x for x in tree.iter() if x.get('id')}
        button = ids['643127111']
        button.find("string[@key='NSFrame']").text = '{{12, 15}, {126, 32}}'
        button.find("string[@key='IBUINormalTitle']").text = 'Town Name'
        changes[name] = ET.tostring(tree, encoding='utf-8', xml_declaration=True)
        evidence.append({'entry': name, 'input_sha256': hashlib.sha256(before).hexdigest(),
                         'output_sha256': hashlib.sha256(changes[name]).hexdigest(),
                         'change': 'Reuse hidden DEBUG button as Town Name; relocate into free space beside audio controls; other controls unchanged'})
    return changes, evidence


class Arm:
    def __init__(self, start):
        self.start = start; self.words = []; self.labels = {}; self.jumps = []; self.ptrs = []; self.literals = []
    def here(self): return self.start + len(self.words)*4
    def emit(self, word): self.words.append(word)
    def mov(self, dest, source): self.emit(0xe1a00000 | (dest << 12) | source)
    def imm(self, dest, value):
        assert 0 <= value < 256
        self.emit(0xe3a00000 | (dest << 12) | value)
    def call(self, address): self.emit(branch(self.here(), address))
    def mark(self, name): self.labels[name] = self.here()
    def jump(self, name, cond=14, link=False):
        self.jumps.append((len(self.words), name, cond, link)); self.emit(0)
    def ptr(self, reg, value):
        self.ptrs.append((len(self.words), reg, value)); self.emit(0)
        self.emit(0xe08f0000 | (reg << 12) | reg)
    def literal(self, reg, value):
        self.literals.append((len(self.words), reg, value)); self.emit(0)
    def sel(self, name): self.ptr(0, name); self.call(0x10d9d58); self.mov(1, 0)
    def send(self, receiver, name, arg=None, arg2=None):
        self.sel(name); self.mov(0, receiver)
        if arg is not None: self.mov(2, arg)
        if arg2 is not None: self.mov(3, arg2)
        self.jump('send', link=True)
    def string(self, text, dest):
        self.ptr(0, text); self.jump('nsstring', link=True); self.mov(dest, 0)
    def singleton(self, cls, selector, dest):
        self.ptr(0, cls); self.call(0x10d9908); self.mov(dest, 0)
        self.send(dest, selector); self.mov(dest, 0)
    def enter(self): self.emit(0xe92d47f0); self.emit(0xe24dd020)  # 8 registers; 32-byte local/argument area
    def leave(self): self.emit(0xe28dd020); self.emit(0xe8bd87f0)
    def finish(self):
        result = bytearray(struct.pack('<'+'I'*len(self.words), *self.words))
        pool = {}
        for index, reg, value in self.ptrs:
            if isinstance(value, int):
                address = value
            elif isinstance(value, tuple):
                address = self.labels[value[0]]
            elif value in pool:
                address = pool[value]
            else:
                address = self.start + len(result); pool[value] = address
                result.extend(value.encode() + b'\0'); result.extend(b'\0'*(-len(result)%4))
            literal = self.start + len(result)
            load = self.start + index*4
            distance = literal-(load+8); assert 0 <= distance < 4096
            struct.pack_into('<I', result, index*4, 0xe59f0000 | (reg << 12) | distance)
            result.extend(struct.pack('<I', (address-(load+12)) & 0xffffffff))
        for index, target, cond, link in self.jumps:
            word = branch(self.start+index*4, self.labels[target], link=link)
            struct.pack_into('<I', result, index*4, (word & 0x0fffffff) | (cond << 28))
        for index, reg, value in self.literals:
            distance = len(result)-(index*4+8); assert 0 <= distance < 4096
            struct.pack_into('<I', result, index*4, 0xe59f0000 | (reg << 12) | distance)
            result.extend(struct.pack('<I', value))
        return bytes(result)


def native_patches(elf, class_add_method, nslog):
    # Offline-store reroutes every Free Bucks action; these provider methods
    # are retired. Stay within displayOfferWall/showReward/grantGetJar region.
    a = Arm(0x15b6be8)
    a.mark('open'); a.enter(); a.mov(4, 0)
    a.ptr(0, 'ZTSettingsViewController'); a.call(0x10d9908); a.mov(5, 0)
    a.sel('alertView:clickedButtonAtIndex:'); a.mov(0, 5)
    a.ptr(2, ('save',)); a.ptr(3, 'v16@0:4@8i12'); a.call(class_add_method)
    a.string('Name Your Town', 6)
    a.string('Set the sign name. Leave blank to use GPS.', 7)
    a.string('Cancel', 8); a.string('Save', 9)
    a.singleton('UIAlertView', 'alloc', 5)
    a.emit(0xe58d4000); a.emit(0xe58d8004); a.emit(0xe58d9008)
    a.imm(0, 0); a.emit(0xe58d000c)
    a.send(5, 'initWithTitle:message:delegate:cancelButtonTitle:otherButtonTitles:', 6, 7); a.mov(5, 0)
    # Apportable's Java AlertView.setStyle is empty. Its show() does support
    # UITextField subviews, so create that original widget explicitly.
    a.singleton('UITextField', 'alloc', 10)
    a.literal(6, 0x43960000); a.emit(0xe58d6000)  # CGRect width 300
    a.literal(6, 0x42200000); a.emit(0xe58d6004)  # height 40
    a.imm(6, 0); a.send(10, 'initWithFrame:', 6, 6); a.mov(10, 0)
    a.imm(6, 3); a.send(10, 'setBorderStyle:', 6)
    a.send(5, 'addSubview:', 10)
    # Reproduce textFieldAtIndex:'s verified GNU ivar indirection, then add
    # the widget to UIAlertView's original retained text-field array.
    field_slot = (elf.words(0x17b14d0, 1)[0] + elf.words(0x17b14cc, 1)[0] + 0x17b1488) & 0xffffffff
    assert field_slot == 0x1d05934
    a.ptr(6, field_slot)
    a.emit(0xe5966000); a.emit(0xe5966000); a.emit(0xe5966000)
    a.emit(0xe7956006)
    a.send(6, 'addObject:', 10)
    a.singleton('NSUserDefaults', 'standardUserDefaults', 6); a.string(KEY, 7)
    a.send(6, 'stringForKey:', 7); a.mov(6, 0); a.send(10, 'setText:', 6)
    a.send(10, 'autorelease'); a.send(5, 'show'); a.send(5, 'autorelease'); a.leave()
    a.mark('save'); a.enter(); a.mov(9, 0); a.mov(5, 2)
    a.emit(0xe3530001); a.jump('saved', cond=1)
    a.string('NZA: town-name Save callback', 4); a.mov(0, 4); a.call(nslog)
    a.imm(6, 0); a.send(5, 'textFieldAtIndex:', 6); a.mov(5, 0)
    a.send(5, 'text'); a.mov(6, 0)
    a.singleton('NSCharacterSet', 'whitespaceAndNewlineCharacterSet', 7)
    a.send(6, 'stringByTrimmingCharactersInSet:', 7); a.mov(6, 0)
    a.send(6, 'length'); a.mov(4, 0)
    a.string('NZA: town-name text length %u', 7); a.mov(0, 7); a.mov(1, 4); a.call(nslog)
    a.singleton('NSUserDefaults', 'standardUserDefaults', 5); a.string(KEY, 7)
    a.send(5, 'setObject:forKey:', 6, 7); a.send(5, 'synchronize')
    # Follow the original settings-state delegate to the active scene. KVO
    # does not redraw when GPS locality is unchanged, so refresh explicitly.
    a.send(9, 'delegate'); a.mov(5, 0)
    a.send(5, 'townVC'); a.mov(5, 0)
    a.send(5, 'isoViewController'); a.mov(5, 0)
    a.imm(6, 0); a.send(5, 'refreshGateLabel:', 6)
    a.mark('saved'); a.leave()
    a.mark('display'); a.enter(); a.emit(0xe12fff32); a.mov(4, 0)  # original currentLocality IMP in r2
    a.singleton('NSUserDefaults', 'standardUserDefaults', 5); a.string(KEY, 6)
    a.send(5, 'stringForKey:', 6); a.mov(5, 0)
    a.send(5, 'length'); a.emit(0xe3500000)
    a.mov(0, 4); a.jump('display_return', cond=0)
    a.mov(0, 5)
    a.mark('display_return'); a.leave()
    a.mark('nsstring')
    a.emit(0xe92d4070); a.mov(4, 0)
    a.ptr(0, 'NSString'); a.call(0x10d9908); a.mov(5, 0)
    a.send(5, 'stringWithUTF8String:', 4)
    a.emit(0xe8bd8070)
    a.mark('send')
    # Forward r0-r3 and four stack words, needed by UIAlertView's initializer.
    a.emit(0xe92d41f0); a.emit(0xe24dd010)
    for d, s in [(4, 0), (5, 1), (6, 2), (7, 3)]: a.mov(d, s)
    a.call(0x10da16c); a.mov(8, 0)
    a.emit(0xe28dc028); a.emit(0xe89c000f); a.emit(0xe88d000f)
    for d, s in [(0, 4), (1, 5), (2, 6), (3, 7)]: a.mov(d, s)
    a.emit(0xe12fff38); a.emit(0xe28dd010); a.emit(0xe8bd81f0)
    code = a.finish(); assert a.start+len(code) <= 0x15b7638
    patches = []
    def add(address, expected, replacement, reason):
        expected = bytes.fromhex(expected)
        assert elf.data[address:address+len(expected)] == expected
        patches.append({'address': hex(address), 'before': elf.data[address:address+len(replacement)].hex(),
                        'after': replacement.hex(), 'reason': reason})
    add(a.start, 'f04f2de9', code, 'Retired offline-store provider region: local town sign editor, display-only preference, original UIKit dialog and explicit gate refresh')
    add(0x158b978, '70482de9', struct.pack('<I', branch(0x158b978, a.labels['open'], link=False)), 'Reuse hidden development-button action for experimental local town-name editor')
    add(0x158b284, '0120a0e3', struct.pack('<I', 0xe3a02000), 'Show Town Name button in settings')
    add(0x158b2c0, '0020a0e3', struct.pack('<I', 0xe3a02001), 'Enable Town Name button in settings')
    add(0x15d67ec, '32ff2fe1', struct.pack('<I', branch(0x15d67ec, a.labels['display'])), 'Sign display only: prefer local custom name, otherwise preserve GPS currentLocality; coordinates and gameplay data unchanged')
    return patches
