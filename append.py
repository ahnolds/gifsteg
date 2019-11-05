"""
The append implementation of the GIF steganography suite
"""

import shutil

def steg(in_path, out_path, data):
    """
    The steg function (append data)
    """
    shutil.copyfile(in_path, out_path)
    with open(out_path, 'ab') as f:
        f.write(data)
