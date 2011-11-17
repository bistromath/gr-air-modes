#!/usr/bin/env python
import modes_print

infile = open("27augrudi3.txt")

printer = modes_print.modes_output_print([37.409348,-122.07732])
for line in infile:
    printer.parse(line)
