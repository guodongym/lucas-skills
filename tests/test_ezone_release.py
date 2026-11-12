import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/ezone/scripts'))
import ezone
from ezone_client import Client, EzoneError


class ReleaseTests(unittest.TestCase):
    def call(self, *words, results=None, error=None, company='acme'):
        client = Mock(repo='repo/key', company=company)
        client.request.side_effect = error or results
        client.request.return_value = {'status': 'RUNNING'}
        client.upload.return_value = {'id': 9}
        client.paginate.return_value = []
        with patch.object(ezone, 'Client', return_value=client), contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()) as err:
            code = ezone.main(['--host', 'https://example.test', '--repo', 'repo/key', *words])
        return code, client, out.getvalue(), err.getvalue()

    def test_pipeline_list_and_view(self):
        code, c, _, _ = self.call('pipeline', 'list', '--repo-name', 'Team/repo')
        self.assertEqual(code, 0)
        c.request.assert_called_once_with('GET', '/v1/pipeline/pipelines', query={'repoName': 'Team/repo', 'pageNumber': 1, 'pageSize': 100})
        _, c, _, _ = self.call('pipeline', 'view', '12')
        c.request.assert_called_once_with('GET', '/v1/pipeline/pipelines/12')

    def test_run_lists_paginate(self):
        _, c, _, _ = self.call('run', 'list', '--repo-name', 'Team/repo', '--pipeline', '12', '--paginate')
        c.paginate.assert_called_once_with('/v1/pipeline/pipelines/12/builds', query={'repoName': 'Team/repo', 'pageNumber': 1}, page_size=100)

    def test_run_start_preserves_async_response_and_explicit_baseline(self):
        code, c, out, _ = self.call('run', 'start', '--pipeline', '12', '--ref-type', 'COMMIT', '--ref', 'a' * 40)
        self.assertEqual(code, 0)
        c.request.assert_called_once_with('POST', '/v1/pipeline/pipelines/12/manual', body={'externalName': 'a' * 40, 'scmTriggerType': 'COMMIT'})
        self.assertEqual(json.loads(out), {'status': 'RUNNING'})

    def test_run_read_jobs_artifacts_cancel(self):
        for action, suffix, method in [('view', '', 'GET'), ('jobs', '/jobs', 'GET'), ('artifacts', '/artifacts', 'GET'), ('cancel', '/cancel', 'POST')]:
            with self.subTest(action=action):
                _, c, _, _ = self.call('run', action, '34', '--pipeline', '12')
                c.request.assert_called_once_with(method, '/v1/pipeline/pipelines/12/builds/34' + suffix)

    def test_logs_use_defined_text_download_endpoint(self):
        _, c, out, _ = self.call('run', 'log', '--pipeline', '12', '--job', '56', results=['line1\nline2'])
        c.request.assert_called_once_with('GET', '/v1/pipeline/pipelines/12/jobs/56/log_download', response='text')
        self.assertEqual(json.loads(out), 'line1\nline2')

    def test_company_required_before_pipeline_request(self):
        code, c, _, _ = self.call('pipeline', 'view', '12', company=None)
        self.assertEqual(code, 2)
        c.request.assert_not_called()

    def test_release_create_fixed_sha_and_notification_and_attachment_mapping(self):
        _, c, _, _ = self.call('release', 'create', 'v1', '--commit', 'b' * 40, '--body', 'notes', '--at', 'alice', '--attachment', '5', '--note-attachment', '6')
        c.request.assert_called_once_with('POST', '/v1/code/v2/repos/repo%2Fkey/tags', body={'name': 'v1', 'commitId': 'b' * 40, 'refName': 'b' * 40, 'refType': 'COMMIT', 'releaseNote': 'notes', 'atMembers': ['alice'], 'attachmentIds': [5], 'noteAttachmentIds': [6]})

    def test_release_rejects_branch_as_commit(self):
        code, c, _, _ = self.call('release', 'create', 'v1', '--commit', 'main', '--body', 'notes', '--no-notify')
        self.assertEqual(code, 2)
        c.request.assert_not_called()

    def test_release_view_edit_upload(self):
        _, c, _, _ = self.call('release', 'view', 'release/v1')
        c.request.assert_called_once_with('GET', '/v1/code/v2/repos/repo%2Fkey/tags/release%2Fv1', query={'tagQueryTypes': ['ALL']})
        _, c, _, _ = self.call('release', 'edit', 'release/v1', '--body', 'new', '--no-notify')
        c.request.assert_called_once_with('PUT', '/v1/code/v2/repos/repo%2Fkey/tags/release%2Fv1', body={'releaseNote': 'new', 'atMembers': []})
        _, c, _, _ = self.call('release', 'upload', '22', '--file', '/tmp/example.zip')
        c.upload.assert_called_once_with('/v1/code/v2/repos/repo%2Fkey/tags/22/upload', {}, '/tmp/example.zip', file_field='files')

    def test_artifact_list_view_and_release_parameters(self):
        _, c, _, _ = self.call('artifact', 'list', '--package', '7', '--format', 'raw')
        c.request.assert_called_once_with('GET', '/v1/package/api/artifact', query={'pkgId': 7, 'pageNumber': 1, 'pageSize': 100})
        _, c, _, _ = self.call('artifact', 'view', '8', '--format', 'raw')
        c.request.assert_called_once_with('GET', '/v1/package/api/artifact/simpleInfo', query={'artifactId': 8, 'format': 'raw'})
        _, c, _, _ = self.call('artifact', 'release', '8', '--format', 'raw', '--version', '1.0')
        c.request.assert_called_once_with('POST', '/v1/package/api/artifact/release', query={'artId': 8, 'format': 'raw', 'releaseVersion': '1.0'})

    def test_artifact_upload_checks_existence_then_query_not_form(self):
        code, c, _, _ = self.call('artifact', 'upload', '--package', '7', '--format', 'raw', '--version', '1.0', '--file', '/tmp/file', results=[False])
        self.assertEqual(code, 0)
        c.request.assert_called_once_with('GET', '/v1/package/api/artifact/isExist', query={'pkgId': 7, 'format': 'raw', 'version': '1.0'})
        c.upload.assert_called_once_with('/v1/package/api/artifact/upload', {}, '/tmp/file', query={'pkgId': 7, 'version': '1.0'})

    def test_artifact_upload_refuses_existing_or_unknown_existence(self):
        for exists in (True, {}, None):
            code, c, _, _ = self.call('artifact', 'upload', '--package', '7', '--format', 'raw', '--version', '1.0', '--file', '/tmp/file', results=[exists])
            self.assertEqual(code, 1)
            c.upload.assert_not_called()

    def test_download_failure_does_not_overwrite_or_leave_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'output'
            code, _, _, _ = self.call('artifact', 'download', '8', '--format', 'raw', '--output', str(target), error=EzoneError('transport', 3))
            self.assertEqual(code, 3)
            self.assertFalse(target.exists())
            target.write_bytes(b'old')
            code, c, _, _ = self.call('artifact', 'download', '8', '--format', 'raw', '--output', str(target), results=[b'new'])
            self.assertEqual(code, 2)
            self.assertEqual(target.read_bytes(), b'old')
            c.request.assert_not_called()

    def test_download_bytes_and_mapping(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'output'
            code, c, _, _ = self.call('artifact', 'download', '8', '--format', 'raw', '--output', str(target), results=[b'file'])
            self.assertEqual(code, 0)
            self.assertEqual(target.read_bytes(), b'file')
            c.request.assert_called_once_with('GET', '/v1/package/api/artifact/download', query={'artifactId': 8, 'format': 'raw'}, response='bytes')

    def test_business_failure_and_unknown_write_status_propagate(self):
        for error in (EzoneError('business failure', 1), EzoneError('写入结果未知，先回读', 5)):
            code, c, _, _ = self.call('run', 'cancel', '34', '--pipeline', '12', error=error)
            self.assertEqual(code, error.exit_code)
            self.assertEqual(c.request.call_count, 1)

    def test_upload_extension_streams_and_preserves_query_response(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'big'
            source.write_bytes(b'x' * 200000)
            client = Client('https://example.test')
            def request(method, path, **kwargs):
                self.assertEqual(kwargs['query'], {'pkgId': 7})
                self.assertEqual(kwargs['response'], 'text')
                chunks = list(kwargs['body'])
                self.assertLessEqual(max(map(len, chunks[1:-1])), 65536)
                self.assertEqual(sum(map(len, chunks)), kwargs['body'].length)
                return 'accepted'
            with patch.object(client, 'request', side_effect=request):
                self.assertEqual(client.upload('/upload', {}, source, query={'pkgId': 7}, response='text'), 'accepted')


if __name__ == '__main__':
    unittest.main()
