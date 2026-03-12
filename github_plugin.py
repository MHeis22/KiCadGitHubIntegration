import wx
import os
import subprocess
import pcbnew
from .diff_engine import DiffEngine
from .diff_window import DiffWindow

# Fix for Windows: prevents the plugin from popping up CMD windows or hanging
CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

class CommandCenterDialog(wx.Dialog):
    def __init__(self, parent, project_dir):
        super().__init__(parent, title="GitHub Command Center", size=(450, 480))
        self.project_dir = project_dir
        self.git_cmd = "git.exe" if os.name == "nt" else "git"
        self.gh_cmd = "gh.exe" if os.name == "nt" else "gh"
        
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)
        
        # --- Header & Status ---
        header = wx.StaticText(panel, label="Git Version Control")
        font = header.GetFont()
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        font.SetPointSize(12)
        header.SetFont(font)
        vbox.Add(header, flag=wx.ALIGN_CENTER | wx.TOP | wx.BOTTOM, border=15)

        self.status_lbl = wx.StaticText(panel, label="Checking status...")
        vbox.Add(self.status_lbl, flag=wx.LEFT | wx.RIGHT | wx.BOTTOM, border=15)
        
        # --- Action Buttons ---
        btn_diff = wx.Button(panel, label="🔍 Generate Visual Diff (Changed Only)", size=(-1, 40))
        btn_diff_all = wx.Button(panel, label="🔍 Generate Visual Diff (All Files)", size=(-1, 40))
        btn_commit = wx.Button(panel, label="💾 Quick Commit", size=(-1, 40))
        btn_push = wx.Button(panel, label="☁️ Link and Push to GitHub", size=(-1, 40))
        btn_close = wx.Button(panel, label="Close")
        
        btn_diff.Bind(wx.EVT_BUTTON, self.on_diff)
        btn_diff_all.Bind(wx.EVT_BUTTON, self.on_diff_all)
        btn_commit.Bind(wx.EVT_BUTTON, self.on_commit)
        btn_push.Bind(wx.EVT_BUTTON, self.on_push)
        btn_close.Bind(wx.EVT_BUTTON, self.on_close)
        
        vbox.Add(btn_diff, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=15)
        vbox.Add(btn_diff_all, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=15)
        vbox.Add(btn_commit, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=15)
        vbox.Add(btn_push, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=15)
        vbox.Add(btn_close, flag=wx.ALIGN_RIGHT | wx.RIGHT | wx.BOTTOM, border=15)
        
        panel.SetSizer(vbox)
        self.update_git_status()

    def update_git_status(self):
        if not os.path.isdir(os.path.join(self.project_dir, ".git")):
            self.status_lbl.SetLabel("Status: Not a Git repository. Commit to initialize.")
            return
        
        try:
            res = subprocess.run([self.git_cmd, "-C", self.project_dir, "status", "-s"], 
                                 capture_output=True, text=True, creationflags=CREATE_NO_WINDOW)
            changes = len([line for line in res.stdout.split('\n') if line.strip()])
            if changes > 0:
                self.status_lbl.SetLabel(f"Status: {changes} uncommitted changes.")
            else:
                self.status_lbl.SetLabel("Status: Working tree clean.")
        except Exception as e:
            self.status_lbl.SetLabel("Status: Error checking git status.")

    def _generate_diff(self, show_unchanged):
        wx.BeginBusyCursor()
        try:
            engine = DiffEngine(self.project_dir)
            diffs, summary = engine.render_all_diffs(show_unchanged=show_unchanged)
            
            if not diffs:
                wx.MessageBox("No files found to display.", "Info")
            else:
                win = DiffWindow(diffs, summary)
                win.Show()
        except Exception as e:
            wx.MessageBox(f"Error generating diff: {e}", "Error")
        finally:
            if wx.IsBusy(): wx.EndBusyCursor()

    def on_diff(self, event):
        self._generate_diff(show_unchanged=False)

    def on_diff_all(self, event):
        self._generate_diff(show_unchanged=True)

    def on_commit(self, event):
        dlg = wx.TextEntryDialog(self, "Enter commit message:", "Quick Commit", "Update project files")
        if dlg.ShowModal() == wx.ID_OK:
            message = dlg.GetValue().strip()
            if message:
                self.git_commit(message)
                self.update_git_status()
        dlg.Destroy()

    def git_commit(self, message):
        try:
            if not os.path.isdir(os.path.join(self.project_dir, ".git")):
                subprocess.run([self.git_cmd, "-C", self.project_dir, "init"], check=True, creationflags=CREATE_NO_WINDOW)
                wx.MessageBox("Initialized new Git repository for this project!", "Info")

            subprocess.run([self.git_cmd, "-C", self.project_dir, "add", "."], check=True, creationflags=CREATE_NO_WINDOW)
            subprocess.run([self.git_cmd, "-C", self.project_dir, "commit", "-m", message], check=True, creationflags=CREATE_NO_WINDOW)
            wx.MessageBox("Successfully committed to local Git!", "Success")
        except Exception as e:
            wx.MessageBox(f"Git Error: {str(e)}", "Error")

    def create_github_repo(self, repo_name):
        """Uses the GitHub CLI to create a new remote repo and push the current code"""
        try:
            # gh repo create <name> --public --push --source <dir>
            cmd = [self.gh_cmd, "repo", "create", repo_name, "--public", "--push", "--source", self.project_dir]
            res = subprocess.run(cmd, capture_output=True, text=True, creationflags=CREATE_NO_WINDOW)
            
            if res.returncode == 0:
                return True, "Successfully created and pushed to new GitHub repository!"
            else:
                return False, f"Failed to create repo.\n\nError details:\n{res.stderr}"
        except FileNotFoundError:
            return False, "GitHub CLI ('gh') not found.\n\nPlease install it from https://cli.github.com/ or use the manual URL method."
        except Exception as e:
            return False, f"Could not create repo.\n{str(e)}"

    def on_push(self, event):
        if not os.path.isdir(os.path.join(self.project_dir, ".git")):
            wx.MessageBox("This is not a Git repository yet. Please make a 'Quick Commit' first.", "Warning")
            return

        # Check for an existing remote named 'origin'
        res_remote = subprocess.run([self.git_cmd, "-C", self.project_dir, "remote", "get-url", "origin"], 
                                    capture_output=True, text=True, creationflags=CREATE_NO_WINDOW)
        
        if res_remote.returncode != 0:
            # No remote found, ask the user to provide one OR create one
            msg = ("No remote repository linked to this project.\n\n"
                   "Would you like to automatically create a NEW repository on GitHub?\n"
                   "(Requires GitHub CLI 'gh' to be installed and logged in)\n\n"
                   "Click 'Yes' to create via CLI.\n"
                   "Click 'No' to manually paste an existing GitHub URL.")
            
            dlg_choice = wx.MessageDialog(self, msg, "Link GitHub Repository", wx.YES_NO | wx.CANCEL | wx.ICON_QUESTION)
            choice = dlg_choice.ShowModal()
            dlg_choice.Destroy()

            if choice == wx.ID_YES:
                # Flow 1: Create new via GitHub CLI
                default_repo_name = os.path.basename(os.path.abspath(self.project_dir))
                dlg_name = wx.TextEntryDialog(self, "Enter new repository name:", "Create GitHub Repo", default_repo_name)
                
                if dlg_name.ShowModal() == wx.ID_OK:
                    repo_name = dlg_name.GetValue().strip()
                    dlg_name.Destroy()
                    if repo_name:
                        wx.BeginBusyCursor()
                        success, result_msg = self.create_github_repo(repo_name)
                        if wx.IsBusy(): wx.EndBusyCursor()
                        
                        if success:
                            wx.MessageBox(result_msg, "Success")
                            return  # The --push flag handled the push, we can exit early.
                        else:
                            wx.MessageBox(result_msg, "Error")
                            return
                else:
                    dlg_name.Destroy()
                    return

            elif choice == wx.ID_NO:
                # Flow 2: Manual URL Paste
                dlg_url = wx.TextEntryDialog(
                    self, 
                    "Paste the existing repository URL here\n(e.g., https://github.com/user/repo.git):", 
                    "Link Existing Repository"
                )
                if dlg_url.ShowModal() == wx.ID_OK:
                    remote_url = dlg_url.GetValue().strip()
                    if remote_url:
                        try:
                            subprocess.run([self.git_cmd, "-C", self.project_dir, "remote", "add", "origin", remote_url], 
                                           check=True, creationflags=CREATE_NO_WINDOW)
                            wx.MessageBox("Successfully linked to remote repository!", "Success")
                        except Exception as e:
                            wx.MessageBox(f"Failed to add remote:\n{e}", "Error")
                            dlg_url.Destroy()
                            return
                    else:
                        dlg_url.Destroy()
                        return
                else:
                    dlg_url.Destroy()
                    return
                dlg_url.Destroy()
            else:
                # Flow 3: Cancelled
                return

        # Push to the remote (Standard flow if remote exists or was just added via URL)
        try:
            # Get current branch (usually main or master)
            res_br = subprocess.run([self.git_cmd, "-C", self.project_dir, "branch", "--show-current"], 
                                    capture_output=True, text=True, creationflags=CREATE_NO_WINDOW)
            branch = res_br.stdout.strip() or "main"
            
            # Show busy cursor during push (it involves network traffic)
            wx.BeginBusyCursor()
            res_push = subprocess.run([self.git_cmd, "-C", self.project_dir, "push", "-u", "origin", branch], 
                                      capture_output=True, text=True, creationflags=CREATE_NO_WINDOW)
            wx.EndBusyCursor()
            
            if res_push.returncode == 0:
                wx.MessageBox("Successfully pushed code to GitHub!", "Push Complete")
            else:
                # Often occurs if they haven't authenticated the terminal with GitHub yet, or on merge conflicts
                wx.MessageBox(f"Failed to push code.\n\nError Details:\n{res_push.stderr}", "Push Error")
                
        except Exception as e:
            if wx.IsBusy(): wx.EndBusyCursor()
            wx.MessageBox(f"An unexpected error occurred during push:\n{e}", "Error")

    def on_close(self, event):
        self.Destroy()

class GithubActionPlugin(pcbnew.ActionPlugin):
    def defaults(self):
        self.name = "GitHub Command Center"
        self.category = "Tool"
        self.description = "Visual Diff & GitHub Commit for Schematics & PCB"
        self.show_toolbar_button = True 
        
        plugin_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(plugin_dir, 'icon.png')
        
        if not os.path.isfile(icon_path):
            parent_dir = os.path.dirname(plugin_dir)
            grandparent_dir = os.path.dirname(parent_dir)
            plugin_id = os.path.basename(plugin_dir)      
            resource_path = os.path.join(grandparent_dir, 'resources', plugin_id, 'icon.png')
            if os.path.isfile(resource_path):
                icon_path = resource_path
            else:
                resource_path_n = os.path.join(grandparent_dir, 'resources', plugin_id + 'n', 'icon.png')
                if os.path.isfile(resource_path_n):
                    icon_path = resource_path_n

        self.icon_file_name = icon_path

    def Run(self):
        board = pcbnew.GetBoard()
        board_path = board.GetFileName()
        
        if not board_path or not os.path.exists(board_path):
            wx.MessageBox("Please save your board before using Git features.", "Error")
            return
            
        project_dir = os.path.dirname(board_path)
        
        # Open the new Command Center Dialog instead of running straight away
        dlg = CommandCenterDialog(None, project_dir)
        dlg.ShowModal()