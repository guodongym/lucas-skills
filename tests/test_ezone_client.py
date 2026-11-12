import io
from http.client import IncompleteRead
import json
import os
from pathlib import Path
import ssl
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills/ezone/scripts'
sys.path.insert(0, str(SCRIPTS))


class ClientTests(unittest.TestCase):
    def setUp(self):
        import ezone_client
        self.m = ezone_client
        self.env = patch.dict(os.environ, {'EZONE_TOKEN': 'secret-test-token'})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.client = self.m.Client('https://example.test', repo='org/project')

    def response(self, value):
        return io.BytesIO(json.dumps(value).encode())

    def test_missing_auth(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(self.m.EzoneError) as cm:
                self.m.Client('https://example.test').request('GET', '/v2/repos')
        self.assertEqual(cm.exception.exit_code, 4)

    def test_origin_validation(self):
        for host in ['http://example.test', 'https://u:p@example.test', 'https://example.test/path', 'https://example.test?q=x']:
            with self.subTest(host=host), self.assertRaises(self.m.EzoneError):
                self.m.Client(host)

    def test_success_and_header_only_token(self):
        with patch.object(self.client.opener, 'open', return_value=self.response({'code': 0, 'data': [1]})) as op:
            self.assertEqual(self.client.request('GET', '/v2/repos', query={'pageNumber': 1}), [1])
        req = op.call_args.args[0]
        self.assertEqual(req.get_header('Access_token'), 'secret-test-token')
        self.assertNotIn('secret-test-token', req.full_url)

    def test_business_and_unknown_envelopes(self):
        for value in [{'code':1000,'message':'secret-test-token failed'}, {'code':1}, {'data':[]}, {'code':False,'data':1}, {'code':'0','data':1}]:
            with self.subTest(value=value), patch.object(self.client.opener,'open',return_value=self.response(value)):
                with self.assertRaises(self.m.EzoneError) as cm:
                    self.client.request('GET','/v2/repos')
                self.assertNotIn('secret-test-token', str(cm.exception))
                self.assertEqual(cm.exception.exit_code, 4 if value.get('code') == 1000 else 1)
        with patch.object(self.client.opener,'open',return_value=self.response({'code':1000,'message':'bad'})):
            with self.assertRaises(self.m.EzoneError) as cm:self.client.request('GET','/x')
        self.assertIn('code=1000',str(cm.exception))

    def test_http_auth_permission_and_redirect(self):
        for status, exit_code in [(401,4),(403,6),(302,1),(500,1)]:
            with self.subTest(status=status), patch.object(self.client.opener,'open',side_effect=HTTPError('https://example.test',status,'secret-test-token',{},None)):
                with self.assertRaises(self.m.EzoneError) as cm:
                    self.client.request('GET','/v2/repos')
                self.assertEqual(cm.exception.exit_code,exit_code)
                self.assertNotIn('secret-test-token', str(cm.exception))

    def test_http_write_server_errors_unknown_no_retry(self):
        for status in [500, 502, 503, 504]:
            with self.subTest(status=status), patch.object(self.client.opener, 'open', side_effect=HTTPError('https://example.test', status, 'secret-test-token', {}, None)) as op:
                with self.assertRaises(self.m.EzoneError) as cm:
                    self.client.request('POST', '/v2/repos')
                self.assertEqual(op.call_count, 1)
                self.assertEqual(cm.exception.exit_code, 5)
                self.assertIn(f'HTTP {status}', str(cm.exception))
                self.assertIn('写入结果未知，先回读', str(cm.exception))
                self.assertNotIn('secret-test-token', str(cm.exception))

    def test_http_read_server_error_remains_known_failure(self):
        for method, write in [('GET', None), ('POST', False)]:
            with self.subTest(method=method, write=write), patch.object(self.client.opener, 'open', side_effect=HTTPError('https://example.test', 504, 'secret-test-token', {}, None)) as op:
                with self.assertRaises(self.m.EzoneError) as cm:
                    self.client.request(method, '/v2/repos', write=write)
                self.assertEqual(op.call_count, 1)
                self.assertEqual(cm.exception.exit_code, 1)
                self.assertIn('HTTP 504', str(cm.exception))
                self.assertNotIn('写入结果未知', str(cm.exception))
                self.assertNotIn('secret-test-token', str(cm.exception))

    def test_http_write_rejections_keep_exit_codes(self):
        for status, exit_code in [(401, 4), (403, 6), (400, 1)]:
            with self.subTest(status=status), patch.object(self.client.opener, 'open', side_effect=HTTPError('https://example.test', status, 'secret-test-token', {}, None)) as op:
                with self.assertRaises(self.m.EzoneError) as cm:
                    self.client.request('POST', '/v2/repos')
                self.assertEqual(op.call_count, 1)
                self.assertEqual(cm.exception.exit_code, exit_code)
                self.assertIn(f'HTTP {status}', str(cm.exception))
                self.assertNotIn('写入结果未知', str(cm.exception))
                self.assertNotIn('secret-test-token', str(cm.exception))

    def test_transport_write_unknown_no_retry(self):
        for method, exit_code in [('GET',3),('POST',5)]:
            with patch.object(self.client.opener,'open',side_effect=URLError('secret-test-token')) as op:
                with self.assertRaises(self.m.EzoneError) as cm:
                    self.client.request(method,'/v2/repos')
                self.assertEqual(cm.exception.exit_code,exit_code)
                self.assertEqual(op.call_count,1)
                self.assertNotIn('secret-test-token',str(cm.exception))

    def test_tls_and_redirect_policy(self):
        self.assertIsNone(self.m.NoRedirect().redirect_request(None,None,302,'',{},'https://other.test'))
        with patch.object(self.client.opener,'open',side_effect=ssl.SSLError('certificate failed')):
            with self.assertRaises(self.m.EzoneError) as cm:
                self.client.request('GET','/v2/repos')
        self.assertEqual(cm.exception.exit_code,3)

    def test_invalid_path_and_token_query(self):
        for path, query in [('https://other.test',None),('//other.test',None),('/v2/repos?access_token=x',None),('/v2/repos',{'access_token':'x'})]:
            with self.subTest(path=path),self.assertRaises(self.m.EzoneError):
                self.client.request('GET',path,query=query)

    def test_json_and_file_errors(self):
        for raw in [b'not json', b'{}']:
            with patch.object(self.client.opener,'open',return_value=io.BytesIO(raw)),self.assertRaises(self.m.EzoneError):
                self.client.request('GET','/x')
        with self.assertRaises(self.m.EzoneError):self.m.read_json('/missing/ezone.json')
        with patch('sys.stdin',io.StringIO('{')):
            with self.assertRaises(self.m.EzoneError):self.m.read_json('-')
        with patch('sys.stdin',io.StringIO('hello')):
            self.assertEqual(self.m.read_body(file_path='-'),'hello')
        with self.assertRaises(self.m.EzoneError):self.m.read_body('a','b')

    def test_pagination_page_offset_total(self):
        for style, expected in [('page',{'pageNumber':1,'pageSize':2}),('offset',{'offset':0,'limit':2})]:
            with patch.object(self.client,'request',side_effect=[{'list':[1,2],'total':3},{'list':[3],'total':3}]) as request:
                self.assertEqual(self.client.paginate('/x',style=style,page_size=2),[1,2,3])
                self.assertEqual(request.call_args_list[0].kwargs['query'],expected)

    def test_pagination_repeated_and_unknown(self):
        for pages in [[{'items':[]}],[[1,2],[1,2]]]:
            with patch.object(self.client,'request',side_effect=pages),self.assertRaises(self.m.EzoneError):
                self.client.paginate('/x',page_size=2)

    def test_interrupted_response_is_unknown_for_write(self):
        with patch.object(self.client.opener, 'open', side_effect=IncompleteRead(b'partial', 12)):
            with self.assertRaises(self.m.EzoneError) as cm:
                self.client.request('POST', '/x')
        self.assertEqual(cm.exception.exit_code, 5)

    def test_upload_streamed_and_wrapped(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'hello.bin'
            source.write_bytes(b'x' * 150000)
            def receive(request, timeout):
                chunks = list(request.data)
                self.assertLessEqual(max(map(len, chunks)), 65536)
                payload = b''.join(chunks)
                self.assertIn(b'name="file"', payload)
                self.assertIn(b'name="name"', payload)
                self.assertIn(b'x' * 150000, payload)
                self.assertEqual(int(request.get_header('Content-length')),len(payload))
                return self.response({'code':0,'data':{'id':1}})
            with patch.object(self.client.opener, 'open', side_effect=receive):
                self.assertEqual(self.client.upload('/upload', {'name':'asset'}, source), {'id':1})
        with self.assertRaises(self.m.EzoneError) as cm:
            self.client.upload('/upload',{},'/missing/file')
        self.assertEqual(cm.exception.exit_code,2)

    def test_repo_encoding(self):
        self.assertEqual(self.m.repo_path('org/project','branches/feature%2Fx'),'/v1/code/v2/repos/org%2Fproject/branches/feature%2Fx')
        with self.assertRaises(self.m.EzoneError):self.m.repo_path(None)


if __name__ == '__main__': unittest.main()
