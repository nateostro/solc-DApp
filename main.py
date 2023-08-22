#!/usr/bin/python
# -*- coding: UTF-8 -*-

import sys
try:
    from soltool.utils.utils import parseDependency, compileDapp, parseArg
except:
    from utils.utils import parseDependency, compileDapp, parseArg

    
def compartmentalize_and_compile_contracts(inputDir, outputDir, contractName, graph, debug):
    ## print uml graph in outputDir
    if graph:
        parseDependency(inputDir, outputDir, graph, debug)
        # sys.exit(0)

    ## complie ${contractName}
    return compileDapp(inputDir, outputDir, debug)


if __name__ == "__main__":
    inputDir, outputDir, contractName, graph, debug = parseArg(sys.argv[1:])
    compartmentalize_and_compile_contracts(inputDir, outputDir, contractName, graph, debug)