#!/usr/bin/env python3

"""
The main program used to hide data in a GIF
"""

import argparse
import os.path

def main():
    """
    The main function

    Parses arguments from the command line and invokes the requested
    steganography implementation.
    """

    # Constants for use in file paths
    INDIR = 'GIFs'
    DEF_OUTDIR = 'outputs'

    # Get the list of GIFs that are available
    files = sorted(os.listdir(INDIR))
    gifs = filter(lambda f: f.endswith('.gif'), files)
    gif_names = list(map(lambda g: g[:-4], gifs))

    # Set up the argument parser
    parser = argparse.ArgumentParser(description='Hide data in a GIF.')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-a', '--append',    action='store_true',
                       help='Append the data after the GIF trailer')
    group.add_argument('-e', '--extension', action='store_true',
                       help='Conceal the data in a custom Extension Block')
    group.add_argument('-l', '--lsb',       action='store_true',
                       help='Conceal the data within the Least Significant Bits of the Color Table entries')
    group.add_argument('-s', '--shuffle',   action='store_true',
                       help='Conceal the data in a permutation of the Color Table entries')
    parser.add_argument('payload',
                        help='The data to hide')
    parser.add_argument('in_name', choices=gif_names, metavar='gif_name',
                        help='The input file name (no path or exentsion)')
    parser.add_argument('out_file', nargs='?',
                        help=f'The output file name, default {DEF_OUTDIR}/<in_name>.gif')
    args = parser.parse_args()

    # Get the full input path
    in_path = os.path.join(INDIR, f'{args.in_name}.gif')

    # Make an output directory if necessary
    if args.out_file is None:
        if not os.path.exists(DEF_OUTDIR):
            os.makedirs(DEF_OUTDIR)
        out_path = os.path.join(DEF_OUTDIR, f'new_{args.in_name}.gif')
    else:
        out_path = args.out_file

    # Determine the module to use
    if args.append:
        import append
        module = append
    elif args.extension:
        import extension
        module = extension
    elif args.lsb:
        raise NotImplementedError('LSB steganography not yet implemented')
    elif args.shuffle:
        raise NotImplementedError('Shuffle steganography not yet implemented')
    else:
        raise RuntimeError('No steganography method selected')
   
    # Invoke the relevant steg algorithm
    module.steg(in_path, out_path, args.payload.encode('utf-8'))


# Run the main function if loaded directly
if __name__ == '__main__':
    main()
