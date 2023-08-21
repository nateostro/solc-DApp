import getopt
import subprocess
import sys
import os, json, re
from solidity_parser import parser
from graphviz import Digraph
import time
import logging
from termcolor import colored

logging.basicConfig(level=logging.INFO)

'''
#  parses command line arguments.
# Why: Command line arguments are used to specify the input directory, output directory, contract name, and other options.
# Subtleties: If the arguments are not correctly formatted, an error message is logged and the program exits.
# Possible bugs: If new command line options are added, they must be included in the getopt.getopt call.
'''
def parseArg(argv):
    inputDir = ""
    outputDir = "./output"
    contractName = ""
    graph = False
    debug = False
    try:
        opts, args = getopt.getopt(argv, "hgi:o:n:", ["help", "graph", "inputDir=", "outputDir=", "contractName="])
    except getopt.GetoptError:
        logging.error('Error parsing arguments, got: ', str(argv))
        logging.error("Usage is: python3 main.py -i <inputDir> -o <outputDir> -n <contractName>, -d to enable debug mode")
        sys.exit(2)
    for opt, arg in opts:
        if opt in ("-d", "--debug"):
            debug = True
        if opt in ("-h", "--help"):
            if debug: logging.info(colored('Help:', 'green'))
            if debug: logging.info("python3 main.py -i <inputDir> -o <outputDir> -n <contractName>, -d to enable debug mode")
            sys.exit()
        elif opt in ("-g", "--graph"):
            graph = True
        elif opt in ("-i", "--inputDir"):
            inputDir = arg
        elif opt in ("-o", "--outputDir"):
            outputDir = arg
        elif opt in ("-n", "--contractName"):
            contractName = arg
    if not os.path.isdir(inputDir):
        logging.error(f"{inputDir} is not a input dir")
        sys.exit(2)
    elif not os.path.isdir(outputDir):
        logging.error(f"{outputDir} is not a output dir")
        sys.exit(2)
    elif contractName != "" and not os.path.exists(os.path.join(inputDir, contractName + ".sol")):
        logging.error(f"contract {contractName} does not exist")
        sys.exit(2)
    if debug: logging.info(colored('Arguments parsed successfully.', 'green'))
    return inputDir, outputDir, contractName, graph, debug

'''
#  parses the Solidity version from a file using readline.
# Why: The Solidity version is needed to compile the contract.
# Subtleties: If the version is not found, "unknown version" is returned.
# Possible bugs: If the version is not specified in the expected format, it may not be correctly identified.
'''
def parseVersionReadline(filePath, debug=False):
    if debug: logging.info(colored('Parsing solidity version by readline...', 'green'))
    f = open(filePath)
    line = f.readline()
    while line:
        if re.search('pragma', line) != None and re.search('0\.[0-9\.]*', line) != None:
            return re.search('0\.[0-9\.]*', line).group(0)
        line = f.readline()
    f.close()
    if debug: logging.info(colored('Solidity version parsed successfully.', 'green'))
    return "unknown version"

'''
#  parses the Solidity version from a .sol file.
# Why: The Solidity version is needed to compile the contract.
# Subtleties: If the version is not found, the function falls back to parseVersionReadline.
# Possible bugs: If the version is not specified in the expected format, it may not be correctly identified.
'''
def parseVersion(filePath, debug=False):
    if debug: logging.info(colored('Parsing solidity version from .sol file...', 'green'))
    try:
        fileUnits = parser.parse_file(filePath, loc=False)
    except Exception as e:
        logging.error('Error parsing solidity version from .sol file.')
        return parseVersionReadline(filePath)
    for item in fileUnits["children"]:
        if item["type"] == "PragmaDirective":
            if debug: logging.info(colored('Solidity version parsed successfully.', 'green'))
            return item["value"]
    if debug: logging.info(colored('Solidity version parsed successfully.', 'green'))
    return "unknown version"

'''
#  switches the solc version using solc-select.
# Why: Different contracts may require different versions of the Solidity compiler.
# Subtleties: The function sleeps for 5 seconds after switching versions to ensure the change takes effect.
# Possible bugs: If solc-select is not installed or not working correctly, this function will not work.
'''
def switchVersion(version, debug=False):
    if debug: logging.info(colored('Switching solc version...', 'green'))
    cleanVersion = re.search('0\.[0-9\.]*', version).group(0)
    check_and_install_solc_version(cleanVersion)
    os.system("solc-select use " + cleanVersion)
    time.sleep(5)
    if debug: logging.info(colored('Solc version switched successfully.', 'green'))

'''
#  parses a list of contracts with absolute paths.
# Why: The list of contracts is needed to compile the DApp.
# Subtleties: The function recursively searches directories for .sol files.
# Possible bugs: If a .sol file is not a contract, it will still be included in the list.
'''
def parseContractList(inputDir, debug=False):
    if debug: logging.info(colored('Parsing contract list with absolute path...', 'green'))
    result = dict()
    inputFiles = os.listdir(inputDir)
    for inputFile in inputFiles:
        targetPath = os.path.join(inputDir, inputFile)
        targetPath = os.path.abspath(targetPath)
        if (not os.path.isdir(targetPath)) \
                and re.match("[\S]*.sol$", inputFile) != None:
            result[targetPath] = inputFile
        elif os.path.isdir(targetPath):
            nestResult = parseContractList(targetPath)
            for key, value in nestResult.items():
                result[key] = value
    if debug: logging.info(colored('Contract list parsed successfully.', 'green'))
    return result

'''
#  parses a list of imported files in relative paths.
# Why: The list of imported files is needed to compile the DApp.
# Subtleties: If an import statement cannot be parsed, an empty list is returned.
# Possible bugs: If an import statement is not in the expected format, it may not be correctly identified.
'''
def parseImportList(filePath, debug=False):
    if debug: logging.info(colored('Parsing import file list in relative path...', 'green'))
    try:
        fileUnits = parser.parse_file(filePath, loc=False)
    except Exception as e:
        logging.error('Error parsing import file list in relative path.')
        return []
    result = []
    try:
        for item in fileUnits["children"]:
            if item["type"] == "ImportDirective":
                result.append(item["path"])
    except Exception as e:
        logging.error(filePath)
    if debug: logging.info(colored('Import file list parsed successfully.', 'green'))
    return result

'''
#  draws a dependency graph of the contracts.
# Why: The dependency graph is useful for understanding the structure of the DApp.
# Subtleties: If a contract imports a file that does not exist, a node with label "404" is added to the graph.
# Possible bugs: If a contract imports a file that is not a contract, it will still be included in the graph.
'''
def parseDependency(inputDir, outputDir, graph, debug=False):
    if debug: logging.info(colored('Drawing dependency graph...', 'green'))
    result = parseContractList(inputDir)
    dot = Digraph(comment="The Dependency Graph", node_attr={'shape': 'record'})
    ## add node from the contract list
    for path, name in result.items():
        dot.node(name = path, label = "{%s|path: %s|version: %s}"%(name, path, parseVersion(path)))
    ## add graph from the import list
    for path, name in result.items():
        importFiles = parseImportList(path)
        dirName = os.path.dirname(path)
        for importFile in importFiles:
            realPath = os.path.join(dirName, importFile)
            for key in result.keys():
                if os.path.exists(realPath) and os.path.samefile(key, realPath):
                    realPath = key
                    break
            if realPath in result:
                dot.edge(realPath, path)
            else:
                dot.node(name = realPath, label = "{404|path: %s}"%realPath)
                dot.edge(realPath, path)
    if graph:
        dot.render(os.path.join(outputDir, "DependencyGraph.gv"), format='png', view=True)
    if debug: logging.info(colored('Dependency graph drawn successfully.', 'green'))
    return dot

'''
#  gets the leaf nodes of the dependency graph.
# Why: The leaf nodes are the contracts that do not depend on any other contracts.
# Subtleties: The function counts the out degree of each node to determine if it is a leaf node.
# Possible bugs: If a contract imports a file that is not a contract, it may be incorrectly identified as a leaf node.
'''
def getLeafNode(inputDir, debug=False):
    if debug: logging.info(colored('Getting leaf node of dependency graph...', 'green'))
    result = parseContractList(inputDir)
    nodeList = dict()
    ## add node from the contract list
    for path, name in result.items():
        nodeList[path] = 0
    ## calculate out degree of each node
    for path, name in result.items():
        importFiles = parseImportList(path)
        dirName = os.path.dirname(path)
        for importFile in importFiles:
            realPath = os.path.join(dirName, importFile)
            for key in result.keys():
                if os.path.exists(realPath) and os.path.samefile(key, realPath):
                    realPath = key
                    break
            if realPath in result:
                nodeList[realPath] += 1
    if debug: logging.info(colored('Leaf node of dependency graph obtained successfully.', 'green'))
    return nodeList                

'''
compile DApp
'''
def compileLeafNodes(inputDir, outputDir, debug=False):
    if debug: logging.info(colored('Compiling DApp...', 'green'))
    ## get leaf node (contract)
    nodeList = getLeafNode(inputDir)
    leafNodes = []
    for path, outDegree in nodeList.items():
        if outDegree == 0:
            leafNodes.append(path)
    ## compile leaf node
    for leafNode in leafNodes:
        (_, contractName) = os.path.split(leafNode)
        targetPath = os.path.join(outputDir, contractName[:len(contractName) - 4] + ".json")
        if os.path.exists(targetPath) and os.path.getsize(targetPath):
            continue
        version = parseVersion(leafNode)
        if version == "unknown version":
            logging.error(f"Unable to identify solidity version of {contractName}")
            continue
        switchVersion(version)
        basePath = os.path.join(os.path.dirname(inputDir), "node_modules")
        if not os.path.exists(basePath):
            os.mkdir(basePath)
        _, _, importLibs = calculateImportLib(inputDir)
        compileCommand = "solc --combined-json abi,bin,bin-runtime,srcmap,srcmap-runtime,ast "
        for importLib in importLibs:
            libs = importLib.split("/")
            if libs[0] == ".":
                continue
            compileCommand = compileCommand + libs[0] + "=" + os.path.join(basePath, libs[0]) + " "
        compileCommand = compileCommand \
                    + leafNode + " > " \
                    + targetPath \
                    + " --allow-paths " \
                    + os.path.dirname(inputDir)
        os.system(compileCommand)
    if debug: logging.info(colored('DApp compiled successfully.', 'green'))

def compileDapp(inputDir, outputDir, debug=False):
    try:
        if debug: logging.info(colored('Compiling DApp...', 'green'))
        ## get all node (contract)
        contractList = parseContractList(inputDir)
        ## compile each contract
        for contractPath, contractName in contractList.items():
            print('hello')
            targetPath = os.path.join(outputDir, contractName[:len(contractName) - 4] + ".json")
            if os.path.exists(targetPath) and os.path.getsize(targetPath):
                continue
            version = parseVersion(contractPath)
            if version == "unknown version":
                logging.error("Unable to identify solidity version of", contractName)
                continue
            switchVersion(version)
            basePath = os.path.join(os.path.dirname(inputDir), "node_modules")
            if not os.path.exists(basePath):
                os.mkdir(basePath)
            _, _, importLibs = calculateImportLib(inputDir)
            compileCommand = "solc --combined-json abi,bin,bin-runtime,srcmap,srcmap-runtime,ast "
            for importLib in importLibs:
                libs = importLib.split("/")
                if libs[0] == ".":
                    continue
                compileCommand = compileCommand + libs[0] + "=" + os.path.join(basePath, libs[0]) + " "
            compileCommand = compileCommand \
                        + contractPath + " > " \
                        + targetPath \
                        + " --allow-paths " \
                        + os.path.dirname(inputDir)
            
            logging.info("Compiling this contract " + contractName + "... compileCommand: " + str(compileCommand))
            os.system(compileCommand)
    except Exception as e:
        logging.error('Error compiling DApp.')
        return False
    
    logging.info('DApp compiled successfully.')
    return True

import subprocess

def check_and_install_solc_version(version):
    # Get the installed solc version
    installed_version = subprocess.check_output(["solc", "--version"]).decode("utf-8")

    # Check if the required version is installed
    if version not in installed_version:
        # If not, install the required version
        logging.info(f"Version {version} not found. Installing...")
        subprocess.call(["solc-select", "install", version])
        subprocess.call(["solc-select", "use", version])
        logging.info(f"Version {version} installed successfully.")
    else:
        logging.info(f"Version {version} is already installed.")

'''
compile contract
'''
def compileContract(inputDir, outputDir, targetContract):
    logging.info('Compiling contract...')
    ## get leaf node (contract)
    nodeList = getLeafNode(inputDir)
    leafNode = ""
    for path, outDegree in nodeList.items():
        (cPath, cName) = os.path.split(path)
        cName = cName[:len(cName) - 4]
        if cName == targetContract:
            leafNode = path
    # compile leaf node
    if leafNode == "":
        return
    (_, contractName) = os.path.split(leafNode)
    targetPath = os.path.join(outputDir, contractName[:len(contractName) - 4] + ".json")
    version = parseVersion(leafNode)
    if version == "unknown version":
        logging.error("Unable to identify solidity version of %s", contractName)
        return
    switchVersion(version)
    basePath = os.path.join(os.path.dirname(inputDir), "node_modules")
    if not os.path.exists(basePath):
        os.mkdir(basePath)
    _, _, importLibs = calculateImportLib(inputDir)
    compileCommand = "solc --combined-json abi,bin,bin-runtime,srcmap,srcmap-runtime,ast "
    for importLib in importLibs:
        libs = importLib.split("/")
        if libs[0] == ".":
            continue
        compileCommand = compileCommand + libs[0] + "=" + os.path.join(basePath, libs[0]) + " "
    compileCommand = compileCommand \
                + leafNode + " > " \
                + targetPath \
                + " --allow-paths " \
                + os.path.dirname(inputDir)
    os.system(compileCommand)
    logging.info('Contract compiled successfully.')

'''
calculate how many import lib
'''
def calculateImportLib(inputDir):
    logging.info('Calculating how many import lib...')
    ## get all node (contract)
    result = parseContractList(inputDir)
    modulePath = os.path.dirname(inputDir)
    modulePath = os.path.join(modulePath, "node_modules")
    ## calculate import lib
    libNum = 0
    lib = []
    for path, name in result.items():
        importFiles = parseImportList(path)
        flag = False
        for importFile in importFiles:
            importFile = importFile.replace("'", "")
            dirName = os.path.dirname(path)
            if not os.path.exists(os.path.join(dirName, importFile)):
                    # and not os.path.exists(os.path.join(modulePath, importFile)):
                flag = True
                # print(os.path.join(modulePath, importFile))
                # print(os.path.join(dirName, importFile))
                lib.append(importFile)
        if flag:
            libNum += 1
    logging.info('Number of import lib calculated successfully.')
    return libNum, len(result.keys()), list(set(lib))

'''
get contract string without ''pragma solidity''
'''
def getPackedContract(contractPath, nodeModulePath):
    logging.info('Getting contract string without ''pragma solidity''...')
    f = open(contractPath, 'r')
    contractStringWithVersion = f.read()
    f.close()
    versionPattern = 'pragma solidity [\S]*;'
    versionString = re.search(versionPattern, contractStringWithVersion)
    if versionString == None:
        return "failed", "failed"
    versionString = versionString.group()
    contractStringWithoutVersion = re.sub(versionPattern, '', contractStringWithVersion)

    result = ""

    importPattern1 = 'import[\s]*([\S]*);'
    importItem = re.search(importPattern1, contractStringWithoutVersion)
    while importItem != None:
        contractStringWithoutVersion = re.sub(importPattern1, '', contractStringWithoutVersion)
        targetPath1 = os.path.join(contractPath, importItem.group(1))
        targetPath2 = os.path.join(nodeModulePath, importItem.group(1))
        importItem = re.search(importPattern1, contractStringWithoutVersion)
        if os.path.exists(targetPath1):
            tempVersion, tempresult =  getPackedContract(targetPath1, nodeModulePath)
            if tempVersion == "failed":
                return "failed", "failed"
            result = result + tempresult
        elif os.path.exists(targetPath2):
            tempVersion, tempresult =  getPackedContract(targetPath2, nodeModulePath)
            if tempVersion == "failed":
                return "failed", "failed"
            result = result + tempresult
        else:
            return "failed", "failed"

    importPattern2 = 'import[\s]*[\S]*[\s]*from[\s]*([\S]*);'
    importItem = re.search(importPattern2, contractStringWithoutVersion)
    result = ""
    while importItem != None:
        contractStringWithoutVersion = re.sub(importPattern2, '', contractStringWithoutVersion)
        targetPath1 = os.path.join(contractPath, importItem.group(1))
        targetPath2 = os.path.join(nodeModulePath, importItem.group(1))
        importItem = re.search(importPattern2, contractStringWithoutVersion)
        if os.path.exists(targetPath1):
            tempVersion, tempresult =  getPackedContract(targetPath1, nodeModulePath)
            if tempVersion == "failed":
                return "failed", "failed"
            result = result + tempresult
        elif os.path.exists(targetPath2):
            tempVersion, tempresult =  getPackedContract(targetPath2, nodeModulePath)
            if tempVersion == "failed":
                return "failed", "failed"
            result = result + tempresult
        else:
            return "failed", "failed"

    result = result + contractStringWithoutVersion
    return versionString, result


'''
get packed leaf contracts
'''
def getPacked(inputDir, outputDir):
    ## get node_modules path
    nodeModulePath = os.path.join(os.path.dirname(inputDir), "node_modules")
    ## get leaf node (contract)
    nodeList = getLeafNode(inputDir)
    leafNodes = []
    for path, outDegree in nodeList.items():
        # if outDegree == 0:
        leafNodes.append(path)
    ## compile leaf node
    for leafNode in leafNodes:
        (contractPath, contractName) = os.path.split(leafNode)
        contractPath = os.path.join(contractPath, contractName)
        contractName = contractName[:len(contractName) - 4]
        targetPath = os.path.join(outputDir, contractName + "_packed.sol")
        version, contract = getPackedContract(contractPath, nodeModulePath)
        if version == "failed":
            continue
        packedLeafNode = version + "\n" + contract
        with open(targetPath, 'w') as f:
            f.write(packedLeafNode)


