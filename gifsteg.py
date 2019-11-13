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

    # Set up the argument parser
    parser = argparse.ArgumentParser(description='Hide data in/extract data from a GIF.')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-a', '--append', action='store_true',
                       help='Data goes after the GIF trailer')
    group.add_argument('-e', '--extension', action='store_true',
                       help='Data goes in a custom Extension Block')
    group.add_argument('-l', '--lsb', action='store_true',
                       help='Data goes in the Least Significant Bits of the Color Table entries')
    group.add_argument('-s', '--shuffle', action='store_true',
                       help='Data goes into a permutation of the Color Table entries')
    subparsers = parser.add_subparsers(help='Whether to hide or extract data', dest='action')

    # Subparser for hiding data
    subparser = subparsers.add_parser('hide')
    subparser.add_argument('payload',
                           help='The data to hide')
    subparser.add_argument('in_file', help='The input file')
    subparser.add_argument('out_file', help='The output file')

    # Subparser for extracting data
    subparser = subparsers.add_parser('extract')
    subparser.add_argument('in_file', help='The input file')

    # Actually parse the arguments
    args = parser.parse_args()
    if args.action is None:
        parser.print_help()
        return 2

    # Determine the module to use
    if args.append:
        import append
        module = append
    elif args.extension:
        import extension
        module = extension
    elif args.lsb:
        import lsb
        module = lsb
    elif args.shuffle:
        raise NotImplementedError('Shuffle steganography not yet implemented')
    else:
        raise RuntimeError('No steganography method selected')
   
    # Invoke the relevant algorithm
    if args.action == 'hide':
        # Make sure the output directory exists
        out_dir = os.path.dirname(args.out_file)
        if out_dir and not os.path.exists(out_dir):
            os.makedirs(out_dir)
        # Call the chosen steg function, passing input, output, and payload to cause hiding
        module.steg(args.in_file, args.out_file, args.payload.encode('utf-8'))
    elif args.action == 'extract':
        # Call the chosen steg function, passing only input to cause extraction
        data = module.steg(args.in_file)
        print(data.decode('utf-8'))

    return 0


# Run the main function if loaded directly
if __name__ == '__main__':
    exit(main())
