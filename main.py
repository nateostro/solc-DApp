#!/usr/bin/python
# -*- coding: UTF-8 -*-

import sys
sys.path.append("./utils")
try:
    from utils import parseDependency, compileDapp, parseArg
except ImportError:
    print("Error: Could not import parseDependency, compileContract, or parseArg from utils")


if __name__ == "__main__":
    inputDir, outputDir, contractName, graph, debug = parseArg(sys.argv[1:])

    ## print uml graph in outputDir
    if graph:
        parseDependency(inputDir, outputDir, graph, debug)
        # sys.exit(0)

    ## complie ${contractName}
    compileDapp(inputDir, outputDir, debug)
