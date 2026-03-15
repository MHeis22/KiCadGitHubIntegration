import wx
import os
import pcbnew
from .utils import is_git_installed
from .command_center import CommandCenterDialog

class GithubActionPlugin(pcbnew.ActionPlugin):
    def defaults(self):
        self.name = "GitHub Command Center"
        self.category = "Tool"
        self.description = "Visual Diff & Force Sync"
        self.show_toolbar_button = True 
        self.icon_file_name = os.path.join(os.path.dirname(__file__), 'icon.png')

    def Run(self):
        if not is_git_installed():
            wx.MessageBox("Git is not installed or not in PATH.", "Git Dependency Missing", wx.ICON_ERROR)
            return

        board = pcbnew.GetBoard()
        path = board.GetFileName()
        if not path:
            wx.MessageBox("Save the board first.")
            return
            
        dlg = CommandCenterDialog(None, os.path.dirname(path))
        dlg.ShowModal()