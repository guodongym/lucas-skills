"""Ezone 标准库 HTTP 边界与共享输入帮助函数。"""
from http.client import HTTPException
import json
import os
from pathlib import Path
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener
import uuid


from ezone_config import EzoneError, canonical_host, validate_token


def redact(message, token=None):
    message = str(message)
    if token:
        message = message.replace(token, '[REDACTED]')
    return re.sub(r'(?i)(access_token|authorization|token)([\s"\x27:=]+)[^\s,"\x27&}]+', r'\1\2[REDACTED]', message)


def repo_path(repo, suffix=''):
    if not repo or not repo.strip():
        raise EzoneError('请使用 --repo 或 EZONE_REPO 指定 repoKey', 2)
    return '/v1/code/v2/repos/' + quote(repo, safe='') + ('/' + suffix.lstrip('/') if suffix else '')


def read_body(text=None, file_path=None):
    if text is not None and file_path is not None:
        raise EzoneError('正文和正文文件不能同时提供', 2)
    if file_path is None:
        return text
    try:
        return sys.stdin.read() if file_path == '-' else Path(file_path).read_text(encoding='utf-8')
    except (OSError, UnicodeError) as exc:
        raise EzoneError('无法读取输入文件: ' + str(exc), 2) from None


def read_json(file_path):
    try:
        return json.loads(read_body(file_path=file_path))
    except (ValueError, TypeError):
        raise EzoneError('输入必须是有效 JSON', 2) from None


def write_download(file_path, data):
    target = Path(file_path)
    created = False
    try:
        with target.open('xb') as output:
            created = True
            output.write(data)
    except OSError as exc:
        if created:
            try:
                target.unlink()
            except OSError:
                raise EzoneError('下载写入失败且无法清理本次输出，请检查输出路径与目录权限', 2) from None
        raise EzoneError('无法写入下载文件（不覆盖已有文件）: ' + str(exc), 2) from None


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # 所有重定向均拒绝，避免凭据和写入被隐式转发。
        return None


class Client:
    def __init__(self, host=None, repo=None, company=None, token=None):
        self.host = canonical_host(host or os.environ.get('EZONE_HOST', ''))
        self.repo = repo or os.environ.get('EZONE_REPO')
        self.company = company or os.environ.get('EZONE_COMPANY')
        if self.company:
            try:
                self.company.encode('latin-1')
            except UnicodeEncodeError:
                raise EzoneError('企业标识不能编码为 HTTP 请求头；请填写平台企业标识而非中文显示名称', 2) from None
        self.token = token
        self.opener = build_opener(NoRedirect())

    def request(self, method, path, *, query=None, body=None, response='json', write=None):
        method = method.upper()
        if method not in ('GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD'):
            raise EzoneError('不支持的 HTTP 方法', 2)
        if response not in ('json', 'text', 'bytes'):
            raise EzoneError('不支持的响应模式', 2)
        if not path.startswith('/') or path.startswith('//') or '?' in path or '#' in path or '\\' in path or any(c.isspace() for c in path):
            raise EzoneError('API 路径必须是同源绝对路径，查询参数使用 --query', 2)
        if any(str(k).lower() in ('access_token', 'token', 'authorization') for k in (query or {})):
            raise EzoneError('令牌只能来自个人凭据或 EZONE_TOKEN', 2)
        token = self.token if self.token is not None else os.environ.get('EZONE_TOKEN')
        if not token:
            raise EzoneError('缺少个人令牌，请执行 auth login 或通过受信任环境设置 EZONE_TOKEN', 4)
        validate_token(token)
        if self.company and any(c in self.company for c in '\r\n'):
            raise EzoneError('认证或企业请求头无效', 2)
        headers = {'access_token': token, 'Accept': 'application/json' if response == 'json' else '*/*'}
        if self.company:
            headers['x-company-name'] = self.company
        if isinstance(body, _Multipart):
            headers.update({'Content-Type': body.content_type, 'Content-Length': str(body.length)})
            data = body
        elif body is not None:
            try:
                data = json.dumps(body, ensure_ascii=False, allow_nan=False).encode('utf-8')
            except (ValueError, TypeError):
                raise EzoneError('请求体必须是可序列化的 JSON', 2) from None
            headers['Content-Type'] = 'application/json'
        else:
            data = None
        url = self.host + path + ('?' + urlencode(query, doseq=True) if query else '')
        request = Request(url, data=data, headers=headers, method=method)
        is_write = method not in ('GET', 'HEAD') if write is None else write
        try:
            with self.opener.open(request, timeout=30) as result:
                raw = result.read()
        except HTTPError as exc:
            if is_write and 500 <= exc.code < 600:
                raise EzoneError(f'HTTP {exc.code}: 写入结果未知，先回读后决定是否重试', 5) from None
            code = 4 if exc.code == 401 else 6 if exc.code == 403 else 1
            raise EzoneError(f'HTTP {exc.code}（重定向不会跟随）' if 300 <= exc.code < 400 else f'HTTP {exc.code}', code) from None
        except (URLError, OSError, HTTPException) as exc:
            message = '写入结果未知，先回读后决定是否重试' if is_write else '只读请求传输失败'
            raise EzoneError(message + ': ' + redact(exc, token), 5 if is_write else 3) from None
        if response == 'bytes':
            return raw
        try:
            text = raw.decode('utf-8')
            if response == 'text':
                return text
            value = json.loads(text)
        except (UnicodeError, ValueError):
            raise EzoneError('响应不是有效 UTF-8 JSON；无法确认业务结果', 5 if is_write else 1) from None
        if not isinstance(value, dict) or type(value.get('code')) is not int:
            raise EzoneError('未知业务响应包装；无法确认业务结果', 5 if is_write else 1)
        if value['code'] != 0:
            message = value.get('message', value.get('msg', '业务失败'))
            raise EzoneError(f"业务 code={value['code']}: {redact(message, token)}", 4 if value['code'] == 1000 else 1)
        return value.get('data')

    def paginate(self, path, *, query=None, style='page', page_size=100):
        if style not in ('page', 'offset') or type(page_size) is not int or page_size < 1:
            raise EzoneError('分页参数无效', 2)
        params = dict(query or {})
        index_key, size_key, start = ('pageNumber', 'pageSize', 1) if style == 'page' else ('offset', 'limit', 0)
        index = params.get(index_key, start)
        if type(index) is not int or index < start:
            raise EzoneError('分页起点无效', 2)
        items, seen = [], set()
        while True:
            params.update({index_key: index, size_key: page_size})
            data = self.request('GET', path, query=dict(params))
            page = data if isinstance(data, list) else data.get('list') if isinstance(data, dict) else None
            if not isinstance(page, list):
                raise EzoneError('未知分页结构；未返回不完整结果', 1)
            total = data.get('total') if isinstance(data, dict) else None
            if total is not None and (type(total) is not int or total < 0):
                raise EzoneError('未知分页 total；未返回不完整结果', 1)
            fingerprint = json.dumps(page, sort_keys=True, ensure_ascii=False)
            if page and fingerprint in seen:
                raise EzoneError('重复分页；未返回不完整结果', 1)
            seen.add(fingerprint)
            items.extend(page)
            consumed = (index - 1) * page_size + len(page) if style == 'page' else index + len(page)
            if total is not None and consumed >= total:
                return items
            if len(page) < page_size:
                if total is not None and consumed < total:
                    raise EzoneError('分页提前结束，total 尚未满足', 1)
                return items
            index += 1 if style == 'page' else page_size

    def upload(self, path, fields, file_path, *, file_field='file', query=None, response='json'):
        try:
            with open(file_path, 'rb') as source:
                return self.request('POST', path, query=query, body=_Multipart(fields, source, file_field), response=response, write=True)
        except OSError as exc:
            raise EzoneError('无法读取上传文件: ' + str(exc), 2) from None


class _Multipart:
    def __init__(self, fields, source, file_field):
        boundary = uuid.uuid4().hex
        self.source = source
        self.content_type = 'multipart/form-data; boundary=' + boundary
        parts = []
        for name, value in fields.items():
            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{quote(str(name), safe="")}"\r\n\r\n{value}\r\n'.encode())
        filename = quote(Path(source.name).name, safe='')
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{quote(file_field, safe="")}"; filename="{filename}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode())
        self.prefix = b''.join(parts)
        self.suffix = f'\r\n--{boundary}--\r\n'.encode()
        self.length = len(self.prefix) + os.fstat(source.fileno()).st_size + len(self.suffix)

    def __iter__(self):
        yield self.prefix
        while chunk := self.source.read(65536):
            yield chunk
        yield self.suffix
