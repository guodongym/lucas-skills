import contextlib
import io
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
from urllib.error import URLError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/ezone/scripts'))
import ezone


class Response(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *args): self.close()


class PrTests(unittest.TestCase):
    def run_cli(self, args, responses=None, stdin=''):
        self.requests = []
        responses = iter(responses if responses is not None else [{'accepted': True}])
        def open_request(opener, request, timeout):
            self.requests.append(request)
            value = next(responses)
            if isinstance(value, Exception): raise value
            return Response(json.dumps({'code': 0, 'data': value}).encode())
        out, err = io.StringIO(), io.StringIO()
        with patch.dict(os.environ, {'EZONE_TOKEN': 'fixture-token'}):
            with patch('urllib.request.OpenerDirector.open', open_request), patch('sys.stdin', io.StringIO(stdin)), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                try:
                    code = ezone.main(['--host', 'https://example.test', '--repo', 'org/a b', '--json', 'pr'] + args)
                except SystemExit as exc:
                    code = exc.code
        return code, json.loads(out.getvalue()) if out.getvalue() else None, err.getvalue()

    def body(self): return json.loads(self.requests[-1].data)
    def query(self): return parse_qs(urlsplit(self.requests[-1].full_url).query)

    def test_read_routes(self):
        for action, suffix in [('view', ''), ('changes', '/changes'), ('pushes', '/pushes'), ('comments', '/comments'), ('reviews', '/votes'), ('pipelines', '/pipelines')]:
            with self.subTest(action=action):
                code, result, _ = self.run_cli([action, '7'])
                self.assertEqual(code, 0)
                self.assertTrue(self.requests[-1].full_url.endswith('/org%2Fa%20b/reviews/7' + suffix))
        self.assertEqual(self.run_cli(['checks', '7'], [None])[:2], (0, None))
        self.assertTrue(self.requests[-1].full_url.endswith('/review_gate/7'))

    def test_list_and_reviewers_paging(self):
        self.assertEqual(self.run_cli(['list', '--status', 'ONGOING', '--page', '2'])[0], 0)
        self.assertEqual(self.query(), {'pageNumber': ['2'], 'pageSize': ['100'], 'status': ['ONGOING']})
        self.assertEqual(self.run_cli(['reviewers', '7', '--paginate', '--page-size', '2'], [[1, 2], [3]])[:2], (0, [1, 2, 3]))
        self.assertEqual(self.query()['reviewSeq'], ['7'])

    def test_commits_over_fifty(self):
        code, data, _ = self.run_cli(['commits', '7', '--paginate', '--page-size', '50'], [list(range(50)), list(range(50, 65))])
        self.assertEqual(code, 0)
        self.assertEqual(len(data), 65)
        self.assertEqual(self.query(), {'offset': ['50'], 'limit': ['50']})

    def test_create_and_edit(self):
        self.assertEqual(self.run_cli(['create', '--src', 'feature/a', '--dest', 'main', '--title', '主题', '--reviewer', 'alice'])[0], 0)
        self.assertEqual(self.body(), {'srcBranch': 'feature/a', 'destBranch': 'main', 'subject': '主题', 'notifyReviewers': ['alice']})
        self.assertEqual(self.run_cli(['edit', '7', '--status', 'ABANDONED', '--title', 'new'])[0], 0)
        self.assertEqual(self.body(), {'status': 'ABANDONED', 'subject': 'new'})
        self.assertEqual(self.run_cli(['edit', '7', '--status', 'MERGED'])[0], 2)
        self.assertEqual(self.run_cli(['edit', '7'])[0], 2)

    def test_comment_multiline_and_mentions(self):
        self.assertEqual(self.run_cli(['comment', '7', '--path', '目录/a b.py', '--line', '3', '--commit', 'abc', '--body-file', '-', '--at', 'alice'], stdin='first\nsecond\n')[0], 0)
        self.assertEqual(self.body(), {'message': 'first\nsecond\n', 'path': '目录/a b.py', 'lineNum': 3, 'commitId': 'abc', 'atMembers': ['alice']})
        self.assertNotIn('side', self.body())

    def test_reply_types_and_resolve(self):
        parent = {'id': '12', 'commitId': 'old-commit', 'path': 'old/name.py', 'lineNum': 4}
        self.assertEqual(self.run_cli(['reply', '7', '--comment-id', '12', '--body', 'line'], [[parent], {'accepted': True}])[0], 0)
        self.assertEqual(self.body(), {'parentCommentId': 12, 'message': 'line', 'commitId': 'old-commit', 'path': 'old/name.py', 'lineNum': 4, 'reviewSeq': 7})
        self.assertEqual([r.method for r in self.requests], ['GET', 'POST'])
        self.assertTrue(self.requests[-1].full_url.endswith('/comments'))
        self.assertEqual(self.run_cli(['reply', '7', '--vote-id', '13', '--parent-reply-id', '14', '--body', 'general', '--at', 'bob'])[0], 0)
        self.assertEqual(self.body(), {'voteId': 13, 'parentReplyId': 14, 'message': 'general', 'atMembers': ['bob']})
        self.assertTrue(self.requests[-1].full_url.endswith('/vote_replies'))
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(self.run_cli(['resolve', '7', '12'])[0], 0)
        self.assertEqual(self.body(), {'resolved': True})
        self.assertEqual(self.requests[-1].method, 'PUT')
        self.assertEqual(self.run_cli(['resolve', '7', '12', '--unresolve'])[0], 0)
        self.assertEqual(self.body(), {'resolved': False})
        self.assertEqual(self.run_cli(['reply', '7', '--comment-id', '12', '--parent-reply-id', '14', '--body', 'x'])[0], 2)

    def test_line_reply_requires_same_pr_valid_anchor(self):
        valid = {'id': 12, 'commitId': 'previous-push-commit', 'path': '目录/old.py', 'lineNum': 9}
        invalid = [[], [{'id': 99, 'commitId': 'abc', 'path': 'a', 'lineNum': 1}], {'list': [valid]}]
        invalid += [[{**valid, field: value}] for field, value in [('commitId', None), ('path', ''), ('lineNum', 0), ('lineNum', True), ('lineNum', '9'), ('id', '012')]]
        for comments in invalid:
            with self.subTest(comments=comments):
                code, _, err = self.run_cli(['reply', '7', '--comment-id', '12', '--body', 'x'], [comments])
                self.assertEqual(code, 1)
                self.assertEqual([r.method for r in self.requests], ['GET'])
                self.assertTrue(err)

    def test_review_notify_retrigger_merge(self):
        for vote in ['APPROVAL', 'NEUTRAL', 'REJECTION']:
            self.assertEqual(self.run_cli(['review', '7', '--result', vote, '--commit', 'abc', '--body', 'text'])[0], 0)
            self.assertEqual(self.body(), {'result': vote, 'commitId': 'abc', 'message': 'text'})
        self.assertEqual(self.run_cli(['notify', '7', '--reviewer', 'alice', '--type', 'USER'])[0], 0)
        self.assertEqual(self.body(), {'reviewSeq': 7, 'reviewer': 'alice', 'type': 'USER'})
        self.assertEqual(self.run_cli(['retrigger', '7', '--build-id', '33'])[0], 0)
        self.assertEqual(self.query(), {'buildId': ['33']})
        self.assertEqual(self.run_cli(['merge', '7', '--mode', 'CREATE_MERGE_COMMIT', '--title', 'merge', '--body-file', '-'], stdin='full\nmessage\n')[0], 0)
        self.assertEqual(self.body(), {'reviewSeq': 7, 'type': 'REVIEW_MERGE', 'deleteSrcRef': False, 'mode': 'CREATE_MERGE_COMMIT', 'title': 'merge', 'message': 'full\nmessage\n'})
        self.assertTrue(self.requests[-1].full_url.endswith('/merge'))

    def test_missing_diff_refs_and_invalid_paging(self):
        self.assertEqual(self.run_cli(['diff', '7'])[0], 2)
        self.assertFalse(self.requests)
        self.assertEqual(self.run_cli(['commits', '7', '--offset', '-1'])[0], 2)
        self.assertFalse(self.requests)

    def test_complete_diff_and_unknown_stat(self):
        import base64
        refs = ['--src', 'a/b', '--src-type', 'COMMIT', '--dest', 'main', '--dest-type', 'BRANCH']
        files = [{'path': 'added.txt', 'changeType': 'ADD'}, {'path': '目录/deleted.py', 'changeType': 'DELETE'}, {'path': 'new name', 'oldPath': 'old name', 'changeType': 'RENAME'}]
        stat = {'fileDiffs': files, 'hasAnyMore': False, 'total': '93'}
        code, data, _ = self.run_cli(['diff', '7'] + refs, [stat] + [base64.b64encode(('diff ' + f['path']).encode()).decode() for f in files])
        self.assertEqual(code, 0)
        self.assertEqual(data['stat'], stat)
        self.assertEqual([d['diff'] for d in data['files']], ['diff ' + f['path'] for f in files])
        self.assertEqual(data['files'][2]['stat']['oldPath'], 'old name')
        self.assertEqual(len(self.requests), 4)
        self.assertIn('/diffs/stat?', self.requests[0].full_url)
        self.assertEqual(self.query()['path'], ['new name'])
        for bad in [{'fileDiffs': files, 'hasAnyMore': True}, {'list': files}, {'fileDiffs': [{'wrong': 'path'}], 'hasAnyMore': False}]:
            self.assertEqual(self.run_cli(['diff', '7'] + refs, [bad])[0], 1)
            self.assertEqual(len(self.requests), 1)
        self.assertEqual(self.run_cli(['diff', '7'] + refs, [{'fileDiffs': files[:1], 'hasAnyMore': False}, 'not base64'])[0], 1)

    def test_required_inputs_and_blank_body_fail_before_http(self):
        for args in [
            ['merge', '7', '--mode', 'FAST_FORWARD', '--title', 'x'],
            ['merge', '7', '--title', 'x', '--body', 'x'],
            ['reviewers'],
            ['comment', '7', '--path', 'a', '--line', '0', '--commit', 'abc', '--body', 'x'],
            ['review', '7', '--result', 'NEUTRAL', '--body', '  '],
            ['review', '7', '--result', 'APPROVAL', '--body', 'a', '--body-file', '-'],
            ['reply', '7', '--body', 'x'],
        ]:
            with self.subTest(args=args):
                self.assertEqual(self.run_cli(args)[0], 2)
                self.assertFalse(self.requests)

    def test_business_failure_is_not_success(self):
        out, err = io.StringIO(), io.StringIO()
        def fail(opener, request, timeout):
            return Response(b'{"code":1,"message":"gate blocked"}')
        with patch.dict(os.environ, {'EZONE_TOKEN': 'fixture-token'}), patch('urllib.request.OpenerDirector.open', fail), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = ezone.main(['--host', 'https://example.test', '--repo', 'r', 'pr', 'merge', '7', '--mode', 'FAST_FORWARD', '--title', 'x', '--body', 'x'])
        self.assertEqual(code, 1)
        self.assertFalse(out.getvalue())
        self.assertIn('gate blocked', err.getvalue())

    def test_unknown_write_no_retry(self):
        code, _, err = self.run_cli(['review', '7', '--result', 'NEUTRAL', '--body', 'x'], [URLError('timeout')])
        self.assertEqual(code, 5)
        self.assertEqual(len(self.requests), 1)
        self.assertIn('结果未知', err)


if __name__ == '__main__': unittest.main()
