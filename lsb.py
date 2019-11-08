"""
The LSB implementation of the GIF steganography suite
"""

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

def hide_data(in_f, out_f, has_ct, ct_size, data):
    """
    Insert the data into the color table and write to the output file
    """
    if has_ct:
        true_ct_size = 3 * (2 ** (ct_size + 1))
        ct = bytearray(in_f.read(true_ct_size))
        if len(ct) != true_ct_size:
            raise RuntimeError('The Color Table is shorter than specified')

        # Insert as much data into the Color Table as possible
        # Use only one-byte chunks to avoid complication, so a 15 byte color table will
        # contain one byte of data across the first 8 bytes and no data in the last 7
        num_bytes = min(true_ct_size // 8, len(data))
        for index, byte in enumerate(data[:num_bytes]):
            ct[index * 8 + 0] = (ct[index * 8 + 0] & 0b11111110) | ((byte & 0b10000000) >> 7)
            ct[index * 8 + 1] = (ct[index * 8 + 1] & 0b11111110) | ((byte & 0b01000000) >> 6)
            ct[index * 8 + 2] = (ct[index * 8 + 2] & 0b11111110) | ((byte & 0b00100000) >> 5)
            ct[index * 8 + 3] = (ct[index * 8 + 3] & 0b11111110) | ((byte & 0b00010000) >> 4)
            ct[index * 8 + 4] = (ct[index * 8 + 4] & 0b11111110) | ((byte & 0b00001000) >> 3)
            ct[index * 8 + 5] = (ct[index * 8 + 5] & 0b11111110) | ((byte & 0b00000100) >> 2)
            ct[index * 8 + 6] = (ct[index * 8 + 6] & 0b11111110) | ((byte & 0b00000010) >> 1)
            ct[index * 8 + 7] = (ct[index * 8 + 7] & 0b11111110) | ((byte & 0b00000001) >> 0)

        # Write out the modified Color Table
        out_f.write(ct)

        # Return the number of bytes written into the Color Table
        return num_bytes
    else:
        # No Color Table => No space to hide stuff
        return 0

def steg(in_path, out_path, data):
    """
    The steg function (use the LSB of the color table entries to hide the data)
    """
    with open(in_path, 'rb') as in_f:
        with open(out_path, 'wb') as out_f:
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
            bytes_written = hide_data(in_f, out_f, has_gct, gct_size, data)

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
                    bytes_written += hide_data(in_f, out_f, has_lct, lct_size, data[bytes_written:])

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

            if bytes_written != len(data):
                raise RuntimeError(f'Failed to hide all the data ({bytes_written}/{len(data)})')

            # Politely pass any extra appended data through :)
            out_f.write(in_f.read())
