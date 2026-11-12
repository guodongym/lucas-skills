"""PR 资源命令；只传递显式决定，不自动批准、合并或修改门禁。"""
import base64
import binascii
import sys

from ezone_client import EzoneError, read_body, repo_path

REF_TYPES = ('BRANCH', 'DCR_BRANCH', 'MR_BRANCH', 'PM_BRANCH', 'TAG', 'COMMIT')
MERGE_MODES = ('FAST_FORWARD', 'CREATE_MERGE_COMMIT', 'CREATE_MERGE_COMMIT_IF_NECESSARY', 'REBASE_SOURCE_BRANCH_COMMITS', 'REBASE_SOURCE_BRANCH_COMMITS_AND_NO_FF', 'SQUASH_SOURCE_BRANCH_COMMITS', 'CHERRY_PICK_SOURCE_BRANCH_COMMITS')


def _path(client, args, suffix=''):
    return repo_path(client.repo, 'reviews/' + str(args.seq) + ('/' + suffix if suffix else ''))


def _read(client, args):
    if args.action == 'checks':
        return client.request('GET', repo_path(client.repo, 'review_gate/' + str(args.seq)))
    return client.request('GET', _path(client, args, args.suffix))


def _list(client, args):
    query = {}
    if args.action == 'reviewers':
        path = repo_path(client.repo, 'reviewers')
        query['reviewSeq'] = args.seq
    elif args.action == 'commits':
        path = _path(client, args, 'commits')
    else:
        path = repo_path(client.repo, 'reviews')
        if args.status:
            query['status'] = args.status
    offset = args.action == 'commits'
    query.update({'offset': args.offset} if offset else {'pageNumber': args.page})
    if args.paginate:
        return client.paginate(path, query=query, style='offset' if offset else 'page', page_size=args.page_size)
    query['limit' if offset else 'pageSize'] = args.page_size
    print('当前输出为单页；使用 --paginate 获取全部', file=sys.stderr)
    return client.request('GET', path, query=query)


def _write(client, args):
    action = args.action
    body = {}
    method, path = 'POST', _path(client, args) if hasattr(args, 'seq') else repo_path(client.repo, 'reviews')
    if action == 'create':
        body = {'srcBranch': args.src, 'destBranch': args.dest, 'subject': args.title}
        if args.reviewer:
            body['notifyReviewers'] = args.reviewer
    elif action == 'edit':
        method = 'PUT'
        if args.title is not None:
            body['subject'] = args.title
        if args.status:
            body['status'] = args.status
        if not body:
            raise EzoneError('edit 至少提供 --title 或 --status', 2)
    elif action == 'notify':
        path = repo_path(client.repo, 'reviewers/notify')
        body = {'reviewSeq': args.seq, 'reviewer': args.reviewer, 'type': args.type}
    elif action == 'resolve':
        method, path = 'PUT', _path(client, args, 'comments/' + str(args.comment_id))
        body = {'resolved': not args.unresolve}
    elif action == 'retrigger':
        return client.request('POST', _path(client, args, 'pipelines/re_trigger'), query={'buildId': args.build_id})
    else:
        message = read_body(args.body, args.body_file)
        if not message or not message.strip():
            raise EzoneError('正文不能为空', 2)
        body['message'] = message
        if action == 'merge':
            path = repo_path(client.repo, 'merge')
            body.update({'reviewSeq': args.seq, 'type': 'REVIEW_MERGE', 'deleteSrcRef': False, 'mode': args.mode, 'title': args.title})
        else:
            if args.at:
                body['atMembers'] = args.at
            if action == 'review':
                path = _path(client, args, 'votes')
                body['result'] = args.result
                if args.commit:
                    body['commitId'] = args.commit
            elif action == 'comment':
                path = _path(client, args, 'comments')
                body.update({'path': args.path, 'lineNum': args.line, 'commitId': args.commit})
                if args.push_id is not None:
                    body['pushId'] = args.push_id
            elif action == 'reply':
                if args.vote_id is not None:
                    path = _path(client, args, 'vote_replies')
                    body['voteId'] = args.vote_id
                    if args.parent_reply_id is not None:
                        body['parentReplyId'] = args.parent_reply_id
                else:
                    if args.parent_reply_id is not None:
                        raise EzoneError('--parent-reply-id 只用于总评回复 --vote-id', 2)
                    path = _path(client, args, 'comments')
                    comments = client.request('GET', path)
                    if not isinstance(comments, list):
                        raise EzoneError('未知评论列表结构；未发送回复', 1)
                    parents = [item for item in comments if isinstance(item, dict) and str(item.get('id')) == str(args.comment_id)]
                    if len(parents) != 1:
                        raise EzoneError('当前 PR 未找到唯一父评论；未发送回复', 1)
                    parent = parents[0]
                    if (not isinstance(parent.get('commitId'), str) or not parent['commitId'].strip()
                            or not isinstance(parent.get('path'), str) or not parent['path'].strip()
                            or type(parent.get('lineNum')) is not int or parent['lineNum'] < 1):
                        raise EzoneError('父评论缺少有效 commitId/path/lineNum；未发送回复', 1)
                    # 旧提交上的线程仍沿用原评论锚点，不能替换为当前 PR 最新提交。
                    body.update({key: parent[key] for key in ('commitId', 'path', 'lineNum')})
                    body.update({'parentCommentId': args.comment_id, 'reviewSeq': args.seq})
    return client.request(method, path, body=body)


def _diff(client, args):
    query = {'srcRef': args.src, 'srcRefType': args.src_type, 'destRef': args.dest, 'destRefType': args.dest_type}
    stat = client.request('GET', repo_path(client.repo, 'diffs/stat'), query=query)
    if not isinstance(stat, dict) or not isinstance(stat.get('fileDiffs'), list) or stat.get('hasAnyMore') is not False:
        raise EzoneError('未知或不完整 diff stat；无法确认全部文件（该端点未定义分页参数）', 1)
    files = stat['fileDiffs']
    if any(not isinstance(item, dict) or not isinstance(item.get('path'), str) or not item['path'] for item in files):
        raise EzoneError('diff stat 缺少文件 path；无法确认全部文件', 1)
    diffs = []
    for item in files:
        data = client.request('GET', repo_path(client.repo, 'diffs'), query={**query, 'path': item['path']})
        try:
            decoded = base64.b64decode(data, validate=True).decode('utf-8') if isinstance(data, str) else None
        except (ValueError, binascii.Error, UnicodeError):
            decoded = None
        if decoded is None:
            raise EzoneError('未知文件 diff 格式；需要 base64 编码的 UTF-8，未输出不完整结果', 1)
        diffs.append({'stat': item, 'diff': decoded})
    return {'reviewSeq': args.seq, 'refs': query, 'stat': stat, 'files': diffs}


def _positive(value):
    import argparse
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError('必须为正整数') from None
    if number < 1:
        raise argparse.ArgumentTypeError('必须为正整数')
    return number


def _body_options(parser, mentions=True):
    body = parser.add_mutually_exclusive_group(required=True)
    body.add_argument('--body')
    body.add_argument('--body-file', help='UTF-8 正文文件；- 读取标准输入')
    if mentions:
        parser.add_argument('--at', action='append', default=[], help='atMembers 成员，可重复')


def add_commands(subparsers):
    root = subparsers.add_parser('pr', help='PR 资源命令；输出服务事实，不自动判断门禁或流水线通过')
    actions = root.add_subparsers(dest='action', required=True)
    for action in ('list', 'commits', 'reviewers'):
        parser = actions.add_parser(action, help='默认单页；--paginate 获取全部')
        if action != 'list':
            parser.add_argument('seq', type=_positive)
        else:
            parser.add_argument('--status', choices=('ONGOING', 'MERGED', 'ABANDONED'))
        parser.add_argument('--paginate', action='store_true')
        parser.add_argument('--page-size', type=int, default=100)
        parser.add_argument('--offset', type=int, default=0) if action == 'commits' else parser.add_argument('--page', type=int, default=1)
        parser.set_defaults(handler=_list)
    for action, suffix in [('view', ''), ('changes', 'changes'), ('pushes', 'pushes'), ('comments', 'comments'), ('reviews', 'votes'), ('checks', ''), ('pipelines', 'pipelines')]:
        parser = actions.add_parser(action)
        parser.add_argument('seq', type=_positive)
        parser.set_defaults(handler=_read, suffix=suffix)
    parser = actions.add_parser('diff', help='完整差异：显式引用应来自当前PR事实；先stat，再逐文件读取')
    parser.add_argument('seq', type=_positive)
    for ref in ('src', 'dest'):
        parser.add_argument('--' + ref, required=True)
        parser.add_argument('--' + ref + '-type', required=True, choices=REF_TYPES)
    parser.set_defaults(handler=_diff)
    for action in ('create', 'edit', 'comment', 'reply', 'resolve', 'review', 'notify', 'retrigger', 'merge'):
        parser = actions.add_parser(action, help='仅通知进行中评审；成功只表示API接受，不保证送达' if action == 'notify' else None)
        if action != 'create':
            parser.add_argument('seq', type=_positive)
        parser.set_defaults(handler=_write)
        if action == 'create':
            parser.add_argument('--src', required=True)
            parser.add_argument('--dest', required=True)
            parser.add_argument('--title', required=True)
            parser.add_argument('--reviewer', action='append', default=[])
        elif action == 'edit':
            parser.add_argument('--title')
            parser.add_argument('--status', choices=('ONGOING', 'ABANDONED'), help='ONGOING 重开；ABANDONED 关闭；合并请用 merge')
        elif action == 'resolve':
            parser.add_argument('comment_id', type=_positive)
            parser.add_argument('--unresolve', action='store_true')
        elif action == 'notify':
            parser.add_argument('--reviewer', required=True)
            parser.add_argument('--type', required=True, choices=('USER', 'GROUP', 'COMPANY_ROLE', 'LEADER'))
        elif action == 'retrigger':
            parser.add_argument('--build-id', required=True, type=_positive)
        else:
            _body_options(parser, mentions=action != 'merge')
            if action == 'comment':
                parser.add_argument('--path', required=True)
                parser.add_argument('--line', required=True, type=_positive)
                parser.add_argument('--commit', required=True)
                parser.add_argument('--push-id', type=_positive)
            elif action == 'reply':
                target = parser.add_mutually_exclusive_group(required=True)
                target.add_argument('--comment-id', type=_positive, help='行间回复，使用 parentCommentId')
                target.add_argument('--vote-id', type=_positive, help='总评回复，使用 vote_replies')
                parser.add_argument('--parent-reply-id', type=_positive)
            elif action == 'review':
                parser.add_argument('--result', required=True, choices=('APPROVAL', 'NEUTRAL', 'REJECTION'))
                parser.add_argument('--commit')
            elif action == 'merge':
                parser.add_argument('--mode', required=True, choices=MERGE_MODES)
                parser.add_argument('--title', required=True)
