#!/usr/bin/env python
import yaml
import sys
import os
import getopt
import datetime
import collections

# Print usage message
def usage(name):
    print "Usage: python %s [-h|--help] -M|--module module_name -t|--title module_title  [-D|--dir yaml_dir] [-D|--description module_description]" % name
    print "    -h|--help                           : show this message"
    print "    -D|--dir yaml_dir                   : Yaml file directory"
    print "    -M|--module module_name             : module name"
    print "    -t|--title module_title             : module title to write on the file header"
    print "    -d|--description module_description : module description to write on the file header."
    print "                                          If empty, the title will be used as description."
    print ""

# Add File header
def printHeader(title, module, date, description):
    print "#!/usr/bin/env python"
    print "#-----------------------------------------------------------------------------"
    print "# Title      : %s" % title
    print "#-----------------------------------------------------------------------------"
    print "# File       : %s.py" % module
    print "# Created    : %s" % date
    print "#-----------------------------------------------------------------------------"
    print "# Description:"
    print "# %s" % description
    print "#-----------------------------------------------------------------------------"
    print "# This file is part of the rogue software platform. It is subject to "
    print "# the license terms in the LICENSE.txt file found in the top-level directory "
    print "# of this distribution and at: "
    print "#    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html. "
    print "# No part of the rogue software platform, including this file, may be "
    print "# copied, modified, propagated, or distributed except according to the terms "
    print "# contained in the LICENSE.txt file."
    print "#-----------------------------------------------------------------------------"
    print ""
    print "import pyrogue as pr"
    print ""

# Class to process a YAML file
class YamlDoc:
    def __init__(self, fileName):
        
        # Open YAML file
        file = open(fileName, "r")

        # Read the YAML definitions
        doc = yaml.load(file)
    
        # Get all the modules defined on the file
        # Usually there will be just one. 
        k = doc.keys()
        self.yM = []
        for module in k:
            self.yM.append(YamlModule(doc, module))

        # Close the file
        file.close()

    # Method to get the equivalent python class
    def getPyClass(self):
        # For every module, call its getPyClass method
        for ym in self.yM:
            ym.getPyClass()

# Class to process a module on the YAML file
class YamlModule:
    def __init__(self, doc, module):
        # Indentation levels
        #
        #--------->|<- L2
        #----->|<- L1 |
        #class |      |    module.py(pr.Device):
        #      |def   |    __init__(...):
        #             |super(...)
        #             |
        #             |##############################
        #             |# Variables
        #             |##############################
        #
        self.identL1 = 4
        self.identL2 = 8

        # Assume this module doesn't have children
        self.hasChildren = False

        # Variable and Command children counter
        self.variableCount = 0
        self.commandCount  = 0

        # This is the module name
        self.name = module

        # Process the module's nodes
        if (doc[module]):

            # These are the nodes we are looking for
            self.template = collections.OrderedDict([("description",""),("size","")])

            # Look for the nodes on the module and put them on the template
            for f in self.template:
                if (f in doc[module]):
                    if (f in doc[module]):
                        self.template[f] = doc[module][f]

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
    def getPyClass(self):
        # Get the class only if this method has children 
        if self.hasChildren:
            print "class %s.py(pr.Device):" % self.name
            print "%sdef __init__(self, name=\"%s.py\", memBase=None, offset=0x0, hidden=False):" % (' '.ljust(self.identL1), self.name)
            print "%ssuper(self.__class__, self).__init__(name, \"%s\", memBase, offset, hidden)" % (' '.ljust(self.identL2), self.template["description"])
            print ""
            
            # If there were variables on this modules, print them
            if self.variableCount:
                print "%s##############################" % ' '.ljust(self.identL2)
                print "%s# Variables" % ' '.ljust(self.identL2)
                print "%s##############################" % ' '.ljust(self.identL2)
                print ""

                # For every variable child, call its getPyClass method
                for yc in self.yCV:
                    yc.getPyClass()

            # If there were commands on this modules, print them
            if self.commandCount:
                print "%s##############################" % ' '.ljust(self.identL2)
                print "%s# Commands" % ' '.ljust(self.identL2)
                print "%s##############################" % ' '.ljust(self.identL2)
                print ""

                # For every command child, call its getPyClass method
                for yc in self.yCC:
                    yc.getPyClass()                

# Method to process one child of the module on the YAML file
class YamlChild:
    def __init__(self, doc, module, var):
        # Indentation levels
        #--------------------------------------------------->|<- L5
        #-------------------------------------------->|<-L4  |
        #------------------------------->|<-L3        |      |
        #----------------------->|<-L2   |            |      |
        #-->|<-L1                |       |            |      |
        #   |self.add(pr.Command |(      |name        |=     |'name',
        #   |                    |       |function    |=     |"""\
        #   |                    |       |            |      | entry(value)
        #   |                    |       |            |      | """
        #   |                    |))     |            |      |
        #   |                    |       |            |      |
        #   |self.add(pr.Variable|(      |name        |=     |'name',
        #   |                    |       |description |=     |'description',
        #   |                    |))
        #
        self.identL1 = 8
        self.identL2 = 28
        self.identL3 = 32
        self.identL4 = 45
        self.identL5 = 47

        # Type of child (Only Variable and Command are supported)
        self.isVariable = False
        self.isCommand  = False

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
            self.formats = {"description":'s', "offset":'h', "bitSize":'d', "bitOffset":'h', "base":'s', "mode":'s', "nelms":'d', "stride":'d'}

            # These are the nodes we are looking for in the child
            var_fields = ["description", "sizeBits", "base", "mode"]
            # These are the map between this YAML nodes name to Python node name
            cpsw_rogue_var_field_name_dict = {"description":"description", "sizeBits":"bitSize", "base":"base", "mode":"mode"}

            # These are the nodes we are looking for under the "at" container
            var_at_fields = ["offset", "bitOffset", "nelms", "stride"]
            # These are the map between this YAML nodes name to Python node name
            cpsw_rogue_var_at_field_name_dict = {"offset":"offset", "bitOffset":"bitOffset", "nelms":"nelms", "stride":"stride"}

            # Look for the node under "at" and put then on the template
            for vaf in var_at_fields:
                if (vaf in doc[module]["children"][var]["at"]):
                    self.template[cpsw_rogue_var_at_field_name_dict[vaf]] = doc[module]["children"][var]["at"][vaf]
                
            # Look for the child's node and put them on the template
            for vf in var_fields:
                if (vf in doc[module]["children"][var]):
                    self.template[cpsw_rogue_var_field_name_dict[vf]] = doc[module]["children"][var][vf]

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
    def getPyClass (self):
        if self.isVariable:
            self.getPyVariablesClass()

        if self.isCommand:
            self.getPyCommandsClass()

    # Method to get the equivalent python class for Variables (IntFields)
    def getPyVariablesClass(self):
        # Print the variable definition line
        print "%s%s%s%s= '%s'," % (
            ' '.ljust(self.identL1), 
            'self.add(pr.Variable'.ljust(self.identL2 - self.identL1), 
            '('.ljust(self.identL3 - self.identL2),
            'name'.ljust(self.identL4 - self.identL3), 
            self.name)

        # Print the variable properties
        for node in self.template:
            if self.formats[node] is 's':
                print "%s%s= '%s'," % (
                    ' '.ljust(self.identL3), 
                    node.ljust(self.identL4 - self.identL3), 
                    self.template[node])
            elif self.formats[node] is 'h':
                print "%s%s=  0x%02X," % (
                    ' '.ljust(self.identL3), 
                    node.ljust(self.identL4 - self.identL3), 
                    self.template[node])
            else:
                print "%s%s=  %d," % (
                    ' '.ljust(self.identL3),
                    node.ljust(self.identL4 - self.identL3), 
                    self.template[node])
        
        # Print the end of variable elements
        print "%s))" % ' '.ljust(self.identL2)
        print ""

    # Method to get the equivalent python class for Commands (SequenceCommand)
    def getPyCommandsClass(self):
        # Printf the comamnd definition line
        print "%s%s%s%s= '%s'," % (
            ' '.ljust(self.identL1), 
            'self.add(pr.Command'.ljust(self.identL2 - self.identL1), 
            '('.ljust(self.identL3 - self.identL2),
            'name'.ljust(self.identL4 - self.identL3), 
            self.name)

        # Print the command properties
        for node in self.template:
            print "%s%s= '%s'," % (
                ' '.ljust(self.identL3), 
                node.ljust(self.identL4 - self.identL3), 
                self.template[node])

        # Print the command sequence
        print "%s%s= \"\"\"\\" % (
            ' '.ljust(self.identL3), 
            'function'.ljust(self.identL4 - self.identL3))
        
        for i in range(len(self.seq)):
            print "%sself.%s.set(%d)" % (' '.ljust(self.identL5), self.seq[i][0], self.seq[i][1])

        print "%s\"\"\"" % (' '.ljust(self.identL5))

        # Print the end of commands elements
        print "%s))" % ' '.ljust(self.identL2)
        print ""

    # Method to get if this child is a variable
    def isVariable(self):
        return self.isVariable

    # Method to get if this child is a command
    def isCommand(self):
        return self.isCommand

# Main
def main(argv):
    # Process input arguments
    fileDir     = "."
    moduleName  = ""
    title       = ""
    description = ""

    try:
        opts, args = getopt.getopt(argv, "hM:D:p:t:",["module=", "path=", "description=", "title="])
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
        elif opt in ("-p", "--path"):
            fileDir = arg
        elif opt in ("-d", "--description"):
            description = arg
        elif opt in ("-t", "--title"):
            title = arg

    # The module name is mandatory
    if not moduleName:
        print "Must especify a module name!"
        usage(sys.argv[0])
        sys.exit(2)

    # The module title is mandatory
    if not title:
        print "Must especify a module title!"
        usage(sys.argv[0])
        sys.exit(2)

    # Verify if the directory exist
    if not os.path.exists(fileDir):
        print "Directory \"%s\" doesn't exist!" % fileDir
        print ""
        sys.exit(2)     

    # The YAML file full path
    yamlFile = fileDir + '/' + moduleName + ".yaml"

    # Verify is YAML file exist
    if not os.path.isfile(yamlFile):
        print "Yaml file \"%s\" doesn't exist!" % yamlFile
        print ""
        sys.exit(2)
    
    # If no description was specify, use title as description
    if not description:
        description = title

    # Get today's date
    date = "%d-%02d-%02d" % (datetime.date.today().year, datetime.date.today().month, datetime.date.today().day)

    # Print the file header
    printHeader(title=title, module=moduleName, date=date, description=description)

    # Process the YAML file
    yD = YamlDoc(yamlFile)

    # print the equivalent Python class
    yD.getPyClass()

# Call main 
if __name__ == "__main__":
        main(sys.argv[1:])
