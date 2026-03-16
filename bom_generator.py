import os
import csv
import glob
from .kicad_parser import get_bom_data

class BOMGenerator:
    def __init__(self, project_dir, settings=None):
        self.project_dir = project_dir
        self.settings = settings or {}
        self.mpn_field = self.settings.get('mpn_field_name', 'MPN')

    def generate_boms(self):
        """Generates two CSV files: a distributor-friendly one and a full engineering one."""
        sch_files = glob.glob(os.path.join(self.project_dir, "*.kicad_sch"))
        if not sch_files:
            return []

        # Merge BOM data from all schematic files
        all_bom = {}
        for sch in sch_files:
            all_bom.update(get_bom_data(sch))

        if not all_bom:
            return []

        # Get project name for file naming
        project_name = "project"
        pro_files = glob.glob(os.path.join(self.project_dir, "*.kicad_pro"))
        if pro_files:
            project_name = os.path.splitext(os.path.basename(pro_files[0]))[0]

        dist_path = os.path.join(self.project_dir, f"{project_name}_distributor_bom.csv")
        full_path = os.path.join(self.project_dir, f"{project_name}_full_bom.csv")

        # 1. Generate Full Engineering BOM (grouped by Value/Footprint/MPN)
        self._write_full_bom(full_path, all_bom)

        # 2. Generate Distributor BOM (Minimal: Qty, Ref, MPN)
        self._write_distributor_bom(dist_path, all_bom)

        return [dist_path, full_path]

    def _write_full_bom(self, path, bom):
        """Detailed BOM for human review."""
        groups = {}
        for ref, data in bom.items():
            # Signature for grouping
            sig = (data['val'], data['fp'], data['mpn'], data['desc'])
            if sig not in groups:
                groups[sig] = {'refs': [], 'data': data}
            groups[sig]['refs'].append(ref)

        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Qty', 'Reference', 'Value', 'Footprint', 'MPN', 'Description'])
            
            # Sort by Value then Footprint
            for sig in sorted(groups.keys()):
                item = groups[sig]
                refs = sorted(item['refs'])
                writer.writerow([
                    len(refs),
                    ", ".join(refs),
                    item['data']['val'],
                    item['data']['fp'],
                    item['data']['mpn'],
                    item['data']['desc']
                ])

    def _write_distributor_bom(self, path, bom):
        """Compact BOM for automated tool uploads."""
        groups = {}
        for ref, data in bom.items():
            mpn = data['mpn'] if data['mpn'] else "NO_MPN"
            if mpn not in groups:
                groups[mpn] = []
            groups[mpn].append(ref)

        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Qty', 'Reference', 'Manufacturer_Part_Number'])
            
            for mpn in sorted(groups.keys()):
                refs = sorted(groups[mpn])
                writer.writerow([
                    len(refs),
                    ", ".join(refs),
                    mpn
                ])