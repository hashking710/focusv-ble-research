# Ghidra headless post-script: dump functions, full disassembly, and strings to text files.
# Jython-compatible (avoid Python-3-only syntax) since Ghidra's default script engine is Jython.
import os

program = currentProgram
listing = program.getListing()
funcMgr = program.getFunctionManager()

args = getScriptArgs()
outDir = args[0] if len(args) > 0 else "."

func_path = os.path.join(outDir, "functions.txt")
f = open(func_path, "w")
count = 0
for func in funcMgr.getFunctions(True):
    f.write("%s\t%s\t%d\n" % (func.getEntryPoint(), func.getName(), func.getBody().getNumAddresses()))
    count += 1
f.close()
print("Wrote %d functions to %s" % (count, func_path))

disasm_path = os.path.join(outDir, "disasm.txt")
f = open(disasm_path, "w")
icount = 0
for ins in listing.getInstructions(True):
    f.write("%s\t%s\n" % (ins.getAddress(), ins.toString()))
    icount += 1
f.close()
print("Wrote %d instructions to %s" % (icount, disasm_path))

strings_path = os.path.join(outDir, "strings.txt")
f = open(strings_path, "w")
scount = 0
for d in listing.getDefinedData(True):
    if d.hasStringValue():
        f.write("%s\t%s\n" % (d.getAddress(), repr(d.getValue())))
        scount += 1
f.close()
print("Wrote %d strings to %s" % (scount, strings_path))
