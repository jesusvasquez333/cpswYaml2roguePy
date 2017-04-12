#!/usr/bin/env python
import yaml
import sys
import os
import getopt
import datetime
import collections

# Print usage message
def usage(name):
    print "Usage: python %s [-h|--help] -M|--module module_name [-T|--title module_title]  [-Y|--yamlDir yaml_dir] [P|--pythonDir python_dir] [-D|--description module_description]" % name
    print "    -h|--help                           : show this message"
    print "    -M|--module module_name             : module name"
    print "    -Y|--yamlDir yaml_dir               : Yaml input file directory"
    print "    -P|--pythonDir python_dir           : Python output file directory"
    print "    -T|--title module_title             : module title to write on the file header."
    print "                                          If empty, \"PyRogue \" + the description found on YAML will be used as description."
    print "    -D|--description module_description : module description to write on the file header."
    print "                                          If empty, \"PyRogue \" + the description found on YAML will be used as description."
    print ""

# Add File header
def printHeader(file, title, module, date, description):
    file.write("#!/usr/bin/env python\n")
    file.write("#-----------------------------------------------------------------------------\n")
    file.write("# Title      : %s\n" % title)
    file.write("#-----------------------------------------------------------------------------\n")
    file.write("# File       : %s.py\n" % module)
    file.write("# Created    : %s\n" % date)
    file.write("#-----------------------------------------------------------------------------\n")
    file.write("# Description:\n")
    file.write("# %s\n" % description)
    file.write("#-----------------------------------------------------------------------------\n")
    file.write("# This file is part of the rogue software platform. It is subject to\n")
    file.write("# the license terms in the LICENSE.txt file found in the top-level directory\n")
    file.write("# of this distribution and at:\n")
    file.write("#    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.\n")
    file.write("# No part of the rogue software platform, including this file, may be\n")
    file.write("# copied, modified, propagated, or distributed except according to the terms\n")
    file.write("# contained in the LICENSE.txt file.\n")
    file.write("#-----------------------------------------------------------------------------\n")
    file.write("\n")
    file.write("import pyrogue as pr\n")
    file.write("\n")


# Setup support for ordered dicts so we do not lose ordering
# when importing from YAML
def dict_representer(dumper, data):
    return dumper.represent_mapping(_mapping_tag, data.iteritems())

def dict_constructor(loader, node):
    return collections.OrderedDict(loader.construct_pairs(node))

# Class to process a YAML file
class YamlDoc:
    def __init__(self, yamlFile, title, description, date):
        
        # Open YAML file
        yFile = open(yamlFile, "r")

        # Setup support for ordered dicts so we do not lose ordering
        # when importing from YAML
        _mapping_tag = yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG
        yaml.add_representer(collections.OrderedDict, dict_representer)
        yaml.add_constructor(_mapping_tag, dict_constructor)

        # Read the YAML definitions
        doc = yaml.load(yFile)
    
        # Get all the modules defined on the file
        # Usually there will be just one. 
        k = doc.keys()
        self.yM = []
        for module in k:
            self.yM.append(YamlModule(doc, module, title, description, date))

        # Close the file
        yFile.close()

    # Method to get the equivalent python class
    def getPyClass(self, file):
        # For every module, call its getPyClass method
        for ym in self.yM:
            ym.getPyClass(file)

# Class to process a module on the YAML file
class YamlModule:
    def __init__(self, doc, module, title, description, date):
        # Indentation levels
        #
        #----------------------------------------------------------------->|<-L6
        #---------------------------------------------------------->|<-L5  |
        #------------------------------------------------>|<-L4     |      |
        #----------------------------------------->|<-L3  |         |      |
        #------------------------------->|<- L2    |      |         |      |
        #------------------------>|<- L1 |         |      |         |      |
        #class module(pr.Device): |      |         |      |         |      |
        #                         |def   |__init__ |(     |self     |      |
        #                         |                |      |name     |=     |"name"
        #                         |                |      |...
        #                         |                |):
        #                         |super(...)
        #                         |
        #                         |##############################
        #                         |# Variables
        #                         |##############################
        #
        self.identL1 = 4
        self.identL2 = 8
        self.identL3 = 16
        self.identL4 = 20
        self.identL5 = 32
        self.identL6 = 34

        # Assume this module it's not defined
        self.isDefined = False

        # Assume this module doesn't have children
        self.hasChildren = False

        # Variable and Command children counter
        self.variableCount = 0
        self.commandCount  = 0

        # Module details
        self.name        = module
        self.title       = title
        self.description = description
        self.date        = date

        # Process the module's nodes
        if (doc[module]):

            # The module is defined
            self.isDefined = True

            # These are the node we want to have on the python class
            self.template = collections.OrderedDict([("name",self.name), ("description",""), ("memBase","None"), ("offset",0), ("hidden","False"), ])
            # And these are the formats we will use to print each node
            # s: string, us: unquoted string, d: decimal, h: hex
            self.formats = {"name":'s', "description":'s', "memBase":'us', "offset":'h', "hidden":'us'}

            # These are the nodes we are looking for
            fields = ["name", "description", "offset"]

            # Look for the nodes on the module and put them on the template
            for f in fields:
                if (f in doc[module]):
                    if (f in doc[module]):
                        self.template[f] = doc[module][f]

            # If not title was specify, use "PyRogue " + the description found on YAML
            if not self.title:
                self.title = "PyRogue %s" % self.template["description"]

            # If not description was specify, use "PyRogue " + the description found on YAML
            if not self.description:
                self.description = "PyRogue %s" % self.template["description"]

            # Now look for children on the module
            if "children" in doc[module]:
                children = doc[module]["children"]
                if children:

                    # The module has children
                    self.hasChildren = True

                    # Get all the children on the mdules
                    self.yCV = []   # These are Variable children
                    self.yCC = []   # These are Command children
                    
                    for var in children:
                        yc = YamlChild(doc, module, var)

                        # Check if this child is a variable
                        if yc.isVariable:
                            self.yCV.append(yc)
                            self.variableCount += 1

                        # Check if this child is a command
                        if yc.isCommand:
                            self.yCC.append(yc)
                            self.commandCount += 1

    # Method to get the equivalent python class
    def getPyClass(self, file):

        # Get the class only if the module is defined
        if self.isDefined:

            # Print the file header
            printHeader(file=file, title=self.title, module=self.name, date=self.date, description=self.description)

            file.write("class %s(pr.Device):\n" % self.name)
            file.write("%s%s%s%s%s\n" % (
                ' '.ljust(self.identL1),
                'def'.ljust(self.identL2 - self.identL1),
                '__init__'.ljust(self.identL3 - self.identL2),
                '('.ljust(self.identL4 - self.identL3),
                'self,'.ljust(self.identL5 - self.identL4)))

            for node in self.template:
                if self.formats[node] is 's':
                    file.write("%s%s%s%s,\n" % (
                        ' '.ljust(self.identL4),
                        node.ljust(self.identL5 - self.identL4),
                        '='.ljust(self.identL6 - self.identL5),
                        ('\"' + self.template[node] + '\"')))
                if self.formats[node] is 'us':
                    file.write("%s%s%s %s,\n" % (
                        ' '.ljust(self.identL4),
                        node.ljust(self.identL5 - self.identL4),
                        '='.ljust(self.identL6 - self.identL5),
                        self.template[node]))
                elif self.formats[node] is 'h':
                    file.write("%s%s%s 0x%02X,\n" % (
                        ' '.ljust(self.identL4),
                        node.ljust(self.identL5 - self.identL4),
                        '='.ljust(self.identL6 - self.identL5),
                        self.template[node]))
                elif self.formats[node] is 'd':
                    file.write("%s%s%s %d,\n" % (
                        ' '.ljust(self.identL4),
                        node.ljust(self.identL5 - self.identL4),
                        '='.ljust(self.identL6 - self.identL5),
                        self.template[node]))

            file.write("%s):\n" % ' '.ljust(self.identL3))

            file.write("%ssuper(self.__class__, self).__init__(" % (' '.ljust(self.identL2)))
            for node in self.template:
                file.write("%s, " % node)
            file.write(")\n")

            file.write("\n")
            
            # Get the variables and commands only if this method has children 
            if self.hasChildren:

                # If there were variables on this modules, print them
                if self.variableCount:
                    file.write("%s##############################\n" % ' '.ljust(self.identL2))
                    file.write("%s# Variables\n" % ' '.ljust(self.identL2))
                    file.write("%s##############################\n" % ' '.ljust(self.identL2))
                    file.write("\n")

                    # For every variable child, call its getPyClass method
                    for yc in self.yCV:
                        yc.getPyClass(file)

                # If there were commands on this modules, print them
                if self.commandCount:
                    file.write("%s##############################\n" % ' '.ljust(self.identL2))
                    file.write("%s# Commands\n" % ' '.ljust(self.identL2))
                    file.write("%s##############################\n" % ' '.ljust(self.identL2))
                    file.write("\n")

                    # For every command child, call its getPyClass method
                    for yc in self.yCC:
                        yc.getPyClass(file)                

# Method to process one child of the module on the YAML file
class YamlChild:
    def __init__(self, doc, module, var):
        # Indentation levels
        #----------------------------------------------->|<- L5
        #---------------------------------------->|<-L4  |
        #--------------------------->|<-L3        |      |
        #------------------->|<-L2   |            |      |
        #-->|<-L1            |       |            |      |
        #   |self.addCommand |(      |name        |=     |'name',
        #   |                |       |function    |=     |"""\
        #   |                |       |            |      | entry(value)
        #   |                |       |            |      | """
        #   |                |)      |            |      |
        #   |                |       |            |      |
        #   |self.addVariable|(      |name        |=     |'name',
        #   |                |       |description |=     |'description',
        #   |                |       |enum        |=     |{
        #   |                |       |            |      |    |0 : "Zero"
        #   |                |       |            |      |}   |
        #   |                |)                               |
        #---------------------------------------------------->|<-L6
        #
        self.identL1 = 8
        self.identL2 = 28
        self.identL3 = 32
        self.identL4 = 45
        self.identL5 = 47
        self.identL6 = 50

        # Type of child (Only Variable and Command are supported)
        self.isVariable = False
        self.isCommand  = False

        # Variable of ENUM type
        self.isEnum = False

        # Array of variables
        self.isArray = False

        # This is the child name
        self.name = var

        # Get the child class
        yClass = doc[module]["children"][var]["class"]

        # Process YAML's IntField classes which map to "Variable" in Python
        if yClass == "IntField":

            # This child is a Variable
            self.isVariable = True

            # These are the node we want to have on the python class
            self.template = collections.OrderedDict([("description",""),("offset",0),("bitSize",32),("bitOffset",0),("base","hex"),("mode","RO")])
            # And these are the formats we will use to print each node
            self.formats = {"description":'s', "offset":'h', "bitSize":'d', "bitOffset":'h', "base":'s', "mode":'s', "number":'d', "stride":'d'}

            # These are the nodes we are looking for in the child
            var_fields = ["description", "sizeBits", "base", "mode", "lsBit"]
            # These are the map between this YAML nodes name to Python node name
            cpsw_rogue_var_field_name_dict = {"description":"description", "sizeBits":"bitSize", "base":"base", "mode":"mode", "lsBit":"bitOffset"}

            # These are the nodes we are looking for under the "at" container
            var_at_fields = ["offset", "nelms", "stride"]
            # These are the map between this YAML nodes name to Python node name
            cpsw_rogue_var_at_field_name_dict = {"offset":"offset", "nelms":"number", "stride":"stride"}

            # Look for the node under "at" and put then on the template
            for vaf in var_at_fields:
                if (vaf in doc[module]["children"][var]["at"]):
                    self.template[cpsw_rogue_var_at_field_name_dict[vaf]] = doc[module]["children"][var]["at"][vaf]
                
            # Look for the child's node and put them on the template
            for vf in var_fields:
                if (vf in doc[module]["children"][var]):
                    self.template[cpsw_rogue_var_field_name_dict[vf]] = doc[module]["children"][var][vf]

            # Check if this variable is of ENUM type
            if ("enums" in doc[module]["children"][var]):
                self.isEnum = True
                self.enum = []
                self.template["base"] = "enum"
                yEnum = doc[module]["children"][var]["enums"]
                for i in range(len(yEnum)):
                    self.enum.append((yEnum[i]["value"], yEnum[i]["name"]))

            # Check if this is an array of variables
            if ("nelms" in doc[module]["children"][var]["at"]):
                self.isArray = True

                # 'stride' is optional on YAML but mandatory on PyRogue
                # So let's ckeck if it was present on YAML. If not, use 4 as default
                if ("stride" not in doc[module]["children"][var]["at"]):
                    self.template["stride"] = 4



        # Process YAML's SequenceCommand classes which map to "Command" in Python
        if yClass == "SequenceCommand":

            # This Child is a Command
            self.isCommand = True

            # These are the nodes we are looking for
            self.template = collections.OrderedDict([("description","")])

            # Look for the nodes on the module and put them on the template
            for f in self.template:
                if (f in doc[module]["children"][var]):
                    self.template[f] = doc[module]["children"][var][f]
            
            # Read the command sequence
            self.seq = []
            ySeq = doc[module]["children"][var]["sequence"]
            for i in range(len(ySeq)):
                self.seq.append((ySeq[i]["entry"], ySeq[i]["value"]))

    # Method to get the equivalent python class
    def getPyClass (self, file):
        if self.isVariable:
            self.getPyVariablesClass(file)

        if self.isCommand:
            self.getPyCommandsClass(file)

    # Method to get the equivalent python class for Variables (IntFields)
    def getPyVariablesClass(self, file):
        # Print the variable definition line
        file.write("%s%s%s%s= \"%s\",\n" % (
            ' '.ljust(self.identL1), 
            ('self.addVariable' + ('s' if self.isArray else '')).ljust(self.identL2 - self.identL1),
            '('.ljust(self.identL3 - self.identL2),
            'name'.ljust(self.identL4 - self.identL3), 
            self.name))

        # Print the variable properties
        for node in self.template:
            if self.formats[node] is 's':
                file.write("%s%s= \"%s\",\n" % (
                    ' '.ljust(self.identL3), 
                    node.ljust(self.identL4 - self.identL3), 
                    self.template[node]))
            elif self.formats[node] is 'h':
                file.write("%s%s=  0x%02X,\n" % (
                    ' '.ljust(self.identL3), 
                    node.ljust(self.identL4 - self.identL3), 
                    self.template[node]))
            else:
                file.write("%s%s=  %d,\n" % (
                    ' '.ljust(self.identL3),
                    node.ljust(self.identL4 - self.identL3), 
                    self.template[node]))
        
        # Print the ENUM dictionary for ENUM type variables
        if self.isEnum:
            file.write("%s%s= {\n" % (' '.ljust(self.identL3), "enum".ljust(self.identL4 - self.identL3)))
            for i in range(len(self.enum)):
                file.write("%s%d : \"%s\",\n" % (' '.ljust(self.identL6), self.enum[i][0], self.enum[i][1]))
            file.write("%s},\n" % ' '.ljust(self.identL5))

        # Print the end of variable elements
        file.write("%s)\n" % ' '.ljust(self.identL2))
        file.write("\n")

    # Method to get the equivalent python class for Commands (SequenceCommand)
    def getPyCommandsClass(self, file):
        # Printf the comamnd definition line
        file.write("%s%s%s%s= \"%s\",\n" % (
            ' '.ljust(self.identL1), 
            'self.addCommand'.ljust(self.identL2 - self.identL1), 
            '('.ljust(self.identL3 - self.identL2),
            'name'.ljust(self.identL4 - self.identL3), 
            self.name))

        # Print the command properties
        for node in self.template:
            file.write("%s%s= \"%s\",\n" % (
                ' '.ljust(self.identL3), 
                node.ljust(self.identL4 - self.identL3), 
                self.template[node]))

        # Print the command sequence
        file.write("%s%s= \"\"\"\\\n" % (
            ' '.ljust(self.identL3), 
            'function'.ljust(self.identL4 - self.identL3)))
        
        for i in range(len(self.seq)):
            file.write("%sself.%s.set(%d)\n" % (' '.ljust(self.identL5), self.seq[i][0], self.seq[i][1]))

        file.write("%s\"\"\"\n" % (' '.ljust(self.identL5)))

        # Print the end of commands elements
        file.write("%s)\n" % ' '.ljust(self.identL2))
        file.write("\n")

    # Method to get if this child is a variable
    def isVariable(self):
        return self.isVariable

    # Method to get if this child is a command
    def isCommand(self):
        return self.isCommand

# Main
def main(argv):
    # Process input arguments
    yamlDir     = "."
    pythonDir   = "."
    moduleName  = ""
    title       = ""
    description = ""

    try:
        opts, args = getopt.getopt(argv, "hM:Y:P:D:T:",["module=", "yamlDir=", "pythonDir=", "description=", "title="])
    except getopt.GetoptError:
        print "Invalid option!"
        usage(sys.argv[0])
        sys.exit(2)

    for opt, arg in opts:
        if opt in ("-h", "--help"):
            usage(sys.argv[0])
            sys.exit()
        elif opt in ("-M", "--module"):
            moduleName = arg
        elif opt in ("-Y", "--yamlDir"):
            yamlDir = arg
        elif opt in ("-D", "--description"):
            description = arg
        elif opt in ("-T", "--title"):
            title = arg
        elif opt in ("-P", "--pythonDir"):
            pythonDir = arg

    # The module name is mandatory
    if not moduleName:
        print "Must especify a module name!"
        usage(sys.argv[0])
        sys.exit(2)

    # Verify if the input directory exist
    if not os.path.exists(yamlDir):
        print "Directory \"%s\" doesn't exist!" % yamlDir
        print ""
        sys.exit(2)     

    # Verify if the output directory exist
    if not os.path.exists(pythonDir):
        print "Directory \"%s\" doesn't exist!" % pythonDir
        print ""
        sys.exit(2)     

    # The YAML file full path
    yamlFile = yamlDir + '/' + moduleName + ".yaml"

    # The python file full path
    pythonFile = pythonDir + '/' + moduleName + ".py"

    # Verify is YAML file exist
    if not os.path.isfile(yamlFile):
        print "Yaml file \"%s\" doesn't exist!" % yamlFile
        print ""
        sys.exit(2)

    # Get today's date
    date = "%d-%02d-%02d" % (datetime.date.today().year, datetime.date.today().month, datetime.date.today().day)

    # Process the YAML file
    yD = YamlDoc(yamlFile, title, description, date)

    # open the output python file
    pFile = open(pythonFile, "w")

    # print the equivalent Python class
    yD.getPyClass(pFile)

    # Close the output python file
    pFile.close()

    print "Module %s converted from %s to %s" % (moduleName, yamlFile, pythonFile)

# Call main 
if __name__ == "__main__":
        main(sys.argv[1:])
