import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills/ezone/scripts'
sys.path.insert(0,str(SCRIPTS))


class RepoTests(unittest.TestCase):
    def run_cli(self, argv):
        import ezone
        out=io.StringIO()
        with patch.dict(os.environ,{'EZONE_TOKEN':'test-token'}), patch('ezone.Client.request',return_value={'ok':True}) as request, contextlib.redirect_stdout(out):
            code=ezone.main(['--host','https://example.test','--repo','org/project','--json']+argv)
        self.assertEqual(code,0)
        self.assertEqual(json.loads(out.getvalue()),{'ok':True})
        return request.call_args

    def test_reads(self):
        for args,path in [(['repo','view'],''),(['repo','rules'],'/settings/branch_protection'),(['repo','release-template'],'/settings/release_template'),(['branch','view','feature/a'],'/branches/feature%2Fa'),(['commit','view','abc'],'/commits/abc')]:
            with self.subTest(args=args):
                call=self.run_cli(args)
                self.assertEqual(call.args,('GET','/v1/code/v2/repos/org%2Fproject'+path))

    def test_branch_create_explicit_base(self):
        call=self.run_cli(['branch','create','new','--from','main','--ref-type','BRANCH'])
        self.assertEqual(call.args,('POST','/v1/code/v2/repos/org%2Fproject/branches'))
        self.assertEqual(call.kwargs['body'],{'name':'new','refName':'main','refType':'BRANCH'})
        import ezone
        with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit) as cm:
            ezone.main(['branch','create','new'])
        self.assertEqual(cm.exception.code,2)

    def test_lists_single_page(self):
        for resource,suffix in [('repo',''),('branch','/org%2Fproject/branches'),('commit','/org%2Fproject/commits')]:
            call=self.run_cli([resource,'list'])
            self.assertEqual(call.args,('GET','/v1/code/v2/repos'+suffix))
            self.assertEqual(call.kwargs['query'],{'offset':0,'limit':100} if resource=='commit' else {'pageNumber':1,'pageSize':100})

    def test_compare(self):
        call=self.run_cli(['repo','compare','--src','main','--dest','new'])
        self.assertEqual(call.kwargs['query'],{'srcRef':'main','destRef':'new'})

    def test_api_explicit(self):
        call=self.run_cli(['api','GET','/v2/repos','--query','pageSize=5'])
        self.assertEqual(call.kwargs['query'],{'pageSize':'5'})

    def test_download_requires_output_before_request(self):
        import ezone
        with patch('ezone.Client.request') as request, contextlib.redirect_stderr(io.StringIO()):
            code=ezone.main(['--host','https://example.test','api','GET','/x','--response','bytes'])
        self.assertEqual(code,2)
        request.assert_not_called()

    def test_download_does_not_overwrite(self):
        import ezone
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'asset'
            target.write_bytes(b'old')
            with patch('ezone.Client.request',return_value=b'new'),contextlib.redirect_stderr(io.StringIO()):
                code=ezone.main(['--host','https://example.test','api','GET','/x','--response','bytes','--output',str(target)])
            self.assertEqual(code,2)
            self.assertEqual(target.read_bytes(),b'old')

    def test_help_version_independent_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            for args in [['--help'],['--version'],['doctor']]:
                p=subprocess.run([sys.executable,str(SCRIPTS/'ezone.py')]+args,cwd=directory,text=True,capture_output=True,env={k:v for k,v in os.environ.items() if not k.startswith('EZONE_')})
                self.assertEqual(p.returncode,0,p.stderr)
                self.assertTrue(p.stdout)

    @unittest.skipUnless(os.name == 'posix', 'requires POSIX file-size limit')
    def test_download_close_failure_cleans_only_new_output(self):
        script = '''import contextlib, io, json, resource, signal, sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, sys.argv[1])
import ezone
resource.setrlimit(resource.RLIMIT_FSIZE, (128, 128))
signal.signal(signal.SIGXFSZ, signal.SIG_IGN)
target = Path(sys.argv[2])
args = ['api', 'GET', '/x', '--response', 'bytes'] if sys.argv[3] == 'api' else ['artifact', 'download', '8', '--format', 'raw']
with patch('urllib.request.OpenerDirector.open', return_value=io.BytesIO(b'x' * 1024)):
    code = ezone.main(['--host', 'https://example.test', '--company', 'acme', *args, '--output', str(target)])
print(json.dumps({'code': code, 'exists': target.exists()}))
'''
        with tempfile.TemporaryDirectory() as directory:
            for mode in ['api', 'artifact']:
                with self.subTest(mode=mode):
                    target = Path(directory) / mode
                    result = subprocess.run([sys.executable, '-c', script, str(SCRIPTS), str(target), mode],
                                            text=True, capture_output=True,
                                            env={**os.environ, 'EZONE_TOKEN': 'fixture-token'})
                    self.assertEqual(result.returncode, 0, result.stderr)
                    data = json.loads(result.stdout)
                    self.assertEqual(data['code'], 2)
                    self.assertFalse(data['exists'], result.stderr)


if __name__ == '__main__': unittest.main()
