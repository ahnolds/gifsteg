"""
The shuffle implementation of the GIF steganography suite
"""

from collections import OrderedDict
from math import factorial
from maybe_open import maybe_open
import struct

all_data = list()

def num_to_data_len(num):
    """
    Convert a permutation number to the length of data it represents
    """
    # Strip off the leading 1 that was added to make the math work
    data = int(bin(num)[3:], 2)
    # Convert from the integer form back to a string
    data = hex(data)[2:]
    # Return the length of the data
    return len(data) // 2

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

def remap_colors(in_f, out_f, lzw_min_size, image_size):
    """
    Un-compress the image data and re-map the color pointers
    """
    global translation
    image = [0] * image_size;
    pos = 0
    # TODO initiliaze lzw params as needed
    code_table = list(range((2 ** lzw_min_size) + 2))
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

        # Get the unique colors (RGB triples)
        colors = [int(ct[i:i + 3].hex(), 16) for i in range(0, len(ct), 3)]
        colors = list(OrderedDict.fromkeys(colors).keys())

        # Pair the colors with their initial positions and sort
        colors_and_positions = sorted(zip(colors, range(len(colors))))

        # Extract the positions since that's all we actually need here
        positions = [pos for color, pos in colors_and_positions]

        # Reconstruct the data from the order
        block_data = 0
        for i in range(len(colors) - 1):
            pos = positions[i]
            block_data *= (len(colors) - i)
            block_data += pos
            # Shift subsequent colors down
            for j in range(i + 1, len(colors)):
                if positions[j] > pos:
                    positions[j] -= 1

        # Add the extracted data to all_data
        all_data.append(block_data)

translation = list()

def hide_data(in_f, out_f, has_ct, ct_size, data, bg_color_index=None, aspect_ratio=None):
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
            raise RuntimeError(f'Failed to hide all the data ({num_to_data_len(factorial(true_ct_size // 3) - 1)}/{num_to_data_len(data)})')

        # Get the unique colors (RGB triples) and sort them with the natural ordering
        all_colors = [int(ct[i:i + 3].hex(), 16) for i in range(0, len(ct), 3)]
        colors = list(OrderedDict.fromkeys(all_colors).keys())
        colors.sort()

        # Allocate the colors' positions based on remainders mod (data)
        positions = [0 for _ in range(len(colors))]
        for i in range(len(colors)):
            positions[len(colors) - i - 1] = data % (i + 1)
            data //= (i + 1)

        # Re-order the colors based on these positions
        new_colors = [0 for _ in range(len(colors))]
        for i in range(len(colors)):
            color = colors[len(colors) - i - 1]
            pos = positions[len(colors) - i - 1]
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

        # Store the translation from original to modified color table so we can fix the image data later
        global translation
        translation = []
        for color in all_colors:
            for pos, new_color in enumerate(new_colors):
                if color == new_color:
                    translation.append(pos)
                    break

        # Write the modified bg_color_index and aspect ratio
        if bg_color_index is not None:
            out_f.write(bytes([translation[bg_color_index], aspect_ratio]))

        # Write out the modified Color Table
        out_f.write(new_ct)

        # Return the number of bytes written into the Color Table
        return True
    else:
        # Still have to save off the bg_colo_index and aspect_ratio
        if bg_color_index is not None:
            out_f.write(bytes([bg_color_index, aspect_ratio]))
        # No Color Table => No space to hide stuff
        return False

def steg(in_path, out_path=None, data=None):
    """
    The steg function (use the ordering of the color table entries to hide the data)
    """

    hidden = False

    if data is not None:
        data_array = bytearray(data)
        # Must start the message with a 1 to ensure the math works out nicely
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
            width, height, packed, bg_color_index, aspect_ratio = struct.unpack('<2H3B', screen_descriptor)
            has_gct   = (packed & 0b10000000) >> 7
            color_res = (packed & 0b01110000) >> 4
            sort_flag = (packed & 0b00001000) >> 3
            gct_size  = (packed & 0b00000111) >> 0

            # Then the Global Color Table (if present)
            if data is not None:
                # Annoyingly, we can't write the bg_color_index until _after_ the color map changes
                out_f.write(struct.pack('<2HB', width, height, packed))
                hidden = hide_data(in_f, out_f, has_gct, gct_size, data, bg_color_index, aspect_ratio)
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
                        # Hide a copy in each color map, this makes the re-coloring logic simpler
                        hidden |= hide_data(in_f, out_f, has_lct, lct_size, data)
                    else:
                        extract_data(in_f, has_lct, lct_size)

                    # Then the Table Based Image Data
                    lzw_min_size = in_f.read(1)
                    if len(lzw_min_size) != 1:
                        raise RuntimeError('No LZW Minimum Code Size value')
                    lzw_min_size, = struct.unpack('<B', lzw_min_size)
                    out_f.write(bytes([lzw_min_size]))
                    remap_colors(in_f, out_f, lzw_min_size, width * height)
                elif byte == 0x21:
                    # Extension Block
                    block_label = in_f.read(1)
                    if len(block_label) != 1:
                        raise RuntimeError('No Extension Block label')
                    out_f.write(bytes([byte]))
                    out_f.write(block_label)

                    # Just as a reference (for our purposes, we can pass these through all the same)
                    #   F9 = Graphic Control
                    #           TODO Should re-map the Transparent Color Index in this case
                    #   FE = Comment
                    #   01 = Plain Text
                    #           TODO Should re-map the Text Foreground and Background Color Indices in this case
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
                # If there was data to hide, make sure we hid it!
                if not hidden:
                    raise RuntimeError('Failed to hide the data')
            else:
                # If data was None (the extracting case), return all the extracted data
                # Strip off the leading 1 that was added to make the math work
                global all_data
                all_data = [int(bin(datum)[3:], 2) for datum in all_data]
                # Convert from the integer form back to a string
                all_data = [bytes.fromhex(hex(datum)[2:]) for datum in all_data]
                # Return the data
                if len(set(all_data)) != 1:
                    print('Warning: multiple different messages recovered from different color maps:')
                    print(all_data)
                return all_data[0]
