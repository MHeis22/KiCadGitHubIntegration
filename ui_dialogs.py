import wx

class SettingsDialog(wx.Dialog):
    def __init__(self, parent, current_settings):
        super().__init__(parent, title="Settings", size=(450, 250)) 
        self.settings = current_settings.copy()
        
        vbox = wx.BoxSizer(wx.VERTICAL)
        
        # KiCad Version toggle
        self.cb_kicad_version = wx.CheckBox(self, label="Automatically append KiCad Version to commit messages")
        self.cb_kicad_version.SetValue(self.settings.get('include_kicad_version', True))
        vbox.Add(self.cb_kicad_version, flag=wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.TOP, border=15)
        
        # Auto-Readme toggle
        self.cb_readme = wx.CheckBox(self, label="Automatically update README.md with hardware summary")
        self.cb_readme.SetValue(self.settings.get('auto_readme', False))
        self.cb_readme.SetToolTip("Generates a sticky footer in your README with BOM and board stats.")
        vbox.Add(self.cb_readme, flag=wx.LEFT | wx.RIGHT | wx.BOTTOM, border=15)

        # Silent Pull toggle
        self.cb_silent_pull = wx.CheckBox(self, label="Auto-Pull text files before pushing (Silent Pull)")
        self.cb_silent_pull.SetValue(self.settings.get('silent_pull', False))
        self.cb_silent_pull.SetToolTip("Automatically pulls remote changes to safe text files (README.md, .csv) before pushing.\nAborts pulling if remote KiCad schematic or PCB changes are detected.")
        vbox.Add(self.cb_silent_pull, flag=wx.LEFT | wx.RIGHT | wx.BOTTOM, border=15)
        
        btn_sizer = wx.StdDialogButtonSizer()
        btn_ok = wx.Button(self, wx.ID_OK)
        btn_cancel = wx.Button(self, wx.ID_CANCEL)
        btn_sizer.AddButton(btn_ok)
        btn_sizer.AddButton(btn_cancel)
        btn_sizer.Realize()
        
        vbox.Add(btn_sizer, flag=wx.ALIGN_RIGHT|wx.BOTTOM|wx.RIGHT, border=10)
        self.SetSizer(vbox)
        self.CenterOnParent()
        
    def get_settings(self):
        self.settings['include_kicad_version'] = self.cb_kicad_version.IsChecked()
        self.settings['auto_readme'] = self.cb_readme.IsChecked()
        self.settings['silent_pull'] = self.cb_silent_pull.IsChecked()
        return self.settings


class CommitDialog(wx.Dialog):
    def __init__(self, parent, changed_files, kicad_version="Unknown KiCad Version", include_version=True):
        super().__init__(parent, title="Commit Changes", size=(450, 480))
        self.changed_files = changed_files
        self.kicad_version = kicad_version
        self.include_version = include_version
        
        vbox = wx.BoxSizer(wx.VERTICAL)
        
        # --- File Selection Menu ---
        vbox.Add(wx.StaticText(self, label="Files to Commit (Uncheck to exclude):"), flag=wx.LEFT|wx.TOP, border=10)
        self.clb_files = wx.CheckListBox(self, choices=self.changed_files)
        # Default all turned on
        for i in range(len(self.changed_files)):
            self.clb_files.Check(i, True)
        vbox.Add(self.clb_files, proportion=1, flag=wx.EXPAND|wx.LEFT|wx.RIGHT|wx.TOP, border=10)
        
        # --- Commit Details ---
        vbox.Add(wx.StaticText(self, label="Commit Message:"), flag=wx.LEFT|wx.TOP, border=10)
        self.tc_msg = wx.TextCtrl(self, style=wx.TE_MULTILINE)
        vbox.Add(self.tc_msg, proportion=1, flag=wx.EXPAND|wx.LEFT|wx.RIGHT|wx.TOP, border=10)
        
        vbox.Add(wx.StaticText(self, label="Target Branch (Leave empty to stay on current):"), flag=wx.LEFT|wx.TOP, border=10)
        self.tc_branch = wx.TextCtrl(self)
        vbox.Add(self.tc_branch, flag=wx.EXPAND|wx.ALL, border=10)

        btn_sizer = wx.StdDialogButtonSizer()
        btn_ok = wx.Button(self, wx.ID_OK)
        btn_cancel = wx.Button(self, wx.ID_CANCEL)
        btn_sizer.AddButton(btn_ok)
        btn_sizer.AddButton(btn_cancel)
        btn_sizer.Realize()
        
        vbox.Add(btn_sizer, flag=wx.ALIGN_RIGHT|wx.BOTTOM|wx.RIGHT, border=10)
        self.SetSizer(vbox)

    def get_selected_files(self):
        return [self.changed_files[i] for i in range(self.clb_files.GetCount()) if self.clb_files.IsChecked(i)]

    def get_message(self):
        msg = self.tc_msg.GetValue().strip()
        # Append KiCad version if global setting is enabled
        if self.include_version and self.kicad_version and self.kicad_version != "Unknown KiCad Version":
            if msg:
                msg += f"\n\n[KiCad Version: {self.kicad_version}]"
            else:
                msg = f"[KiCad Version: {self.kicad_version}]"
        return msg

    def get_branch(self):
        return self.tc_branch.GetValue().strip()