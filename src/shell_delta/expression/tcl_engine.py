import tkinter

from shell_delta.io.io_sdproj import IO_sdproj
from shell_delta import gb_var as gb_var_script

gb_var = gb_var_script.get_gbvar_ctx()
gb_var_full = gb_var_script.get_gbvar_full()

class TCLEngine:
    def __init__(self):
        self.tcl_intepreter = tkinter.Tcl()
        reading_path = gb_var.saving_path
        if reading_path is None:
            print("TCL Engine used when reading_path is None")
            return
        self.expression = IO_sdproj.read_sdproj(
            reading_path=str(reading_path),
            reading_attr="expression"
        )

    def get_procs(self) -> list[str]:
        if self.expression is None:
            return []
        self.tcl_intepreter.eval(self.expression)
        all_procs = self.tcl_intepreter.eval("info procs").split()
        system_procs = {
            'unknown', 'auto_load', 'auto_load_index', 'auto_import', 
            'auto_execok', 'auto_qualify', 'tclLog'
            }
        function_procs = [p for p in all_procs if p not in system_procs]
        return function_procs

    def run_tcl(self,
                func_name: str,
                **arguments
                ) -> str:
        self.tcl_intepreter.eval(self.expression)
        tcl_rtn = self.tcl_intepreter.call(
            func_name,
            [item for pair in arguments.items() for item in pair]
        )
        return str(tcl_rtn)

    