import os
import tempfile
import webbrowser
import pathlib
import json
import base64

class DiffWindow:
    def __init__(self, diffs, summary_text, target_name="HEAD", kicad_version="Unknown KiCad Version", colorblind=False):
        """
        diffs expects a list of dicts: 
        [{'name': '...', 'status': '...', 'visuals': {...}, 'bom_data': {'curr':{}, 'old':{}}}]
        """
        self.diffs = diffs
        self.summary_text = summary_text.replace('\n', '<br>')
        self.target_name = target_name
        self.kicad_version = kicad_version
        self.colorblind = colorblind

    def _get_data_uri(self, file_path):
        """Reads a file and returns a Base64 encoded Data URI for embedding."""
        if not file_path or not os.path.exists(file_path):
            return ""
        try:
            ext = file_path.lower().split('.')[-1]
            mime_type = "image/svg+xml" if ext == "svg" else ("application/pdf" if ext == "pdf" else "image/png")
            with open(file_path, "rb") as f:
                encoded = base64.b64encode(f.read()).decode('utf-8')
            return f"data:{mime_type};base64,{encoded}"
        except Exception as e:
            print(f"Error encoding {file_path}: {e}")
            return ""

    def Show(self):
        html_path = os.path.join(tempfile.gettempdir(), "kicad_diff_viewer.html")
        
        # Prepare data for JavaScript
        js_diffs = []
        for d in self.diffs:
            processed_visuals = {}
            for layer, paths in d.get('visuals', {}).items():
                curr_uri = self._get_data_uri(paths.get('curr'))
                old_uri = self._get_data_uri(paths.get('old'))
                processed_visuals[layer] = {"curr": curr_uri, "old": old_uri}

            js_diffs.append({
                "name": d['name'],
                "status": d.get('status', 'Unknown'),
                "visuals": processed_visuals,
                "netlistDiff": d.get('netlist_diff', ''),
                "bomData": d.get('bom_data', {'curr': {}, 'old': {}}),
                "pcbLogicDiff": d.get('pcb_logic_diff', ''),
                "todos": d.get('todos', {'curr': [], 'old': []}),
                "dimensions": d.get('dimensions', {'curr': None, 'old': None}),
                "health": d.get('health', {'new': [], 'resolved': [], 'unresolved': []})
            })

        diff_json = json.dumps(js_diffs)
        colorblind_class = "colorblind-theme" if self.colorblind else ""

        # Load the template file
        template_path = os.path.join(os.path.dirname(__file__), "viewer_template.html")
        with open(template_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        # Inject Python variables safely
        html_content = html_content.replace('__COLORBLIND_CLASS__', colorblind_class)
        html_content = html_content.replace('__TARGET_NAME__', self.target_name)
        html_content = html_content.replace('__KICAD_VERSION__', self.kicad_version)
        html_content = html_content.replace('__DIFF_JSON__', diff_json)

        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
            
        webbrowser.open(pathlib.Path(html_path).as_uri())