#!/usr/bin/env python3
"""可独立分发的 Ezone 命令行入口。全局选项放在资源命令之前。"""
import argparse
import getpass
import json
import os
import sys
import warnings
from urllib.parse import quote

import ezone_pr
import ezone_release

from ezone_client import Client, EzoneError, read_json, redact, repo_path, write_download
from ezone_config import canonical_host, context, credentials_path, load_token, remove_token, save_token, validate_token

VERSION = '0.2.0'
REF_TYPES = ('BRANCH', 'DCR_BRANCH', 'MR_BRANCH', 'PM_BRANCH', 'TAG', 'COMMIT')


def _repo_read(client, args):
    suffix = args.suffix
    if hasattr(args, 'ref'):
        suffix += '/' + quote(args.ref, safe='')
    return client.request('GET', repo_path(client.repo, suffix))


def _list(client, args):
    path = '/v1/code/v2/repos' if args.resource == 'repo' else repo_path(client.repo, args.resource + ('es' if args.resource == 'branch' else 's'))
    if args.paginate:
        query = {'offset': args.offset} if args.style == 'offset' else {'pageNumber': args.page}
        return client.paginate(path, query=query, style=args.style, page_size=args.page_size)
    print('当前输出为单页；使用 --paginate 获取全部', file=sys.stderr)
    query = {'offset': args.offset, 'limit': args.page_size} if args.style == 'offset' else {'pageNumber': args.page, 'pageSize': args.page_size}
    return client.request('GET', path, query=query)


def _compare(client, args):
    query = {'srcRef': args.src, 'destRef': args.dest}
    if args.src_type:
        query['srcRefType'] = args.src_type
    if args.dest_type:
        query['destRefType'] = args.dest_type
    return client.request('GET', repo_path(client.repo, 'compare'), query=query)


def _branch_create(client, args):
    return client.request('POST', repo_path(client.repo, 'branches'), body={'name': args.name, 'refName': args.base, 'refType': args.ref_type})


def _api(client, args):
    if args.response == 'bytes' and not args.output:
        raise EzoneError('bytes 响应必须提供 --output', 2)
    query = {}
    for entry in args.query:
        key, sep, value = entry.partition('=')
        if not sep or not key:
            raise EzoneError('--query 必须使用 KEY=VALUE', 2)
        if key in query:
            if not isinstance(query[key], list):
                query[key] = [query[key]]
            query[key].append(value)
        else:
            query[key] = value
    result = client.request(args.method, args.path, query=query, body=read_json(args.input) if args.input else None, response=args.response)
    if args.response == 'bytes':
        write_download(args.output, result)
        return {'output': args.output, 'bytes': len(result)}
    return result


def _auth(client, args):
    client.request('GET', '/v1/code/v2/repos', query={'pageNumber': 1, 'pageSize': 1})
    return {'authenticated': True, 'probe': 'repo list', 'scope': '仅该认证探测成功，不能证明全部权限'}


def _login(settings, args):
    host = canonical_host(settings['host'])
    if not sys.stdin.isatty():
        raise EzoneError('auth login 需要交互终端隐藏输入；自动化请使用受信任环境的 EZONE_TOKEN', 2)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', getpass.GetPassWarning)
            token = getpass.getpass(f'Ezone {host} 个人访问令牌（隐藏输入）: ')
    except (EOFError, KeyboardInterrupt):
        raise EzoneError('已取消登录，个人凭据未修改', 2) from None
    except getpass.GetPassWarning:
        raise EzoneError('终端无法保证隐藏输入；请换用交互终端或受信任环境的 EZONE_TOKEN', 2) from None
    validate_token(token)
    client = Client(host, settings['repo'], settings['company'], token=token)
    result = _auth(client, args)
    save_token(host, token)
    return {**result, 'host': host, 'credentials_file': str(credentials_path()),
            'environment_token_present': bool(os.environ.get('EZONE_TOKEN')),
            'notice': '已保存本机凭据；非空 EZONE_TOKEN 会优先于保存的凭据'}


def add_commands(subparsers):
    for resource in ('repo', 'branch', 'commit'):
        root = subparsers.add_parser(resource)
        actions = root.add_subparsers(dest='action', required=True)
        listing = actions.add_parser('list', help='默认单页，--paginate 获取全部')
        listing.add_argument('--paginate', action='store_true')
        listing.add_argument('--page-size', type=int, default=100)
        listing.add_argument('--page', type=int, default=1)
        listing.add_argument('--offset', type=int, default=0)
        listing.set_defaults(handler=_list, style='offset' if resource == 'commit' else 'page')
        view = actions.add_parser('view')
        if resource != 'repo':
            view.add_argument('ref')
        view.set_defaults(handler=_repo_read, suffix='' if resource == 'repo' else 'branches' if resource == 'branch' else 'commits')
        if resource in ('repo', 'commit'):
            compare = actions.add_parser('compare', help='引用比较原始结果')
            compare.add_argument('--src', required=True)
            compare.add_argument('--dest', required=True)
            compare.add_argument('--src-type', choices=REF_TYPES)
            compare.add_argument('--dest-type', choices=REF_TYPES)
            compare.set_defaults(handler=_compare)
        if resource == 'repo':
            for action, suffix in [('rules', 'settings/branch_protection'), ('release-template', 'settings/release_template')]:
                actions.add_parser(action).set_defaults(handler=_repo_read, suffix=suffix)
        if resource == 'branch':
            create = actions.add_parser('create')
            create.add_argument('name')
            create.add_argument('--from', dest='base', required=True)
            create.add_argument('--ref-type', required=True, choices=REF_TYPES)
            create.set_defaults(handler=_branch_create)
    auth = subparsers.add_parser('auth').add_subparsers(dest='action', required=True)
    auth.add_parser('status').set_defaults(handler=_auth)
    auth.add_parser('login', help='交互式隐藏输入并验证后保存个人令牌').set_defaults(handler=None)
    auth.add_parser('logout', help='仅删除当前平台的本机凭据，不撤销远端令牌').set_defaults(handler=None)
    api = subparsers.add_parser('api', help='显式请求单个端点，不自动分页')
    api.add_argument('method', choices=('GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD'))
    api.add_argument('path')
    api.add_argument('--query', action='append', default=[])
    api.add_argument('--input')
    api.add_argument('--response', choices=('json', 'text', 'bytes'), default='json')
    api.add_argument('--output')
    api.set_defaults(handler=_api)
    subparsers.add_parser('doctor').set_defaults(handler=None)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', action='version', version=VERSION)
    parser.add_argument('--host')
    parser.add_argument('--repo')
    parser.add_argument('--company')
    parser.add_argument('--json', action='store_true')
    subparsers = parser.add_subparsers(dest='resource', required=True)
    add_commands(subparsers)
    ezone_pr.add_commands(subparsers)
    ezone_release.add_commands(subparsers)
    args = parser.parse_args(argv)
    token = None
    try:
        settings = context(args.host, args.repo, args.company)
        if args.resource == 'auth' and args.action == 'login':
            result = _login(settings, args)
        elif args.resource == 'auth' and args.action == 'logout':
            result = {'host': canonical_host(settings['host']), 'removed': remove_token(settings['host']),
                      'environment_token_present': bool(os.environ.get('EZONE_TOKEN')),
                      'notice': '仅移除当前平台的本机凭据；远端令牌未撤销，EZONE_TOKEN 环境变量未清除'}
        else:
            token, source = load_token(settings['host'], explicit_host=args.host)
            if args.resource == 'doctor':
                result = {'python': sys.version.split()[0], 'token_present': bool(token), 'token_source': source,
                          'host_configured': bool(settings['host']), 'repo_configured': bool(settings['repo']),
                          'host': settings['host'], 'repo': settings['repo'], 'company': settings['company'],
                          'project_config': settings['project_config'], 'credentials_file': str(credentials_path())}
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return 0
            if hasattr(args, 'page_size') and (args.page_size < 1 or getattr(args, 'page', 1) < 1 or getattr(args, 'offset', 0) < 0):
                raise EzoneError('分页参数必须为正数（offset 可为 0）', 2)
            client = Client(settings['host'], settings['repo'], settings['company'], token=token)
            result = args.handler(client, args)
            if args.resource == 'auth':
                result['token_source'] = source
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except EzoneError as exc:
        print(redact(redact(str(exc), token), os.environ.get('EZONE_TOKEN')), file=sys.stderr)
        return exc.exit_code


if __name__ == '__main__':
    raise SystemExit(main())
