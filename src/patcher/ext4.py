"""Read-only ext4 file extraction for official Android lab images (extent inodes)."""
import argparse
from pathlib import Path
import struct


class Ext4:
    def __init__(self, image, partition='system'):
        self.file = Path(image).open('rb')
        self.partition_bytes = Path(image).stat().st_size
        self.base = 0
        sb = self.read(1024, 1024)
        if struct.unpack_from('<H', sb, 56)[0] != 0xEF53:
            self.base = self.android_partition(partition)
            sb = self.read(1024, 1024)
        if struct.unpack_from('<H', sb, 56)[0] != 0xEF53:
            raise ValueError('Expected raw ext4 image')
        self.block = 1024 << struct.unpack_from('<I', sb, 24)[0]
        self.inodes_per_group = struct.unpack_from('<I', sb, 40)[0]
        self.inode_size = struct.unpack_from('<H', sb, 88)[0]
        incompat = struct.unpack_from('<I', sb, 96)[0]
        self.desc_size = max(32, struct.unpack_from('<H', sb, 254)[0]) if incompat & 0x80 else 32
        self.desc_base = (2 if self.block == 1024 else 1)*self.block

    def read(self, offset, size):
        self.file.seek(self.base + offset)
        data = self.file.read(size)
        if len(data) != size:
            raise ValueError('Truncated filesystem data')
        return data

    def android_partition(self, wanted):
        """Google emulator disks: GPT -> super -> one linear logical extent."""
        header = self.read(512, 512)
        if header[:8] != b'EFI PART':
            raise ValueError('Expected ext4 or GPT Android disk')
        lba, count, size = struct.unpack_from('<QII', header, 72)
        if count > 1024 or size < 128 or size > 1024:
            raise ValueError('Invalid GPT bounds')
        table = self.read(lba*512, count*size)
        for index in range(count):
            part = table[index*size:(index+1)*size]
            name = part[56:128].decode('utf-16le').rstrip('\0')
            if name == wanted:
                first, last = struct.unpack_from('<QQ',part,32)
                self.partition_bytes = (last-first+1)*512
                return struct.unpack_from('<Q',part,32)[0]*512
            if name != 'super':
                continue
            base = struct.unpack_from('<Q',part,32)[0]*512
            geometry = self.read(base+4096, 4096)
            if geometry[:4] != b'gDla':
                raise ValueError('Invalid Android logical partition geometry')
            h = self.read(base+12288, 4096)
            if h[:4] != b'0PLA':
                raise ValueError('Invalid Android logical partition header')
            length = struct.unpack_from('<I',h,44)[0]
            if length > 4*1024*1024:
                raise ValueError('Oversized logical partition table')
            tables = self.read(base+12288+struct.unpack_from('<I',h,8)[0],length)
            offset, number, entry = struct.unpack_from('<III',h,80)
            eoffset, enumber, esize = struct.unpack_from('<III',h,92)
            for i in range(number):
                p = tables[offset+i*entry:offset+(i+1)*entry]
                if p[:36].split(b'\0')[0].decode() != wanted:
                    continue
                first, extents = struct.unpack_from('<II',p,40)
                if extents != 1 or first >= enumber:
                    raise ValueError('Only one linear logical extent supported')
                e = tables[eoffset+first*esize:eoffset+(first+1)*esize]
                sectors, kind, data, source = struct.unpack_from('<QIQI',e)
                if kind or source:
                    raise ValueError('Unsupported logical extent type/device')
                self.partition_bytes = sectors*512
                return base+data*512
        raise FileNotFoundError(wanted)

    def inode(self, number):
        group, index = divmod(number-1, self.inodes_per_group)
        desc = self.read(self.desc_base + group*self.desc_size, self.desc_size)
        table = struct.unpack_from('<I', desc, 8)[0]
        if self.desc_size >= 64:
            table |= struct.unpack_from('<I', desc, 40)[0] << 32
        return self.read(table*self.block + index*self.inode_size, self.inode_size)

    def extents(self, data):
        magic, count, maximum, depth, generation = struct.unpack_from('<HHHHI', data)
        if magic != 0xF30A or count > maximum or depth > 5:
            raise ValueError('Invalid extent tree')
        for i in range(count):
            offset = 12+i*12
            if depth:
                logical, low, high, unused = struct.unpack_from('<IIHH', data, offset)
                yield from self.extents(self.read(((high << 32)|low)*self.block, self.block))
            else:
                logical, length, high, low = struct.unpack_from('<IHHI', data, offset)
                unwritten = length > 32768
                count_blocks = length-32768 if unwritten else length
                yield logical, count_blocks, ((high << 32)|low), unwritten

    def contents(self, number):
        inode = self.inode(number)
        mode = struct.unpack_from('<H', inode)[0]
        size = struct.unpack_from('<I', inode, 4)[0] | struct.unpack_from('<I', inode, 108)[0] << 32
        flags = struct.unpack_from('<I', inode, 32)[0]
        if mode & 0xF000 == 0xA000 and size <= 60:
            return inode[40:40+size]
        if not flags & 0x80000:
            raise ValueError('Non-extent inode unsupported')
        if size > 256*1024*1024:
            raise ValueError('Requested file exceeds extraction limit')
        result = bytearray(size)
        for logical, length, physical, unwritten in self.extents(inode[40:100]):
            start = logical*self.block
            count = min(length*self.block, max(0, size-start))
            if count and not unwritten:
                result[start:start+count] = self.read(physical*self.block, count)
        return bytes(result)

    def ls(self, number):
        data = self.contents(number)
        offset = 0
        while offset+8 <= len(data):
            child, length, size, kind = struct.unpack_from('<IHBB', data, offset)
            if length < 8 or offset+length > len(data):
                raise ValueError('Invalid directory entry')
            if child:
                yield data[offset+8:offset+8+size].decode('utf-8'), child, kind
            offset += length

    def lookup(self, path, links=0):
        if links > 12:
            raise ValueError('Too many symlinks')
        number = 2
        parts = Path(path).as_posix().strip('/').split('/')
        prefix = []
        for index, part in enumerate(parts):
            if not part or part == '.':
                continue
            if part == '..':
                raise ValueError('Parent references are not supported')
            names = {name: (child, kind) for name, child, kind in self.ls(number)}
            number, kind = names[part]
            mode = struct.unpack_from('<H', self.inode(number))[0]
            if mode & 0xF000 == 0xA000:
                target = self.contents(number).decode('utf-8')
                rel = target if target.startswith('/') else '/'.join(prefix+[target])
                return self.lookup(rel+'/'+'/'.join(parts[index+1:]), links+1)
            prefix.append(part)
        return number


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('image', type=Path)
    parser.add_argument('path', nargs='?', default='/')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--partition', default='system')
    args = parser.parse_args()
    fs = Ext4(args.image,args.partition)
    number = fs.lookup(args.path)
    if args.output:
        if args.output.exists():
            raise FileExistsError(args.output)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(fs.contents(number))
        print(args.output)
    else:
        for name, ino, kind in fs.ls(number):
            print(kind, ino, name)
