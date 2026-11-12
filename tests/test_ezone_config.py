import contextlib
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills/ezone/scripts'
sys.path.insert(0, str(SCRIPTS))
import ezone


class ConfigAuthTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.home = self.root / 'home'
        self.home.mkdir()
        self.project = self.root / 'project'
        self.project.mkdir()
        (self.project / '.git').mkdir()
        old_cwd = Path.cwd()
        os.chdir(self.project)
        self.addCleanup(os.chdir, old_cwd)
        env = patch.dict(os.environ, {'HOME': str(self.home)}, clear=True)
        env.start()
        self.addCleanup(env.stop)
        self.credentials = self.home / '.config/ezone/credentials.json'

    def project_file(self, value=None, folder=None):
        path = (folder or self.project) / '.ezone.json'
        path.write_text(json.dumps(value if value is not None else {
            'host': 'https://example.test', 'repo': '123', 'company': 'acme'
        }))
        return path

    def saved(self, hosts=None):
        self.credentials.parent.mkdir(parents=True, exist_ok=True)
        self.credentials.write_text(json.dumps({'hosts': hosts or {'https://example.test': 'saved-secret'}}))
        self.credentials.chmod(0o600)

    def cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = ezone.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_project_config_from_subdirectory(self):
        expected = self.project_file()
        nested = self.project / 'src/component'
        nested.mkdir(parents=True)
        os.chdir(nested)
        code, out, err = self.cli('doctor')
        self.assertEqual(code, 0, err)
        data = json.loads(out)
        self.assertTrue(data['host_configured'])
        self.assertTrue(data['repo_configured'])
        self.assertEqual(Path(data['project_config']), expected.resolve())
        self.assertEqual(data['host'], 'https://example.test')
        self.assertEqual(data['repo'], '123')
        self.assertEqual(data['company'], 'acme')

    def test_does_not_cross_git_directory_or_worktree_file(self):
        self.project_file(folder=self.root)
        for git_file in [False, True]:
            git = self.project / '.git'
            if git_file:
                git.rmdir()
                git.write_text('gitdir: /unused/worktree')
            code, out, err = self.cli('doctor')
            self.assertEqual(code, 0, err)
            self.assertFalse(json.loads(out)['host_configured'])

    def test_non_git_directory_only_checks_current_directory(self):
        self.project_file(folder=self.root)
        other = self.root / 'untracked'
        other.mkdir()
        os.chdir(other)
        code, out, err = self.cli('doctor')
        self.assertEqual(code, 0, err)
        self.assertFalse(json.loads(out)['host_configured'])
        self.project_file(folder=other)
        self.assertTrue(json.loads(self.cli('doctor')[1])['host_configured'])

    def test_nearest_project_config_and_override_precedence(self):
        self.project_file()
        nested = self.project / 'src'
        nested.mkdir()
        self.project_file({'host': 'https://nested.test', 'repo': 'nested'}, nested)
        os.chdir(nested)
        with patch.dict(os.environ, {'EZONE_HOST': 'https://environment.test', 'EZONE_REPO': 'env', 'EZONE_TOKEN': 'env-secret'}):
            with patch.object(ezone.Client, 'request', return_value={}) as request:
                self.assertEqual(self.cli('--host', 'https://explicit.test', '--repo', 'flag', 'repo', 'view')[0], 0)
            self.assertEqual(request.call_args.args[1], '/v1/code/v2/repos/flag')
            with patch('urllib.request.OpenerDirector.open', return_value=io.BytesIO(b'{"code":0,"data":{}}')) as op:
                self.assertEqual(self.cli('repo', 'view')[0], 0)
            req = op.call_args.args[0]
            self.assertTrue(req.full_url.startswith('https://environment.test/'))
            self.assertEqual(req.get_header('Access_token'), 'env-secret')

    def test_invalid_project_config_never_echoes_contents(self):
        for value in [{'token': 'private-secret'}, {'repo': 123}, {'host': 'http://bad.test'}, []]:
            self.project_file(value)
            code, out, err = self.cli('doctor')
            self.assertEqual(code, 2, (value, out, err))
            self.assertNotIn('private-secret', out + err)
        (self.project / '.ezone.json').write_text('{"token": "private-secret"')
        self.assertEqual(self.cli('doctor')[0], 2)
        self.assertNotIn('private-secret', ''.join(self.cli('doctor')[1:]))

    def test_saved_token_is_used_in_request_not_output(self):
        self.project_file()
        self.saved()
        with patch('urllib.request.OpenerDirector.open', return_value=io.BytesIO(b'{"code":0,"data":{}}')) as op:
            code, out, err = self.cli('repo', 'view')
        self.assertEqual(code, 0, err)
        req = op.call_args.args[0]
        self.assertEqual(req.get_header('Access_token'), 'saved-secret')
        self.assertNotIn('saved-secret', req.full_url + out + err)

    def test_origin_normalization_and_port_isolation(self):
        self.project_file({'host': 'https://EXAMPLE.test:443/', 'repo': '123'})
        self.saved()
        self.assertEqual(json.loads(self.cli('doctor')[1])['token_source'], 'credentials')
        self.project_file({'host': 'https://example.test:444', 'repo': '123'})
        data = json.loads(self.cli('doctor')[1])
        self.assertFalse(data['token_present'])
        self.assertEqual(data['token_source'], 'none')

    def test_environment_token_wins_without_reading_broken_store(self):
        self.project_file()
        self.saved()
        self.credentials.write_text('broken saved-secret')
        with patch.dict(os.environ, {'EZONE_TOKEN': 'env-secret', 'EZONE_HOST': 'https://example.test'}):
            code, out, err = self.cli('doctor')
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out)['token_source'], 'environment')
        self.assertNotIn('env-secret', out + err)

    def test_missing_auth_explains_login_without_network(self):
        self.project_file()
        with patch('urllib.request.OpenerDirector.open') as op:
            code, out, err = self.cli('auth', 'status')
        self.assertEqual(code, 4)
        self.assertIn('auth login', err)
        op.assert_not_called()

    def test_environment_token_cannot_get_destination_only_from_project(self):
        self.project_file({'host': 'https://other.test', 'repo': '123'})
        with patch.dict(os.environ, {'EZONE_TOKEN': 'env-secret'}), patch('urllib.request.OpenerDirector.open', return_value=io.BytesIO(b'{"code":0,"data":[]}')) as op:
            code, out, err = self.cli('auth', 'status')
        self.assertEqual(code, 2)
        self.assertIn('EZONE_HOST', err)
        self.assertNotIn('env-secret', out + err)
        op.assert_not_called()

    def test_explicit_host_binds_environment_token_in_another_project(self):
        self.project_file({'host': 'https://other.test', 'repo': '123'})
        with patch.dict(os.environ, {'EZONE_TOKEN': 'env-secret'}), patch('urllib.request.OpenerDirector.open', return_value=io.BytesIO(b'{"code":0,"data":[]}')) as op:
            code, out, err = self.cli('--host', 'https://example.test', 'auth', 'status')
        self.assertEqual(code, 0, err)
        self.assertTrue(op.call_args.args[0].full_url.startswith('https://example.test/'))
        self.assertNotIn('env-secret', out + err)

    def test_login_validates_then_saves_only_current_origin(self):
        self.project_file()
        self.saved({'https://other.test': 'other-secret'})
        with patch('sys.stdin.isatty', return_value=True), patch('getpass.getpass', return_value='new-secret'), patch('urllib.request.OpenerDirector.open', return_value=io.BytesIO(b'{"code":0,"data":[]}')) as op:
            code, out, err = self.cli('auth', 'login')
        self.assertEqual(code, 0, err)
        self.assertEqual(op.call_args.args[0].get_header('Access_token'), 'new-secret')
        self.assertEqual(json.loads(self.credentials.read_text())['hosts'], {'https://other.test': 'other-secret', 'https://example.test': 'new-secret'})
        self.assertNotIn('new-secret', out + err)
        if os.name == 'posix':
            self.assertEqual(stat.S_IMODE(self.credentials.stat().st_mode), 0o600)

    def test_first_login_creates_private_directory_and_persists_across_calls(self):
        self.project_file()
        with patch('sys.stdin.isatty', return_value=True), patch('getpass.getpass', return_value='new-secret'), patch.object(ezone.Client, 'request', return_value=[]):
            self.assertEqual(self.cli('auth', 'login')[0], 0)
        self.assertEqual(json.loads(self.cli('doctor')[1])['token_source'], 'credentials')
        if os.name == 'posix':
            self.assertEqual(stat.S_IMODE(self.credentials.parent.stat().st_mode), 0o700)

    def test_login_rejection_keeps_old_credentials_and_redacts_errors(self):
        self.project_file()
        self.saved()
        before = self.credentials.read_bytes()
        with patch('sys.stdin.isatty', return_value=True), patch('getpass.getpass', return_value='new-secret'), patch('urllib.request.OpenerDirector.open', return_value=io.BytesIO(b'{"code":1000,"message":"new-secret invalid"}')):
            code, out, err = self.cli('auth', 'login')
        self.assertEqual(code, 4)
        self.assertEqual(self.credentials.read_bytes(), before)
        self.assertNotIn('new-secret', out + err)

    def test_noninteractive_login_and_cancel_never_save(self):
        self.project_file()
        with patch('sys.stdin.isatty', return_value=False), patch('getpass.getpass') as prompt:
            self.assertEqual(self.cli('auth', 'login')[0], 2)
            prompt.assert_not_called()
        for exception in [EOFError, KeyboardInterrupt]:
            with patch('sys.stdin.isatty', return_value=True), patch('getpass.getpass', side_effect=exception):
                self.assertEqual(self.cli('auth', 'login')[0], 2)
        self.assertFalse(self.credentials.exists())

    def test_login_refuses_getpass_echo_fallback(self):
        import getpass
        import warnings
        self.project_file()
        def unsafe_prompt(*args):
            warnings.warn('Cannot control echo on the terminal.', getpass.GetPassWarning)
            return 'must-not-be-saved'
        with patch('sys.stdin.isatty', return_value=True), patch('getpass.getpass', side_effect=unsafe_prompt), patch.object(ezone.Client, 'request') as request:
            code, out, err = self.cli('auth', 'login')
        self.assertEqual(code, 2)
        request.assert_not_called()
        self.assertFalse(self.credentials.exists())

    def test_blank_or_multiline_token_is_rejected_before_network(self):
        self.project_file()
        for token in ['  ', 'bad\nheader', 'bad\rheader']:
            with patch.dict(os.environ, {'EZONE_TOKEN': token, 'EZONE_HOST': 'https://example.test'}), patch('urllib.request.OpenerDirector.open') as op:
                code, out, err = self.cli('auth', 'status')
            self.assertEqual(code, 2)
            op.assert_not_called()

    def test_company_display_name_is_controlled_input_error(self):
        self.project_file({'host': 'https://example.test', 'repo': '123', 'company': '企业'})
        from http.client import HTTPConnection
        def encode_headers(opener, request, **kwargs):
            connection = HTTPConnection('example.test')
            connection.putrequest('GET', '/')
            for key, value in request.header_items():
                connection.putheader(key, value)
            return io.BytesIO(b'{"code":0,"data":[]}')
        with patch.dict(os.environ, {'EZONE_TOKEN': 'env-secret', 'EZONE_HOST': 'https://example.test'}), patch('urllib.request.OpenerDirector.open', autospec=True, side_effect=encode_headers):
            code, out, err = self.cli('auth', 'status')
        self.assertEqual(code, 2)
        self.assertIn('企业标识', err)
        self.assertNotIn('env-secret', out + err)

    def test_logout_is_local_preserves_other_hosts_and_reports_environment(self):
        self.project_file()
        self.saved({'https://example.test': 'saved-secret', 'https://other.test': 'other-secret'})
        with patch.dict(os.environ, {'EZONE_TOKEN': 'env-secret'}), patch('urllib.request.OpenerDirector.open') as op:
            code, out, err = self.cli('auth', 'logout')
        self.assertEqual(code, 0, err)
        op.assert_not_called()
        self.assertTrue(json.loads(out)['environment_token_present'])
        self.assertEqual(json.loads(self.credentials.read_text())['hosts'], {'https://other.test': 'other-secret'})
        self.assertEqual(self.cli('auth', 'logout')[0], 0)

    def test_logout_without_store_does_not_create_it(self):
        self.project_file()
        code, out, err = self.cli('auth', 'logout')
        self.assertEqual(code, 0, err)
        self.assertFalse(json.loads(out)['removed'])
        self.assertFalse(self.credentials.exists())

    def test_corrupt_or_insecure_credentials_are_not_overwritten(self):
        self.project_file()
        self.saved()
        for raw in ['broken saved-secret', '{"hosts": []}', '{"hosts":{"http://bad.test":"saved-secret"}}']:
            self.credentials.write_text(raw)
            for action in [('doctor',), ('auth', 'logout')]:
                code, out, err = self.cli(*action)
                self.assertEqual(code, 2, (action, err))
                self.assertNotIn('saved-secret', out + err)
                self.assertEqual(self.credentials.read_text(), raw)
        self.saved()
        if os.name == 'posix':
            self.credentials.chmod(0o644)
            self.assertEqual(self.cli('doctor')[0], 2)

    def test_symlink_credentials_refused_and_target_unchanged(self):
        self.project_file()
        self.saved()
        target = self.root / 'original'
        self.credentials.rename(target)
        self.credentials.symlink_to(target)
        before = target.read_bytes()
        self.assertEqual(self.cli('auth', 'logout')[0], 2)
        self.assertEqual(target.read_bytes(), before)

    def test_atomic_write_failure_keeps_old_store(self):
        self.project_file()
        self.saved()
        before = self.credentials.read_bytes()
        with patch('sys.stdin.isatty', return_value=True), patch('getpass.getpass', return_value='new-secret'), patch.object(ezone.Client, 'request', return_value=[]), patch('os.replace', side_effect=OSError('disk full')):
            code, out, err = self.cli('auth', 'login')
        self.assertEqual(code, 2)
        self.assertEqual(self.credentials.read_bytes(), before)
        self.assertNotIn('new-secret', out + err)
        self.assertEqual(list(self.credentials.parent.iterdir()), [self.credentials])

    def test_saved_token_is_redacted_on_transport_error(self):
        from urllib.error import URLError
        self.project_file()
        self.saved()
        with patch('urllib.request.OpenerDirector.open', side_effect=URLError('saved-secret')):
            code, out, err = self.cli('auth', 'status')
        self.assertEqual(code, 3)
        self.assertNotIn('saved-secret', out + err)


if __name__ == '__main__':
    unittest.main()
