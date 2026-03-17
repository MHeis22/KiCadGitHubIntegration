# Two way of installation of this plugin:
#  - Copy or link this directory to KiCad plugin directory
#  - Copy files to ~/.kicad_plugin except __init__.py...
from __future__ import print_function
import traceback
import sys
import os

# Add current directory to path for relative imports
plugin_dir = os.path.dirname(__file__)
if plugin_dir not in sys.path:
    sys.path.append(plugin_dir)

print(f"Starting plugin GitHub Integration from {plugin_dir}")

try:
    from .github_plugin import GithubActionPlugin
    plugin = GithubActionPlugin()
    plugin.register()
    print("GitHub Integration: Registered successfully")
except Exception as e:
    print("GitHub Integration: Failed to load")
    traceback.print_exc(file=sys.stdout)