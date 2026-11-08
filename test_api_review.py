"""Offline API contract tests using synthetic responses, never paid model calls."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

import api_review as api
import cut_before as cb

SAMPLE = Path(__file__).parent / 'examples/new_story.txt'
TEST_TMP = (Path(__file__).parent / '.test_tmp').resolve()
TEST_TMP.mkdir(exist_ok=True)
tempfile.tempdir = str(TEST_TMP)


class APIReviewTests(unittest.TestCase):
    def setUp(self):
        self.review = json.loads((SAMPLE.parent/'sample_review.json').read_text(encoding='utf-8'))
        self.review['pack_sha256'] = cb.load_pack(SAMPLE)[1]

    def payload(self, protocol='responses', review=None):
        text = json.dumps(review or self.review)
        base = dict(id='mock-response', model='mock-interview-model', usage={'total_tokens':123})
        if protocol == 'responses':
            base.update(status='completed', output=[{'type':'message','content':[{'type':'output_text','text':text}]}])
        else:
            base['choices'] = [{'finish_reason':'stop','message':{'content':text}}]
        return json.dumps(base).encode()

    def test_both_protocols_end_to_end_and_raw_preserved(self):
        for protocol in ('responses','chat_completions'):
            with self.subTest(protocol=protocol), tempfile.TemporaryDirectory() as d:
                payload = self.payload(protocol)
                with patch.object(api, 'post_json', return_value=payload) as post:
                    report = api.review_with_api(SAMPLE, Path(d)/'run', api_key='unit-test-key',
                        model='interview-model', protocol=protocol)
                self.assertTrue(report.exists())
                self.assertEqual(post.call_count, 1)
                self.assertEqual((report.parent/'api_responses/episode_901.response.json').read_bytes(),payload)
                manifest=json.loads((report.parent/'api_run.json').read_text())
                self.assertEqual(manifest['status'],'validated')
                self.assertEqual(manifest['calls'][0]['usage']['total_tokens'],123)
                for p in report.parent.rglob('*'):
                    if p.is_file(): self.assertNotIn('unit-test-key',p.read_text(encoding='utf-8-sig'))

    def test_provider_switch_and_token_settings(self):
        url,body=api.request_spec('responses','https://api.openai.com/v1/','provided-model','hello')
        self.assertEqual(url,'https://api.openai.com/v1/responses')
        self.assertFalse(body['store'])
        url,body=api.request_spec('chat_completions','https://interview.example/v1','other-model','hello',8192,'max_tokens')
        self.assertEqual(url,'https://interview.example/v1/chat/completions')
        self.assertEqual(body['max_tokens'],8192)
        self.assertEqual(body['model'],'other-model')

    def test_bad_json_does_not_produce_report(self):
        payload=json.loads(self.payload())
        payload['output'][0]['content'][0]['text']='not json'
        with tempfile.TemporaryDirectory() as d, patch.object(api,'post_json',return_value=json.dumps(payload).encode()):
            out=Path(d)/'run'
            with self.assertRaises(api.APIReviewError):
                api.review_with_api(SAMPLE,out,api_key='test',model='test')
            self.assertFalse((out/'report.html').exists())
            self.assertTrue((out/'api_responses/episode_901.response.json').exists())
            self.assertEqual(json.loads((out/'api_run.json').read_text())['status'],'failed')

    def test_invalid_model_timestamp_reaches_existing_validator(self):
        bad=copy.deepcopy(self.review)
        bad['reviews'][0]['start']='00:00.01'
        with tempfile.TemporaryDirectory() as d, patch.object(api,'post_json',return_value=self.payload(review=bad)):
            out=Path(d)/'run'
            with self.assertRaises(ValueError):
                api.review_with_api(SAMPLE,out,api_key='test',model='test')
            self.assertFalse((out/'report.html').exists())
            self.assertTrue((out/'ai_review.json').exists())

    def test_truncation_refusal_and_wrong_episode_rejected(self):
        for data,protocol in [({'status':'incomplete'},'responses'),
                              ({'choices':[{'finish_reason':'length'}]},'chat_completions'),
                              ({'choices':[{'finish_reason':'stop','message':{'refusal':'no'}}]},'chat_completions')]:
            with self.assertRaises(api.APIReviewError): api.response_text(data,protocol)
        with self.assertRaises(api.APIReviewError):
            api.parse_review(json.dumps(self.review),self.review['pack_sha256'],902)
        with self.assertRaises(api.APIReviewError):
            api.parse_review(json.dumps(self.review),'wrong-hash',901)

    def test_episode_guard_and_existing_output_make_no_calls(self):
        with tempfile.TemporaryDirectory() as d, patch.object(api,'post_json') as post:
            with self.assertRaises(api.APIReviewError):
                api.review_with_api(SAMPLE,Path(d)/'run',api_key='test',model='test',max_episodes=0)
            with self.assertRaises(api.APIReviewError):
                api.review_with_api(SAMPLE,Path(d),api_key='test',model='test')
            post.assert_not_called()

    def test_unsafe_endpoints_rejected_and_redirects_disabled(self):
        for url in ('http://api.example/v1','https://user:secret@api.example/v1','https://api.example/v1?key=secret'):
            with self.assertRaises(api.APIReviewError): api.request_spec('responses',url,'model','prompt')
        self.assertIsNone(api.NoRedirect().redirect_request(None,None,302,'',{},'https://other.example'))

    def test_http_errors_do_not_leak_or_retry(self):
        err=urllib.error.HTTPError('https://api.example',401,'secret-body',{},None)
        with patch('urllib.request.build_opener') as opener:
            opener.return_value.open.side_effect=err
            with self.assertRaises(api.APIReviewError) as caught:
                api.post_json('https://api.example',{},'private-test-key')
            self.assertNotIn('secret-body',str(caught.exception))
            self.assertNotIn('private-test-key',str(caught.exception))
            self.assertEqual(opener.return_value.open.call_count,1)


if __name__ == '__main__':
    unittest.main()
