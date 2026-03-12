import os
import subprocess
import tempfile
import sys
import shutil
import difflib

# Fix for Windows: prevents the plugin from popping up CMD windows or hanging
CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

class DiffEngine:
    def __init__(self, project_dir):
        self.project_dir = project_dir
        
        # Create a dedicated temp folder for this diff session
        self.tmp_dir = os.path.join(tempfile.gettempdir(), "kicad_git_diff")
        os.makedirs(self.tmp_dir, exist_ok=True)
        
        self.kicad_cli = "kicad-cli.exe" if sys.platform == "win32" else "kicad-cli"
        self.git_cmd = "git.exe" if sys.platform == "win32" else "git"

    def get_git_status(self):
        """Returns a dict of {filename: status_code} for modified files"""
        status_dict = {}
        try:
            res = subprocess.run([self.git_cmd, "-C", self.project_dir, "status", "--porcelain"], 
                                 capture_output=True, text=True, creationflags=CREATE_NO_WINDOW)
            for line in res.stdout.split('\n'):
                if len(line) > 3:
                    code = line[0:2].strip()
                    fname = line[3:].strip().strip('"')
                    status_dict[fname] = code
        except Exception:
            pass # Not a git repo or git error
        return status_dict

    def _generate_text_diff(self, old_file, new_file):
        """Helper to generate a unified diff from two text files (like Netlists or BOMs)"""
        if not old_file or not new_file or not os.path.exists(old_file) or not os.path.exists(new_file):
            return ""
        try:
            with open(old_file, 'r', encoding='utf-8', errors='ignore') as f:
                old_lines = f.readlines()
            with open(new_file, 'r', encoding='utf-8', errors='ignore') as f:
                new_lines = f.readlines()
            
            diff = difflib.unified_diff(old_lines, new_lines, fromfile='Reference', tofile='Current', n=3)
            return "".join(list(diff))
        except Exception as e:
            return f"Error generating text diff: {e}"

    def render_all_diffs(self, show_unchanged=False, compare_target="HEAD"):
        """
        Scans for .kicad_pcb and .kicad_sch. Exports visual and logical files.
        compare_target allows diffing against any git ref (HEAD, origin/main, etc.)
        Returns (list_of_diff_dicts, summary_string)
        """
        git_status = self.get_git_status()
        target_files = []
        
        # 1. Find all relevant hardware files in the project root
        for fname in os.listdir(self.project_dir):
            if fname.endswith('.kicad_pcb') or fname.endswith('.kicad_sch'):
                target_files.append(fname)
                
        diffs = []
        summary_lines = []
        
        for fname in target_files:
            file_path = os.path.join(self.project_dir, fname)
            status_code = git_status.get(fname)
            
            if status_code in ['M', 'AM']: status_text = "Modified"
            elif status_code in ['A', '??']: status_text = "New/Untracked"
            else: status_text = "Unchanged"
            
            if status_text == "Unchanged" and not show_unchanged:
                continue
                
            summary_lines.append(f"{fname}: {status_text}")
            
            safe_name = fname.replace('.', '_')
            is_pcb = fname.endswith('.kicad_pcb')
            ext = "svg" if is_pcb else "pdf"
            
            curr_out = os.path.join(self.tmp_dir, f"curr_{safe_name}.{ext}")
            old_out = os.path.join(self.tmp_dir, f"old_{safe_name}.{ext}")
            old_board_tmp = os.path.join(self.tmp_dir, f"tmp_git_{fname}")
            curr_board_tmp = os.path.join(self.tmp_dir, f"tmp_curr_{fname}")
            
            if os.path.exists(curr_out): os.remove(curr_out)
            if os.path.exists(old_out): os.remove(old_out)

            cli_args = [self.kicad_cli, "pcb" if is_pcb else "sch", "export", ext]
            if is_pcb:
                cli_args.extend(["--layers", "F.Cu,F.Silkscreen,Edge.Cuts", "--exclude-drawing-sheet"])
                
            netlist_diff = ""
            bom_diff = ""

            try:
                # --- Current Version Exports ---
                curr_target = file_path
                if not is_pcb:
                    shutil.copy2(file_path, curr_board_tmp)
                    curr_target = curr_board_tmp

                subprocess.run(cli_args + [curr_target, "--output", curr_out], 
                               check=True, capture_output=True, text=True, input="y\n",
                               creationflags=CREATE_NO_WINDOW)
                
                if not is_pcb:
                    curr_net = os.path.join(self.tmp_dir, f"curr_{safe_name}.net")
                    curr_bom = os.path.join(self.tmp_dir, f"curr_{safe_name}.csv")
                    subprocess.run([self.kicad_cli, "sch", "export", "netlist", curr_target, "--output", curr_net], capture_output=True, creationflags=CREATE_NO_WINDOW)
                    subprocess.run([self.kicad_cli, "sch", "export", "bom", curr_target, "--output", curr_bom], capture_output=True, creationflags=CREATE_NO_WINDOW)
                
                # --- Reference (HEAD or Remote) Version Exports ---
                has_old = False
                # If we are comparing against something other than HEAD, we always try to find the file
                with open(old_board_tmp, "wb") as f:
                    res = subprocess.run([self.git_cmd, "-C", self.project_dir, "show", f"{compare_target}:{fname}"],
                                         stdout=f, stderr=subprocess.PIPE, creationflags=CREATE_NO_WINDOW)
                
                if res.returncode == 0:
                    subprocess.run(cli_args + [old_board_tmp, "--output", old_out], 
                                   check=True, capture_output=True, text=True, input="y\n",
                                   creationflags=CREATE_NO_WINDOW)
                    has_old = True
                    
                    if not is_pcb:
                        old_net = os.path.join(self.tmp_dir, f"old_{safe_name}.net")
                        old_bom = os.path.join(self.tmp_dir, f"old_{safe_name}.csv")
                        subprocess.run([self.kicad_cli, "sch", "export", "netlist", old_board_tmp, "--output", old_net], capture_output=True, creationflags=CREATE_NO_WINDOW)
                        subprocess.run([self.kicad_cli, "sch", "export", "bom", old_board_tmp, "--output", old_bom], capture_output=True, creationflags=CREATE_NO_WINDOW)
                        
                        netlist_diff = self._generate_text_diff(old_net, curr_net)
                        bom_diff = self._generate_text_diff(old_bom, curr_bom)

                diffs.append({
                    "name": fname,
                    "status": status_text,
                    "curr": curr_out if os.path.exists(curr_out) else None,
                    "old": old_out if has_old and os.path.exists(old_out) else None,
                    "netlist_diff": netlist_diff,
                    "bom_diff": bom_diff
                })
                
            except Exception as e:
                print(f"Error rendering {fname}: {e}")

        summary = "\n".join(summary_lines) if summary_lines else "No files found."
        return diffs, summary