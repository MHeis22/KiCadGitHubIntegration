import wx
import os
import subprocess
import pcbnew
import re
from .diff_engine import DiffEngine
from .diff_window import DiffWindow

# Fix for Windows: prevents the plugin from popping up CMD windows or hanging
CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

class CommandCenterDialog(wx.Dialog):
    def __init__(self, parent, project_dir):
        super().__init__(parent, title="GitHub Command Center", size=(500, 500))
        self.project_dir = project_dir
        self.git_cmd = "git.exe" if os.name == "nt" else "git"
        
        panel = wx.Panel(self)
        main_vbox = wx.BoxSizer(wx.VERTICAL)
        
        # --- Header & Status ---
        header = wx.StaticText(panel, label="Git Hardware Control")
        header_font = header.GetFont()
        header_font.SetWeight(wx.FONTWEIGHT_BOLD)
        header_font.SetPointSize(12)
        header.SetFont(header_font)
        main_vbox.Add(header, flag=wx.ALIGN_CENTER | wx.TOP | wx.BOTTOM, border=15)

        self.status_lbl = wx.StaticText(panel, label="Checking status...")
        main_vbox.Add(self.status_lbl, flag=wx.LEFT | wx.RIGHT | wx.BOTTOM, border=15)
        
        # --- Action Buttons ---
        btn_diff = wx.Button(panel, label="🔍 View Local Changes (Visual Diff)", size=(-1, 40))
        btn_commit = wx.Button(panel, label="💾 Save Snapshot (Quick Commit)", size=(-1, 40))
        btn_push = wx.Button(panel, label="🚀 Push Changes to GitHub", size=(-1, 40))
        
        # The "Emergency Reset" rebranded as the primary Sync/Download tool
        btn_sync = wx.Button(panel, label="🔄 Download from Server (Force Sync)", size=(-1, 40))
        btn_sync.SetBackgroundColour(wx.Colour(230, 240, 255)) # Subtle highlight
        
        btn_diff.Bind(wx.EVT_BUTTON, self.on_diff)
        btn_commit.Bind(wx.EVT_BUTTON, self.on_commit)
        btn_push.Bind(wx.EVT_BUTTON, self.on_push)
        btn_sync.Bind(wx.EVT_BUTTON, self.on_force_sync)
        
        main_vbox.Add(btn_diff, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, border=10)
        main_vbox.Add(btn_commit, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, border=10)
        main_vbox.Add(btn_push, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, border=10)
        main_vbox.Add(btn_sync, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, border=10)

        # --- Help Text ---
        help_box = wx.StaticBox(panel, label="Sync Instructions")
        help_sizer = wx.StaticBoxSizer(help_box, wx.VERTICAL)
        help_text = (
            "TO SEE CHANGES AFTER SYNC:\n"
            "1. Run 'Download from Server'.\n"
            "2. Close your PCB/Schematic editor.\n"
            "3. If KiCad asks to save, select 'DISCARD CHANGES'.\n"
            "4. Re-open the file to see the server version."
        )
        st_help = wx.StaticText(panel, label=help_text)
        st_help.SetForegroundColour(wx.Colour(100, 100, 100))
        help_sizer.Add(st_help, flag=wx.ALL, border=5)
        main_vbox.Add(help_sizer, flag=wx.EXPAND | wx.ALL, border=15)
        
        btn_close = wx.Button(panel, label="Close")
        btn_close.Bind(wx.EVT_BUTTON, self.on_close)
        main_vbox.Add(btn_close, flag=wx.ALIGN_RIGHT | wx.RIGHT | wx.BOTTOM, border=15)
        
        panel.SetSizer(main_vbox)
        self.update_git_status()

    def update_git_status(self):
        if not os.path.isdir(os.path.join(self.project_dir, ".git")):
            self.status_lbl.SetLabel("Status: Not a Git repository.")
            return
        try:
            res = subprocess.run([self.git_cmd, "-C", self.project_dir, "status", "-s"], 
                                 capture_output=True, text=True, creationflags=CREATE_NO_WINDOW)
            changes = len([line for line in res.stdout.split('\n') if line.strip()])
            self.status_lbl.SetLabel(f"Status: {changes} local changes." if changes > 0 else "Status: Clean.")
        except:
            self.status_lbl.SetLabel("Status: Git Error.")

    def on_diff(self, event):
        wx.BeginBusyCursor()
        try:
            engine = DiffEngine(self.project_dir)
            diffs, summary = engine.render_all_diffs(show_unchanged=False, compare_target="HEAD")
            if not diffs:
                wx.MessageBox("No local changes detected.", "Info")
            else:
                win = DiffWindow(diffs, summary)
                win.Show()
        finally:
            if wx.IsBusy(): wx.EndBusyCursor()

    def on_force_sync(self, event):
        """Rebranded Emergency Reset: The primary way to get server data."""
        if not os.path.isdir(os.path.join(self.project_dir, ".git")):
            wx.MessageBox("No Git repo found.", "Error")
            return

        # Try to find current branch to suggest a target
        res_br = subprocess.run([self.git_cmd, "-C", self.project_dir, "branch", "--show-current"], 
                                capture_output=True, text=True, creationflags=CREATE_NO_WINDOW)
        curr = res_br.stdout.strip() or "main"
        
        dlg = wx.TextEntryDialog(self, "Enter branch to download (e.g. origin/main):", "Force Download", f"origin/{curr}")
        if dlg.ShowModal() == wx.ID_OK:
            target = dlg.GetValue().strip()
            if target:
                self.perform_atomic_overwrite(target)
        dlg.Destroy()

    def perform_atomic_overwrite(self, remote_ref):
        wx.BeginBusyCursor()
        try:
            # 1. Fetch first to make sure we have the latest refs
            subprocess.run([self.git_cmd, "-C", self.project_dir, "fetch", "origin"], creationflags=CREATE_NO_WINDOW)

            # 2. Force the overwrite
            subprocess.run([self.git_cmd, "-C", self.project_dir, "reset", "--hard", remote_ref], 
                                 capture_output=True, text=True, check=True, creationflags=CREATE_NO_WINDOW)
            subprocess.run([self.git_cmd, "-C", self.project_dir, "clean", "-fd"], creationflags=CREATE_NO_WINDOW)

            # 3. Success Feedback with instructions
            pcbnew.Refresh()
            msg = ("SUCCESS!\n\n"
                   "Local files updated to match " + remote_ref + ".\n\n"
                   "IMPORTANT: Close your PCB/Schematic editor now. "
                   "When prompted, select 'DISCARD CHANGES' to load the new version.")
            wx.MessageBox(msg, "Sync Complete")
            self.update_git_status()
        except subprocess.CalledProcessError as e:
            wx.MessageBox(f"Sync Failed:\n{e.stderr}", "Git Error")
        except Exception as e:
            wx.MessageBox(f"Error: {e}", "Error")
        finally:
            if wx.IsBusy(): wx.EndBusyCursor()

    def on_commit(self, event):
        dlg = wx.TextEntryDialog(self, "Commit message:", "Quick Commit", "Update")
        if dlg.ShowModal() == wx.ID_OK:
            msg = dlg.GetValue().strip()
            if msg:
                try:
                    if not os.path.isdir(os.path.join(self.project_dir, ".git")):
                        subprocess.run([self.git_cmd, "-C", self.project_dir, "init"], check=True, creationflags=CREATE_NO_WINDOW)
                    subprocess.run([self.git_cmd, "-C", self.project_dir, "add", "."], check=True, creationflags=CREATE_NO_WINDOW)
                    subprocess.run([self.git_cmd, "-C", self.project_dir, "commit", "-m", msg], check=True, creationflags=CREATE_NO_WINDOW)
                    wx.MessageBox("Committed successfully.", "Success")
                    self.update_git_status()
                except Exception as e:
                    wx.MessageBox(f"Commit failed: {e}", "Error")
        dlg.Destroy()

    def on_push(self, event):
        wx.BeginBusyCursor()
        try:
            res_br = subprocess.run([self.git_cmd, "-C", self.project_dir, "branch", "--show-current"], 
                                    capture_output=True, text=True, creationflags=CREATE_NO_WINDOW)
            branch = res_br.stdout.strip() or "main"
            res = subprocess.run([self.git_cmd, "-C", self.project_dir, "push", "origin", branch], 
                                 capture_output=True, text=True, creationflags=CREATE_NO_WINDOW)
            if res.returncode == 0:
                wx.MessageBox("Pushed to GitHub.", "Success")
            else:
                wx.MessageBox(f"Push Failed:\n{res.stderr}", "Error")
        finally:
            if wx.IsBusy(): wx.EndBusyCursor()

    def on_close(self, event):
        self.Destroy()

class GithubActionPlugin(pcbnew.ActionPlugin):
    def defaults(self):
        self.name = "GitHub Command Center"
        self.category = "Tool"
        self.description = "Visual Diff & Force Sync"
        self.show_toolbar_button = True 
        self.icon_file_name = os.path.join(os.path.dirname(__file__), 'icon.png')

    def Run(self):
        board = pcbnew.GetBoard()
        path = board.GetFileName()
        if not path:
            wx.MessageBox("Save the board first.")
            return
        dlg = CommandCenterDialog(None, os.path.dirname(path))
        dlg.ShowModal()