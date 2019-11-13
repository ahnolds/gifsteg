"""
Helper functions to support a maybe-existing file
"""

class null_open(object):
    """
    A class to support a non-existent output file

    Just black-holes all the attempts to write
    """

    def __init__(self):
        super(null_open, self).__init__()

    def __enter__(self, *args, **kwargs):
        return self

    def __exit__(self, *args, **kwargs):
        pass

    def write(self, *args, **kwargs):
        pass

def maybe_open(path, *args, **kwargs):
    """
    A function to support a maybe-existing file

    This lets us use the same code for hiding and extracting data, since we
    just use None as the output path when extracting and all the writes are
    silently dropped.
    """
    if path is not None:
        return open(path, *args, **kwargs)
    else:
        return null_open()
