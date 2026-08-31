import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.*;
import ghidra.program.model.address.Address;
import ghidra.program.model.symbol.Reference;
import java.io.*;

public class FindXrefs extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        String outDir = args.length > 0 ? args[0] : ".";
        Listing listing = currentProgram.getListing();
        FunctionManager funcMgr = currentProgram.getFunctionManager();

        PrintWriter out = new PrintWriter(new FileWriter(new File(outDir, "xrefs.txt")));
        DataIterator di = listing.getDefinedData(true);
        while (di.hasNext()) {
            Data d = di.next();
            if (!d.hasStringValue()) continue;
            Address addr = d.getAddress();
            out.println("=== string @ " + addr + ": " + d.getValue() + " ===");
            Reference[] refs = getReferencesTo(addr);
            for (Reference r : refs) {
                Address from = r.getFromAddress();
                Function f = funcMgr.getFunctionContaining(from);
                String fname = f != null ? f.getName() + "@" + f.getEntryPoint() : "(no function)";
                out.println("  ref from " + from + " in " + fname);
                // dump a small window of disassembly around the reference
                Instruction ins = listing.getInstructionAt(from);
                for (int i = 0; i < 12 && ins != null; i++) {
                    out.println("      " + ins.getAddress() + "\t" + ins.toString());
                    ins = ins.getNext();
                }
            }
            out.println();
        }
        out.close();
        println("Wrote xrefs.txt");
    }
}
