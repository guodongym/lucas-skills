"""流水线、代码标签版本说明和 raw 通用制品命令。"""
import argparse
from pathlib import Path
import re
import sys
from urllib.parse import quote

from ezone_client import EzoneError, read_body, repo_path, write_download

PIPELINES = '/v1/pipeline/pipelines'
ARTIFACTS = '/v1/package/api/artifact'


def _company(client):
    if not client.company or not client.company.strip():
        raise EzoneError('此接口需要 --company 或 EZONE_COMPANY', 2)


def _paged(client, args, path, query):
    if args.paginate:
        return client.paginate(path, query={**query, 'pageNumber': args.page}, page_size=args.page_size)
    print('当前输出为单页；使用 --paginate 获取全部', file=sys.stderr)
    return client.request('GET', path, query={**query, 'pageNumber': args.page, 'pageSize': args.page_size})


def _pipeline(client, args):
    _company(client)
    if args.action == 'list':
        return _paged(client, args, PIPELINES, {'repoName': args.repo_name})
    return client.request('GET', PIPELINES + '/' + str(args.pipeline))


def _run(client, args):
    _company(client)
    path = PIPELINES + '/' + str(args.pipeline)
    if args.action == 'list':
        return _paged(client, args, path + '/builds', {'repoName': args.repo_name})
    if args.action == 'start':
        if args.ref_type == 'COMMIT':
            _commit(args.ref)
        return client.request('POST', path + '/manual', body={'externalName': args.ref, 'scmTriggerType': args.ref_type})
    if args.action == 'log':
        # log_download 是无包装文本端点；logs 则明确定义业务 JSON 包装。
        return client.request('GET', path + '/jobs/' + str(args.job) + '/log_download', response='text')
    path += '/builds/' + str(args.record)
    suffix = '' if args.action == 'view' else '/' + args.action
    return client.request('POST' if args.action == 'cancel' else 'GET', path + suffix)


def _commit(value):
    if not re.fullmatch(r'[0-9a-fA-F]{40}|[0-9a-fA-F]{64}', value):
        raise EzoneError('提交基准必须是完整提交 SHA（40 或 64 位十六进制），不能使用分支或标签', 2)


def _release(client, args):
    path = repo_path(client.repo, 'tags')
    if args.action == 'list':
        return _paged(client, args, path, {})
    if args.action == 'upload':
        return client.upload(path + '/' + str(args.tag_id) + '/upload', {}, args.file, file_field='files')
    if args.action == 'view':
        return client.request('GET', path + '/' + quote(args.name, safe=''), query={'tagQueryTypes': ['ALL']})
    body = {'releaseNote': read_body(args.body, args.body_file), 'atMembers': args.at or []}
    if args.action == 'edit':
        return client.request('PUT', path + '/' + quote(args.name, safe=''), body=body)
    _commit(args.commit)
    body.update({'name': args.name, 'commitId': args.commit, 'refName': args.commit, 'refType': 'COMMIT', 'attachmentIds': args.attachment, 'noteAttachmentIds': args.note_attachment})
    if args.message is not None:
        body['message'] = args.message
    return client.request('POST', path, body=body)


def _artifact(client, args):
    _company(client)
    if args.action == 'list':
        return _paged(client, args, ARTIFACTS, {'pkgId': args.package})
    if args.action == 'view':
        return client.request('GET', ARTIFACTS + '/simpleInfo', query={'artifactId': args.artifact, 'format': args.format})
    if args.action == 'release':
        return client.request('POST', ARTIFACTS + '/release', query={'artId': args.artifact, 'format': args.format, 'releaseVersion': args.version})
    if args.action == 'upload':
        exists = client.request('GET', ARTIFACTS + '/isExist', query={'pkgId': args.package, 'format': args.format, 'version': args.version})
        if exists is not False:
            raise EzoneError('制品版本已存在，或存在状态未知；拒绝上传覆盖', 1)
        print('已确认版本不存在；若存在并发上传仍需平台禁止覆盖规则保护', file=sys.stderr)
        return client.upload(ARTIFACTS + '/upload', {}, args.file, query={'pkgId': args.package, 'version': args.version})
    target = Path(args.output)
    if target.exists() or target.is_symlink():
        raise EzoneError('下载路径已存在，不覆盖已有文件', 2)
    data = client.request('GET', ARTIFACTS + '/download', query={'artifactId': args.artifact, 'format': args.format}, response='bytes')
    write_download(target, data)
    return {'output': args.output, 'bytes': len(data), 'responseMode': 'bytes', 'verification': '已保存原生下载响应；请核验制品内容或校验和'}


def _positive(value):
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError('ID 必须是正整数') from None
    if number < 1:
        raise argparse.ArgumentTypeError('ID 必须是正整数')
    return number


def _pages(parser):
    parser.add_argument('--paginate', action='store_true')
    parser.add_argument('--page', type=int, default=1)
    parser.add_argument('--page-size', type=int, default=100)


def _notes(parser):
    body = parser.add_mutually_exclusive_group(required=True)
    body.add_argument('--body')
    body.add_argument('--body-file', help='UTF-8 文件，- 读取标准输入')
    at = parser.add_mutually_exclusive_group(required=True)
    at.add_argument('--at', action='append', help='通知成员，可重复；请求成功不代表通知送达')
    at.add_argument('--no-notify', action='store_true', help='显式使用空 atMembers')


def add_commands(subparsers):
    actions = subparsers.add_parser('pipeline').add_subparsers(dest='action', required=True)
    listing = actions.add_parser('list', help='默认单页，--paginate 获取全部')
    listing.add_argument('--repo-name', required=True, help='流水线服务 repoName，不能由 repoKey 猜测')
    _pages(listing)
    listing.set_defaults(handler=_pipeline)
    view = actions.add_parser('view')
    view.add_argument('pipeline', type=_positive)
    view.set_defaults(handler=_pipeline)

    actions = subparsers.add_parser('run').add_subparsers(dest='action', required=True)
    for action in ('list', 'view', 'start', 'jobs', 'log', 'cancel', 'artifacts'):
        parser = actions.add_parser(action, help='启动仅提交异步请求，使用 view 回读状态' if action == 'start' else None)
        parser.add_argument('--pipeline', required=True, type=_positive)
        parser.set_defaults(handler=_run)
        if action == 'list':
            parser.add_argument('--repo-name', required=True)
            _pages(parser)
        elif action == 'start':
            parser.add_argument('--ref', required=True)
            parser.add_argument('--ref-type', required=True, choices=('COMMIT', 'TAG', 'BRANCH'))
        elif action == 'log':
            parser.add_argument('--job', required=True, type=_positive)
        else:
            parser.add_argument('record', type=_positive)

    actions = subparsers.add_parser('release', help='代码标签与版本说明，不等同于产品版本或制品发布').add_subparsers(dest='action', required=True)
    for action in ('list', 'view', 'create', 'edit', 'upload'):
        parser = actions.add_parser(action)
        parser.set_defaults(handler=_release)
        if action == 'list':
            _pages(parser)
        elif action == 'upload':
            parser.add_argument('tag_id', type=_positive, help='标签 ID，先通过 list/view 查询')
            parser.add_argument('--file', required=True)
        else:
            parser.add_argument('name')
            if action in ('create', 'edit'):
                _notes(parser)
            if action == 'create':
                parser.add_argument('--commit', required=True, help='完整且固定的提交 SHA')
                parser.add_argument('--message')
                parser.add_argument('--attachment', type=_positive, action='append', default=[])
                parser.add_argument('--note-attachment', type=_positive, action='append', default=[])

    actions = subparsers.add_parser('artifact', help='仅 raw 通用制品；其他包协议使用原生工具').add_subparsers(dest='action', required=True)
    for action in ('list', 'view', 'upload', 'download', 'release'):
        parser = actions.add_parser(action)
        parser.set_defaults(handler=_artifact)
        parser.add_argument('--format', required=True, choices=('raw',))
        if action in ('list', 'upload'):
            parser.add_argument('--package', required=True, type=_positive, help='制品包 pkgId')
        else:
            parser.add_argument('artifact', type=_positive, help='制品版本 artifactId')
        if action == 'list':
            _pages(parser)
        elif action == 'upload':
            parser.add_argument('--file', required=True)
            parser.add_argument('--version', required=True)
        elif action == 'release':
            parser.add_argument('--version', required=True, help='目标 releaseVersion，发布后使用 view 回读验证')
        elif action == 'download':
            parser.add_argument('--output', required=True, help='明确输出路径，不覆盖；下载后核验内容及校验和')
