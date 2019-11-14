"""
The shuffle implementation of the GIF steganography suite
"""

from math import factorial
from maybe_open import maybe_open
import struct

all_data = bytearray()

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

def extract_data(in_f, has_ct, ct_size):
    """
    Extract the data from the color table and add it to all_data
    """
    global all_data
    if has_ct:
        true_ct_size = 3 * (2 ** (ct_size + 1))
        ct = bytearray(in_f.read(true_ct_size))
        if len(ct) != true_ct_size:
            raise RuntimeError('The Color Table is shorter than specified')

        # TODO

        # Add the extracted data to all_data
        all_data.extend(block_data)

def hide_data(in_f, out_f, has_ct, ct_size, data):
    """
    Insert the data into the color table and write to the output file
    """
    if has_ct:
        true_ct_size = 3 * (2 ** (ct_size + 1))
        ct = bytearray(in_f.read(true_ct_size))
        if len(ct) != true_ct_size:
            raise RuntimeError('The Color Table is shorter than specified')

        # Validate the data will fit
        if data > factorial(true_ct_size // 3) - 1:
            raise RuntimeError(f'Cannot hide all the data')

        # Get the unique colors (RGB triples) and sort them with the natural ordering
        colors = sorted(set(int(ct[i:i + 3].hex(), 16) for i in range(0, len(ct), 3)))

        # Allocate the color's positions based on remainders mod (data)
        positions = [0 for _ in range(len(colors))]
        for i in range(len(colors)):
            positions[len(colors) - i - 1] = data % (i + 1)
            data //= (i + 1)

        # Re-order the colors based on these positions
        new_colors = [0 for _ in range(len(colors))]
        for i in range(len(colors)):
            color = colors[i]
            pos = positions[i]
            # Shift colors up as needed to make room
            new_colors[pos + 1:] = new_colors[pos:-1]
            # Actually place the color
            new_colors[pos] = color

        # Actually make the new color table
        new_ct = bytearray(len(ct))
        for pos, color in enumerate(new_colors):
            new_ct[pos * 3:pos * 3 + 3] = (((color >> 16) & 0xFF), ((color >> 8) & 0xFF), (color & 0xFF))
        
        # Pad the color table as needed with copies of the last color
        for pos in range(len(colors), len(ct) // 3):
            new_ct[pos * 3:pos * 3 + 3] = new_ct[pos * 3 - 3:pos * 3]

        # Write out the modified Color Table
        out_f.write(new_ct)

        # Return the number of bytes written into the Color Table
        return 0
    else:
        # No Color Table => No space to hide stuff
        return 0

def steg(in_path, out_path=None, data=None):
    """
    The steg function (use the ordering of the color table entries to hide the data)
    """

    if data is not None:
        data_array = bytearray(data)
        # Must start the message with a 1 to ensure the math works out nicely...
        data_array.insert(0, 1)
        # Convert the message to a (propbably very large) integer
        data = int(data_array.hex(), 16)

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
            if data is not None:
                bytes_written = hide_data(in_f, out_f, has_gct, gct_size, data)
            else:
                extract_data(in_f, has_gct, gct_size)

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
                    if data is not None:
                        bytes_written += hide_data(in_f, out_f, has_lct, lct_size, data)
                    else:
                        extract_data(in_f, has_lct, lct_size)

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
                    raise RuntimeError(f'Unexpected byte {hex(byte)} found while decoding')

            # Politely pass any extra appended data through :)
            out_f.write(in_f.read())

            if data is not None:
                # Verify that we wrote all the data
                if bytes_written != 0:
                    raise RuntimeError(f'Failed to hide all the data ({max(0, bytes_written - 1)}/{len(data) - 1})')
            else:
                # If data was None (the extracting case), return all the extracted data
                # Don't include the hidden length byte...
                return all_data[1:]
