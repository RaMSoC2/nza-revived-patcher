import argparse
import hashlib
import json
from pathlib import Path
import struct

class Elf32:

    def __init__(self, path):
        self.data = Path(path).read_bytes()
        assert self.data[:6] == b'\x7fELF\x01\x01'
        h = struct.unpack_from('<16sHHIIIIIHHHHHH', self.data)
        assert h[2] == 40
        self.loads = [struct.unpack_from('<IIIIIIII', self.data, h[5] + i * h[9]) for i in range(h[10]) if struct.unpack_from('<I', self.data, h[5] + i * h[9])[0] == 1]
        self.sections = [struct.unpack_from('<IIIIIIIIII', self.data, h[6] + i * h[11]) for i in range(h[12])]
        self.symbols = {}
        self.dynamic_symbol_names = {}
        for s in self.sections:
            if s[1] != 11:
                continue
            strings = self.sections[s[6]]
            table = self.data[strings[4]:strings[4] + strings[5]]
            for index, off in enumerate(range(s[4], s[4] + s[5], 16)):
                name, value, size, info, _, section = struct.unpack_from('<IIIBBH', self.data, off)
                end = table.find(b'\x00', name)
                text = table[name:end].decode('utf-8', errors='replace')
                self.dynamic_symbol_names[index] = text
                if text and value:
                    self.symbols[text] = value

    def file_offset(self, address):
        for p in self.loads:
            if p[2] <= address < p[2] + p[4]:
                return p[1] + address - p[2]
        raise ValueError(f'Address not backed by file: {address:#x}')

    def words(self, address, count):
        return struct.unpack_from('<' + 'I' * count, self.data, self.file_offset(address))

    def cstring(self, address):
        if not address:
            return None
        pos = self.file_offset(address)
        end = self.data.find(b'\x00', pos, pos + 2048)
        if end < 0:
            raise ValueError('Unbounded string')
        return self.data[pos:end].decode('utf-8', errors='strict')

    def executable(self, address):
        address &= ~1
        return any((s[2] & 4 and s[3] <= address < s[3] + s[5] for s in self.sections))

    def methods(self, pointer):
        result, seen = ([], set())
        while pointer:
            if pointer in seen:
                raise ValueError('Method list cycle')
            seen.add(pointer)
            following, count = self.words(pointer, 2)
            if count > 5000:
                raise ValueError('Invalid method count')
            for index in range(count):
                selector, types, implementation = self.words(pointer + 8 + index * 12, 3)
                if not self.executable(implementation):
                    raise ValueError('Method implementation outside executable section')
                result.append({'selector': self.cstring(selector), 'type_encoding': self.cstring(types), 'implementation_elf_address': hex(implementation), 'implementation_file_offset': hex(self.file_offset(implementation & ~1)), 'thumb': bool(implementation & 1)})
            pointer = following
        return result

    def classes(self):
        classes, rejected = ([], [])
        for symbol, address in sorted(self.symbols.items()):
            if not symbol.startswith('_OBJC_CLASS_'):
                continue
            try:
                fields = self.words(address, 18)
                name = self.cstring(fields[2])
                if name != symbol[len('_OBJC_CLASS_'):]:
                    raise ValueError('Class name does not match symbol')
                superclass = self.cstring(fields[1]) if fields[1] else None
                meta = self.words(fields[0], 18)
                classes.append({'name': name, 'superclass_name_in_metadata': superclass, 'class_elf_address': hex(address), 'class_file_offset': hex(self.file_offset(address)), 'instance_methods': self.methods(fields[7]), 'class_methods': self.methods(meta[7])})
            except (ValueError, UnicodeError, struct.error) as exc:
                rejected.append({'symbol': symbol, 'address': hex(address), 'reason': str(exc)})
        return (classes, rejected)

    def constant_strings(self):
        result = []
        for section in self.sections:
            if section[1] != 9:
                continue
            for off in range(section[4], section[4] + section[5], 8):
                address, info = struct.unpack_from('<II', self.data, off)
                if self.dynamic_symbol_names.get(info >> 8) != '_OBJC_CLASS_NSConstantString':
                    continue
                try:
                    _, text_pointer, length = self.words(address, 3)
                    text = self.cstring(text_pointer)
                    if len(text.encode('utf-8')) != length:
                        continue
                    result.append({'elf_address': hex(address), 'string_elf_address': hex(text_pointer), 'text': text})
                except (ValueError, UnicodeError, struct.error):
                    continue
        return result

    def selectors(self):
        strings = {address: self.cstring(address) for name, address in self.symbols.items() if name.startswith('.objc_sel_name')}
        result = []
        for section in self.sections:
            if section[1] != 1 or section[2] & 3 != 3:
                continue
            for off in range(section[4], section[4] + section[5] - 7, 4):
                name_pointer, types_pointer = struct.unpack_from('<II', self.data, off)
                if name_pointer not in strings:
                    continue
                try:
                    types = self.cstring(types_pointer) if types_pointer else None
                    if types is not None and (len(types) > 256 or not any((char.isdigit() for char in types))):
                        continue
                    result.append({'elf_address': hex(section[3] + off - section[4]), 'selector': strings[name_pointer], 'type_encoding': types})
                except (ValueError, UnicodeError):
                    continue
        return result
