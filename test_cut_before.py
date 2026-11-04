import copy
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
import cut_before as cb

SAMPLE = Path(__file__).parent / 'examples' / 'new_story.txt'
TEST_TMP = (Path(__file__).parent / '.test_tmp').resolve()
TEST_TMP.mkdir(exist_ok=True)
tempfile.tempdir = str(TEST_TMP)

class CutBeforeTests(unittest.TestCase):
    def setUp(self):
        self.episodes, self.pack_hash = cb.load_pack(SAMPLE)
        self.ep = self.episodes[0]

    def review(self):
        return dict(pack_sha256=self.pack_hash, reviewer='synthetic fixture', method='Not a live model test', reviews=[
            dict(episode=901, decision='shortlist', title='An impossible voice', start='00:00.00', end='00:30.00',
                 scores=dict(hook=4,cliffhanger=5,clarity=4,stakes=4), hook='A man is trapped in a vault.',
                 cliffhanger='Why does she sound like his dead daughter?', reason='The danger becomes an identity mystery.',
                 risk='The identity line takes five seconds; inspect the performance.')])

    def finalize(self, review, root):
        review_file = root / 'review.json'
        cb.dump(review_file, review)
        cb.finalize(SAMPLE, review_file, root / 'out')

    def test_new_story_not_hardcoded(self):
        candidates, count = cb.generate(self.ep)
        self.assertGreater(count, 0)
        self.assertTrue(candidates)
        self.assertTrue(all(c['episode'] == 901 for c in candidates))
        self.assertTrue(all(not cb.boundary_errors(self.ep,c['start'],c['end']) for c in candidates))

    def test_new_input_end_to_end(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            cb.scan(SAMPLE, root / 'out')
            self.finalize(self.review(),root)
            result = json.loads((root/'out'/'ranked_promos.json').read_text(encoding='utf-8'))
            self.assertEqual(result['promos'][0]['duration'], 30)
            self.assertEqual(result['promos'][0]['next_beat'][0]['start'], '00:31.00')

    def test_rejects_invented_time(self):
        self.assertIn('Boundary is not an exact source event boundary', cb.boundary_errors(self.ep,'00:00.10','00:30.00'))

    def test_rejects_cut_dialogue_even_at_camera_boundary(self):
        ep = copy.deepcopy(self.ep)
        ep['beats'].append(dict(id='camera',role='CAMERA',start='00:28.00',end='00:29.00',a=28,b=29,text='Close up.'))
        self.assertTrue(any('Cuts spoken line' in e for e in cb.boundary_errors(ep,'00:00.00','00:29.00')))

    def test_rejects_short_or_long_clip(self):
        for end in ('00:15.00','01:01.00'):
            self.assertIn('Duration must be 20-60 seconds',cb.boundary_errors(self.ep,'00:00.00',end))

    def test_rejects_wrong_pack(self):
        with tempfile.TemporaryDirectory() as d:
            r=self.review(); r['pack_sha256']='different'
            with self.assertRaisesRegex(ValueError,'different input'):
                self.finalize(r,Path(d))

    def test_rejects_missing_and_duplicate_episodes(self):
        for mode in ('missing','duplicate'):
            with tempfile.TemporaryDirectory() as d:
                r=self.review(); r['reviews']=[] if mode=='missing' else r['reviews']*2
                with self.assertRaisesRegex(ValueError,'exactly once'):
                    self.finalize(r,Path(d))

    def test_rejects_invalid_scores_and_weak_shortlist(self):
        for value in (6, True, 2):
            with tempfile.TemporaryDirectory() as d:
                r=self.review(); r['reviews'][0]['scores']['hook']=value
                with self.assertRaises(ValueError): self.finalize(r,Path(d))

    def test_rejects_malformed_input(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bad.txt'
            p.write_text(SAMPLE.read_text().replace('00:02.50','00:XX.50'))
            with self.assertRaisesRegex(ValueError,'parsed'): cb.load_pack(p)

    def test_zip_is_read_without_extracting_paths(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'input.zip'
            with zipfile.ZipFile(p,'w') as z: z.writestr('../../outside.txt',SAMPLE.read_bytes())
            episodes,_=cb.load_pack(p)
            self.assertEqual(episodes[0]['episode'],901)
            self.assertEqual(list(Path(d).iterdir()),[p])

    def test_html_escapes_model_text(self):
        with tempfile.TemporaryDirectory() as d:
            r=self.review(); r['reviews'][0]['title']='<script>alert(1)</script>'
            self.finalize(r,Path(d))
            page=(Path(d)/'out'/'report.html').read_text(encoding='utf-8')
            self.assertNotIn('<script>alert(1)</script>',page)
            self.assertIn('&lt;script&gt;',page)

    def test_timestamp_validation(self):
        with self.assertRaises(ValueError): cb.seconds('00:60.00')
        self.assertEqual(cb.stamp(125.75),'02:05.75')

if __name__ == '__main__': unittest.main(verbosity=2)
