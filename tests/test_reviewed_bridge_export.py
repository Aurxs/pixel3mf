"""Synthetic chain fixtures; only grid detection is fixed, all guards run normally."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import white_fallback as white
import reviewed_bridge_export as export
from white_region_correction import correct_regions


class ReviewedBridgeExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.grid = {'width': 45, 'height': 45}
        self.addCleanup(patch.stopall)
        patch.object(white, 'detect_source_grid', return_value=self.grid).start()

        def refine(src, output, preview, **kwargs):
            a = export.rgba(src)[5::10, 5::10]
            a = np.pad(a, ((2, 2), (2, 2), (0, 0)))
            Image.fromarray(a).save(output)
            Image.fromarray(a).resize((392, 392), Image.Resampling.NEAREST).save(preview)
            return {'detected_grid': self.grid, 'working_grid': {'width': 49, 'height': 49}}

        patch.object(white, 'refine_pixel', side_effect=refine).start()
        patch.object(export, 'sampling_edges', return_value=(list(range(0, 451, 10)), list(range(0, 451, 10)))).start()
        a = np.full((450, 450, 4), 255, dtype=np.uint8)
        a[40:410, 40:410] = [100, 140, 200, 255]
        a[20:40, 30:40] = [100, 140, 200, 255]
        a[37:40, 40:46] = [100, 140, 200, 255]
        a[100:110, 100:110] = 255
        a[200:210, 200:210] = 255
        Image.fromarray(a).save(self.root / 'source.png')
        Image.new('L', (450, 450), 0).save(self.root / 'mask.png')
        white.write_json(self.root / 'failure.json', {
            'schema': 'white-fallback-failure/v1', 'source_sha256': white.sha256(self.root / 'source.png'),
            'failure_kind': 'semantic_mask_unusable', 'reason': 'Synthetic missing foreground',
            'source_accepted': True, 'white_background_suitable': True,
            'model_masks': [{'model': 'isnet-anime', 'path': 'mask.png', 'sha256': white.sha256(self.root / 'mask.png')}]})
        self.original, self.corrected = self.root / 'original', self.root / 'corrected'
        white.prepare(self.root / 'source.png', self.root / 'failure.json', self.original)
        regions = export.read(self.original / 'white_regions.json')
        self.assertEqual(len(regions), 2)
        white.write_json(self.root / 'decisions.json', {
            'schema': 'white-fallback-correction/v1', 'reviewer_role': 'main-conversation',
            'manifest_sha256': white.sha256(self.original / 'candidate.json'),
            'candidate_sha256': white.sha256(self.original / 'candidate.png'),
            'components': {c['id']: {'decision': 'background' if i == 0 else 'preserve',
                                    'reason': 'Reviewed synthetic gap or white patch'} for i, c in enumerate(regions)}})
        correct_regions(self.original, self.root / 'decisions.json', self.corrected)
        bridge = self.root / 'bridge'
        bridge.mkdir()
        a = export.rgba(self.corrected / 'candidate.png')
        colors = sorted({tuple(v[:3]) for v in a.reshape(-1, 4) if v[3]})
        codes = {rgb: f'C{i}' for i, rgb in enumerate(colors)}
        cells = [[codes[tuple(v[:3])] if v[3] else None for v in row] for row in a]
        project = {'schema': 'pixel-art-to-beads/v1', 'cells': cells,
                   'palette': {'colors': [{'code': code, 'rgb': list(map(int, rgb))} for rgb, code in codes.items()]}}
        white.write_json(bridge / 'input.json', project)
        for src, name in ((self.original / '02_white_cutout.png', 'source.png'),
                          (self.corrected / 'candidate.png', 'reference.png')):
            (bridge / name).write_bytes(src.read_bytes())
        report = export.read(self.corrected / 'correction.json')
        ox, oy = [v - 2 for v in report['candidate_crop_origin_in_working']]
        h, w = a.shape[:2]
        xs, ys = list(range(ox*10, (ox+w)*10+1, 10)), list(range(oy*10, (oy+h)*10+1, 10))
        src = export.rgba(bridge / 'source.png')
        sampled = src[np.array(ys[:-1])[:, None]+5, np.array(xs[:-1])[None, :]+5]
        differences = [{'x': int(x), 'y': int(y), 'sampled': sampled[y,x].tolist(), 'reference': a[y,x].tolist()}
                       for y,x in np.argwhere(np.any(sampled != a, axis=2))]
        evidence = {'schema': 'pixel-sampling-evidence/v1', 'alpha_threshold': 128,
                    'source_canvas': 'source.png', 'reference_grid': 'reference.png',
                    'source_canvas_sha256': white.sha256(bridge/'source.png'),
                    'reference_grid_sha256': white.sha256(bridge/'reference.png'),
                    'x_edges': xs, 'y_edges': ys, 'reference_differences': differences,
                    'manifest_cleanup': {'removed_edge_white_pixels': len(differences)}}
        white.write_json(bridge/'evidence.json', evidence)
        report = export.run_bridge(bridge/'input.json', bridge/'evidence.json', bridge/'result.json', max_additions=1)
        self.assertEqual(len(report['added_cells']), 1)
        for c in report['added_cells']:
            a[c['y'], c['x']] = [*colors[int(c['code'][1:])], 255]
        Image.fromarray(a).save(self.root/'final.png')
        self.convert_context = {'character_name': 'Synthetic', 'research': self.root/'research.md',
                                'official_sources': ['https://example.org/synthetic']}
        self.convert_context['research'].write_text('Synthetic test only')
        self.bundle = self.root/'bundle'
        export.prepare(self.original, self.corrected, bridge/'input.json', bridge/'evidence.json',
                       bridge/'result.json', self.root/'final.png', self.bundle)
        self.review = self.bundle/'review.json'
        data = export.read(self.bundle/'review.template.json')
        data.update(decision='approved', notes='Main reviewed the synthetic correction and one-cell bridge')
        data['checks'] = dict.fromkeys(data['checks'], True)
        data['components'] = {key: {'decision':'foreground', 'reason':'Reviewed white patch'} for key in data['components']}
        white.write_json(self.review, data)

    def test_promotion_preserves_exact_bytes_rgba_dimensions_and_lineage(self):
        original = (self.root/'final.png').read_bytes()
        export.promote(self.review)
        self.assertEqual((self.bundle/'04_pixel_perfect.png').read_bytes(), original)
        self.assertTrue(np.array_equal(export.rgba(self.bundle/'candidate.png'), export.rgba(self.bundle/'04_pixel_perfect.png')))
        self.assertEqual(export.rgba(self.bundle/'05_pixel_preview_8x.png').shape[:2], tuple(v*8 for v in export.rgba(self.bundle/'candidate.png').shape[:2]))
        with self.assertRaisesRegex(ValueError, 'preserve existing'):
            export.promote(self.review)

    def test_pending_old_role_missing_region_and_old_hash_approvals_rejected(self):
        baseline = export.read(self.review)
        for change in ({'decision':'pending'}, {'schema':'white-fallback-review/v1'}, {'reviewer_role':'worker'},
                       {'candidate_sha256':'0'*64}, {'manifest_sha256':'0'*64}, {'components':{}}, {'checks':{}}):
            with self.subTest(change=change):
                white.write_json(self.review, {**baseline, **change})
                with self.assertRaises(ValueError): export.promote(self.review)
                self.assertFalse((self.bundle/'04_pixel_perfect.png').exists())

    def test_all_chain_artifact_tampering_rejected_before_promotion(self):
        for name in ('candidate.png', 'candidate_8x.png', 'original/01_source.png', 'original/candidate.json',
                     'corrected/correction.json', 'corrected/correction_decisions.json',
                     'bridge/input.json', 'bridge/evidence.json', 'bridge/result.json'):
            with self.subTest(name=name):
                p = self.bundle/name
                old = p.read_bytes()
                p.write_bytes(old + b' ')
                try:
                    with self.assertRaises(ValueError): export.promote(self.review)
                finally: p.write_bytes(old)

    def rebind(self, name):
        manifest = export.read(self.bundle/'candidate.json')
        manifest['artifacts'][name] = white.sha256(self.bundle/name)
        white.write_json(self.bundle/'candidate.json', manifest)
        review = export.read(self.review)
        review['manifest_sha256'] = white.sha256(self.bundle/'candidate.json')
        if name == 'candidate.png': review['candidate_sha256'] = white.sha256(self.bundle/name)
        white.write_json(self.review, review)

    def test_rebound_final_recolor_is_rejected_by_chain_replay(self):
        a = export.rgba(self.bundle/'candidate.png'); a[0,0,0] ^= 1
        Image.fromarray(a).save(self.bundle/'candidate.png'); self.rebind('candidate.png')
        with self.assertRaisesRegex(ValueError, 'final RGBA'): export.promote(self.review)

    def test_rebound_bridge_report_is_rejected_by_formal_replay(self):
        p = self.bundle/'bridge/result.json'; data = export.read(p)
        data['bridge_repair']['added_cells'][0]['source_coverage'] = 1.0
        white.write_json(p, data); self.rebind('bridge/result.json')
        with self.assertRaisesRegex(ValueError, 'bridge report'): export.promote(self.review)

    def test_rebound_wrong_source_and_boundaries_rejected(self):
        p = self.bundle/'bridge/evidence.json'; original = p.read_bytes()
        for key, value in (('source_canvas', 'reference.png'), ('x_edges', [0, 10])):
            data = json.loads(original); data[key] = value
            white.write_json(p,data); self.rebind('bridge/evidence.json')
            with self.assertRaises(ValueError): export.promote(self.review)
        p.write_bytes(original)

    def test_rebound_correction_record_rejected(self):
        p = self.bundle/'corrected/correction.json'
        record = export.read(p); record['removed_cells'] += 1
        white.write_json(p, record)
        manifest_path = self.bundle/'corrected/candidate.json'
        manifest = export.read(manifest_path)
        manifest['artifacts']['correction.json'] = white.sha256(p)
        white.write_json(manifest_path, manifest)
        self.rebind('corrected/correction.json')
        self.rebind('corrected/candidate.json')
        with self.assertRaisesRegex(ValueError, 'replay mismatch'): export.promote(self.review)

    def test_rebound_original_density_outside_gate_rejected(self):
        p = self.bundle/'original/candidate.json'
        record = export.read(p); record['source_grid']['width'] = 44
        white.write_json(p, record); self.rebind('original/candidate.json')
        with self.assertRaisesRegex(ValueError, 'overly coarse'): export.promote(self.review)

    def test_incomplete_hash_inventory_and_path_escape_rejected(self):
        p = self.bundle/'candidate.json'; original = p.read_bytes()
        for name in ('original/01_source.png', 'bridge/result.json'):
            manifest = json.loads(original); manifest['artifacts'].pop(name)
            white.write_json(p, manifest)
            review = export.read(self.review); review['manifest_sha256'] = white.sha256(p)
            white.write_json(self.review, review)
            with self.assertRaisesRegex(ValueError, 'inventory'): export.promote(self.review)
        with self.assertRaisesRegex(ValueError, 'unsafe'): export.local(self.bundle, '../outside')

    def test_conversion_requires_promotion_and_binds_both_variants_to_final(self):
        out = self.root/'export'
        with self.assertRaises(FileNotFoundError): export.convert(self.review,out,self.root/'lumina', **self.convert_context)
        export.promote(self.review)
        lut = self.root/'lumina/lut-npy预设/bambulab'/export.LUT_FILENAME
        lut.parent.mkdir(parents=True); lut.write_bytes(b'synthetic LUT')
        seen = []
        def convert(image, archive, final, lumina, api, **kwargs):
            seen.append((white.sha256(image),kwargs['cells_per_logical_pixel'],kwargs['size_plan']))
            archive.write_bytes(b'raw'); final.write_bytes(b'fixture')
            Image.new('RGB',(2,2)).save(kwargs['preview_path'])
            return {'lut_path':str(lut)}
        with patch.object(export,'convert_with_lumina_batch',side_effect=convert):
            export.convert(self.review,out,self.root/'lumina', **self.convert_context)
        self.assertEqual([x[1] for x in seen],[2,3])
        self.assertTrue(all(x[0] == white.sha256(self.root/'final.png') for x in seen))
        self.assertEqual(export.read(out/'manifest.json')['status'],'needs_main_color_review')
        self.assertTrue((out/'reviewed_chain/original/01_source.png').is_file())

    def test_changed_promoted_image_never_reaches_conversion(self):
        export.promote(self.review)
        with (self.bundle/'04_pixel_perfect.png').open('ab') as f: f.write(b'changed')
        with patch.object(export,'convert_with_lumina_batch') as call:
            with self.assertRaisesRegex(ValueError,'promoted pixels'):
                export.convert(self.review,self.root/'export',self.root/'lumina', **self.convert_context)
            call.assert_not_called()


if __name__ == '__main__': unittest.main()
