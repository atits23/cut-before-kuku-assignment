"""Offline API contract tests using synthetic responses, never paid model calls."""
import copy
import io
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
    def test_complete_endpoints_and_whitespace(self):
        for base in (' https://api.openai.com/ ', 'https://api.openai.com/v1/responses',
                     'https://api.openai.com/v1/chat/completions/'):
            url, body = api.request_spec('responses',base,' model-id ','hello')
            self.assertEqual(url,'https://api.openai.com/v1/responses')
            self.assertEqual(body['model'],'model-id')

    def test_bearer_and_json_headers(self):
        with patch('urllib.request.build_opener') as opener:
            opener.return_value.open.return_value.__enter__.return_value.read.return_value=b'{}'
            api.post_json('https://api.openai.com/v1/responses',{},'private-test-key')
            req=opener.return_value.open.call_args.args[0]
            self.assertEqual(req.get_header('Authorization'),'Bearer private-test-key')
            self.assertEqual(req.get_header('Content-type'),'application/json')
            self.assertEqual(req.get_header('Accept'),'application/json')
            self.assertIn('CutBefore',req.get_header('User-agent'))

    def test_actionable_error_does_not_echo_message(self):
        payload=json.dumps({'error':{'code':'model_not_found',
            'message':'model not found private-test-key confidential screenplay'}}).encode()
        err=urllib.error.HTTPError('https://api.example',404,'Not Found',{},io.BytesIO(payload))
        with patch('urllib.request.build_opener') as opener:
            opener.return_value.open.side_effect=err
            with self.assertRaises(api.APIReviewError) as caught:
                api.post_json('https://api.example',{},'private-test-key')
            message=str(caught.exception)
            self.assertIn('model_not_found',message)
            self.assertNotIn('private-test-key',message)
            self.assertNotIn('confidential screenplay',message)

    def test_connection_check_all_protocols(self):
        for protocol in ('responses','chat_completions','gemini'):
            if protocol=='gemini':
                payload={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'{"ok":true}'}]}}]}
            elif protocol=='responses':
                payload={'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':'{"ok":true}'}]}]}
            else:
                payload={'choices':[{'finish_reason':'stop','message':{'content':'{"ok":true}'}}]}
            with patch.object(api,'post_json',return_value=json.dumps(payload).encode()) as post:
                result=api.test_connection(api_key='test',model='model',protocol=protocol,
                    base_url=api.GEMINI_BASE if protocol=='gemini' else 'https://api.openai.com/v1')
                self.assertIn('passed',result)
                self.assertEqual(post.call_count,1)

    def test_gemini_end_to_end(self):
        payload=json.dumps(dict(responseId='gem-test',modelVersion='available-gemini-model',
            usageMetadata={'totalTokenCount':321},candidates=[dict(finishReason='STOP',
            content=dict(parts=[dict(text=json.dumps(self.review))]))])).encode()
        with tempfile.TemporaryDirectory() as d,patch.object(api,'post_json',return_value=payload) as post:
            report=api.review_with_api(SAMPLE,Path(d)/'run',api_key='test',model='models/available-gemini-model',
                protocol='gemini',base_url='https://generativelanguage.googleapis.com')
            self.assertTrue(report.exists())
            url,body,key,timeout=post.call_args.args
            self.assertEqual(url,api.GEMINI_BASE+'/models/available-gemini-model:generateContent')
            self.assertEqual(body['generationConfig']['responseMimeType'],'application/json')
            manifest=json.loads((report.parent/'api_run.json').read_text())
            self.assertEqual(manifest['calls'][0]['usage']['totalTokenCount'],321)

    def test_gemini_uses_header_key_and_get_for_models(self):
        with patch('urllib.request.build_opener') as opener:
            opener.return_value.open.return_value.__enter__.return_value.read.return_value=b'{}'
            api.post_json(api.GEMINI_BASE+'/models',None,'private-gem-key')
            req=opener.return_value.open.call_args.args[0]
            self.assertEqual(req.method,'GET')
            self.assertEqual(req.get_header('X-goog-api-key'),'private-gem-key')
            self.assertIsNone(req.get_header('Authorization'))
            self.assertNotIn('private-gem-key',req.full_url)

    def test_gemini_model_discovery_pagination_and_selection(self):
        pages=[json.dumps({'models':[{'name':'models/current-a','supportedGenerationMethods':['generateContent']}],
                          'nextPageToken':'next page'}).encode(),
               json.dumps({'models':[{'name':'models/embed','supportedGenerationMethods':['embedContent']},
                                     {'name':'models/current-b','supportedGenerationMethods':['generateContent']}]}).encode()]
        with patch.object(api,'post_json',side_effect=pages) as post:
            chosen=api.choose_gemini_model('secret','old-unavailable-model',choose=lambda prompt:'models/current-b')
            self.assertEqual(chosen,'current-b')
            self.assertIn('pageToken=next%20page',post.call_args.args[0])
        with patch.object(api,'list_gemini_models',return_value=['current-a']):
            with self.assertRaises(api.APIReviewError):
                api.choose_gemini_model('secret','',choose=lambda prompt:'not-in-list')

    def test_gemini_wrong_protocol_and_invalid_model_fail_before_request(self):
        with self.assertRaisesRegex(api.APIReviewError,'wrong API format'):
            api.request_spec('responses','https://generativelanguage.googleapis.com','gemini-1.5-flash','x')
        with self.assertRaises(api.APIReviewError):
            api.request_spec('gemini',api.GEMINI_BASE,'model?key=secret','x')
        with self.assertRaises(api.APIReviewError):
            api.request_spec('gemini','https://other.example/v1','model','x')

    def test_gemini_incomplete_blocked_and_thoughts(self):
        for payload in ({'promptFeedback':{'blockReason':'SAFETY'}},
                        {'candidates':[{'finishReason':'MAX_TOKENS'}]}):
            with self.assertRaises(api.APIReviewError):api.response_text(payload,'gemini')
        payload={'candidates':[{'finishReason':'STOP','content':{'parts':[
            {'thought':True,'text':'internal'}, {'text':'{"reviews":[]}'}]}}]}
        self.assertEqual(api.response_text(payload,'gemini'),'{"reviews":[]}')

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
