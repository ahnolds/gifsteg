"""
The append implementation of the GIF steganography suite
"""

from maybe_open import maybe_open
import struct

def copy_blocks(in_f, out_f):
    """
    Copy through blocks of data
    """
    while True:
        # Read the block size
        block_size = in_f.read(1)
        if len(block_size) != 1:
            raise RuntimeError('The Block is too short to be valid')
        block_size, = struct.unpack('<B', block_size)

        # Read the data in the block
        block_data = in_f.read(block_size)
        if len(block_data) != block_size:
            raise RuntimeError('The Block is shorter than specified')

        # Write the size and data to the output
        out_f.write(bytes([block_size]))
        out_f.write(block_data)

        # Length zero block signals the end of the data
        if block_size == 0:
            break

def steg(in_path, out_path=None, data=None):
    """
    The steg function (add the data after the terminator)
    """
    with open(in_path, 'rb') as in_f:
        with maybe_open(out_path, 'wb') as out_f:
            # First the Header
            header = in_f.read(6)
            if len(header) != 6:
                raise RuntimeError('The Header is too short to be valid')
            signature, version = struct.unpack('<3s3s', header)
            if signature != b'GIF':
                raise RuntimeError('The signature does not match the GIF specification')
            out_f.write(header)

            # Next the Logical Screen Descriptor
            screen_descriptor = in_f.read(7)
            if len(screen_descriptor) != 7:
                raise RuntimeError('The Logical Screen Descriptor is too short to be valid')
            width, heigh, packed, bg_color_index, aspect_ratio = struct.unpack('<2H3B', screen_descriptor)
            has_gct   = (packed & 0b10000000) >> 7
            color_res = (packed & 0b01110000) >> 4
            sort_flag = (packed & 0b00001000) >> 3
            gct_size  = (packed & 0b00000111) >> 0
            out_f.write(screen_descriptor)

            # Then the Global Color Table (if present)
            if has_gct:
                true_gct_size = 3 * (2 ** (gct_size + 1))
                gct = in_f.read(true_gct_size)
                if len(gct) != true_gct_size:
                    raise RuntimeError('The Global Color Table is shorter than specified')
                out_f.write(gct)

            # Loop over the rest of the blocks in the image
            while True:
                # Read a byte to determine the block type
                field = in_f.read(1)
                if len(field) != 1:
                    raise RuntimeError('Expected more data when there was none')
                byte = field[0]

                if byte == 0x2C:
                    # Image Descriptor
                    descriptor = in_f.read(9)
                    if len(descriptor) != 9:
                        raise RuntimeError('The Image Descriptor is too short to be valid')
                    left_pos, top_pos, width, height, packed = struct.unpack('<4HB', descriptor)
                    has_lct   = (packed & 0b10000000) >> 7
                    interlace = (packed & 0b01000000) >> 6
                    sort_flag = (packed & 0b00100000) >> 5
                    reserved  = (packed & 0b00011000) >> 4
                    lct_size  = (packed & 0b00000111) >> 0
                    out_f.write(bytes([byte]))
                    out_f.write(descriptor)

                    # Then the Local Color Table (if present)
                    if has_lct:
                        true_lct_size = 3 * (2 ** (lct_size + 1))
                        lct = in_f.read(true_lct_size)
                        if len(lct) != true_lct_size:
                            raise RuntimeError('The Local Color Table is shorter than specified')
                        out_f.write(lct)

                    # Then the Table Based Image Data
                    lzw_min_size = in_f.read(1)
                    if len(lzw_min_size) != 1:
                        raise RuntimeError('No LZW Minimum Code Size value')
                    lzw_min_size, = struct.unpack('<B', lzw_min_size)
                    out_f.write(bytes([lzw_min_size]))
                    copy_blocks(in_f, out_f)
                elif byte == 0x21:
                    # Extension Block
                    block_label = in_f.read(1)
                    if len(block_label) != 1:
                        raise RuntimeError('No Extension Block label')
                    out_f.write(bytes([byte]))
                    out_f.write(block_label)

                    # Just as a reference (for our purposes, we can pass these through all the same)
                    #   F9 = Graphic Control
                    #   FE = Comment
                    #   01 = Plain Text
                    #   FF = Application
                    #   99 = Our Custom Extension Block Type

                    # Copy the blocks
                    copy_blocks(in_f, out_f)
                elif byte == 0x3B:
                    # Trailer
                    out_f.write(bytes([byte]))
                    break
                else:
                    raise RuntimeError('Unexpected byte found while decoding')

            if data is not None:
                # Write our payload data, dropping any old appeneded data on the floor
                out_f.write(data)
            else:
                # Read and return the appended data
                return in_f.read()
