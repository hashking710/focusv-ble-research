import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.*;
import java.io.*;

public class DumpTC32 extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        String outDir = args.length > 0 ? args[0] : ".";

        Listing listing = currentProgram.getListing();
        FunctionManager funcMgr = currentProgram.getFunctionManager();

        PrintWriter fw = new PrintWriter(new FileWriter(new File(outDir, "functions.txt")));
        int fcount = 0;
        FunctionIterator fi = funcMgr.getFunctions(true);
        while (fi.hasNext()) {
            Function fn = fi.next();
            fw.println(fn.getEntryPoint() + "\t" + fn.getName() + "\t" + fn.getBody().getNumAddresses());
            fcount++;
        }
        fw.close();
        println("Wrote " + fcount + " functions");

        PrintWriter dw = new PrintWriter(new FileWriter(new File(outDir, "disasm.txt")));
        int icount = 0;
        InstructionIterator ii = listing.getInstructions(true);
        while (ii.hasNext()) {
            Instruction ins = ii.next();
            dw.println(ins.getAddress() + "\t" + ins.toString());
            icount++;
        }
        dw.close();
        println("Wrote " + icount + " instructions");

        PrintWriter sw = new PrintWriter(new FileWriter(new File(outDir, "strings.txt")));
        int scount = 0;
        DataIterator di = listing.getDefinedData(true);
        while (di.hasNext()) {
            Data d = di.next();
            if (d.hasStringValue()) {
                sw.println(d.getAddress() + "\t" + d.getValue());
                scount++;
            }
        }
        sw.close();
        println("Wrote " + scount + " strings");
    }
}
