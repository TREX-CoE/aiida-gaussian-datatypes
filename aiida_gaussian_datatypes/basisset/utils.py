# -*- coding: utf-8 -*-
"""
Gaussian Basis Set helper functions

Copyright (c), 2018 Tiziano Müller

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import re


EMPTY_LINE_MATCH = re.compile(r'^(\s*|\s*#.*)$')
BLOCK_MATCH = re.compile(r'^\s*(?P<element>[a-zA-Z]{1,3})\s+(?P<family>\S+).*\n')


def write_cp2k_basisset(fhandle, element, name, blocks, fmts=("{:>#18.12f}", "{:> #14.12f}")):
    """
    Write the Basis Set to the passed file handle in the format expected by CP2K.

    :param fhandle: A valid output file handle
    """

    fhandle.write("{} {}\n".format(element, name))
    fhandle.write("{}\n".format(len(blocks)))  # the number of sets this basis set contains

    e_fmt, c_fmt = fmts

    for block in blocks:
        fhandle.write("{n} {lmin} {lmax} {nexp} ".format(
            n=block['n'], lmin=block['l'][0][0], lmax=block['l'][-1][0], nexp=len(block['coefficients'])
            ))
        fhandle.write(" ".join(str(l[1]) for l in block['l']))
        fhandle.write("\n")

        for row in block['coefficients']:
            fhandle.write(e_fmt.format(row[0]))
            fhandle.write(" ")
            fhandle.write(" ".join(c_fmt.format(f) for f in row[1:]))
            fhandle.write("\n")


def cp2k_basisset_file_iter(fhandle):
    """
    Generates a sequence of dicts, one dict for each basis set found in the given file

    :param fhandle: Open file handle (in text mode) to a basis set file
    """

    # find the beginning of a new basis set entry, then
    # continue until the next one or the EOF

    current_basis = []

    for line in fhandle:
        if EMPTY_LINE_MATCH.match(line):
            # ignore empty and comment lines
            continue

        match = BLOCK_MATCH.match(line)

        if match and current_basis:
            yield parse_single_cp2k_basisset(current_basis)
            current_basis = []

        current_basis.append(line.strip())

    # EOF and we still have lines belonging to a basis set
    if current_basis:
        yield parse_single_cp2k_basisset(current_basis)


def parse_single_cp2k_basisset(basis):
    """
    :param basis: A list of strings, where each string contains a line read from the basis set file.
                  The list must one single basis set.
    :return:      A dictionary containing the element, tags, aliases, orbital_quantum_numbers, coefficients
    """

    # the first line contains the element and one or more idientifiers/names
    identifiers = basis[0].split()
    element = identifiers.pop(0)

    # put the longest identifier first: some basis sets specify the number of
    # valence electrons using <IDENTIFIER>-qN
    identifiers.sort(key=lambda i: -len(i))

    name = identifiers.pop(0)
    tags = name.split('-')
    aliases = [name] + identifiers  # use the remaining identifiers as aliases

    # The second line contains the number of sets, conversion to int ignores any whitespace
    n_blocks = int(basis[1])

    nline = 2

    blocks = []

    # go through all blocks containing different sets of orbitals
    for _ in range(n_blocks):
        # get the quantum numbers for this set, formatted as follows:
        # n lmin lmax nexp nshell(lmin) nshell(lmin+1) ... nshell(lmax-1) nshell(lmax)
        qn_n, qn_lmin, qn_lmax, nexp, *ncoeffs = [int(qn) for qn in basis[nline].split()]

        nline += 1

        blocks.append({
            "n": qn_n,
            "l": [(l, nl) for l, nl in zip(range(qn_lmin, qn_lmax+1), ncoeffs)],
            "coefficients": [[float(c) for c in basis[nline+n].split()] for n in range(nexp)]
            })

        # advance by the number of exponents
        nline += nexp

    return {
        'element': element,
        'name': name,
        'tags': tags,
        'aliases': aliases,
        'blocks': blocks,
        }
