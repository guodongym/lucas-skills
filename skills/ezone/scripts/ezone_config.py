"""项目非机密上下文与按 HTTPS origin 隔离的本机个人凭据。"""
import json
import os
from pathlib import Path
import stat
import tempfile
from urllib.parse import urlsplit


class EzoneError(Exception):
    def __init__(self, message, exit_code=1):
        super().__init__(message)
        self.exit_code = exit_code


def canonical_host(host):
    try:
        origin = urlsplit(host)
        if (not isinstance(host, str) or any(c.isspace() for c in host)
                or origin.scheme != 'https' or not origin.hostname
                or origin.username is not None or origin.password is not None
                or origin.path not in ('', '/') or origin.query or origin.fragment
                or origin.port == 0):
            raise ValueError()
        hostname = origin.hostname.lower()
        if ':' in hostname:
            hostname = '[' + hostname + ']'
        port = ':' + str(origin.port) if origin.port not in (None, 443) else ''
        return 'https://' + hostname + port
    except (ValueError, TypeError, AttributeError):
        raise EzoneError('请使用 --host、EZONE_HOST 或 .ezone.json 指定 HTTPS origin（无路径、凭据、查询参数）', 2) from None


def project_config():
    cwd = Path.cwd()
    ancestors = [cwd, *cwd.parents]
    boundary = next((folder for folder in ancestors if (folder / '.git').exists()), cwd)
    for folder in ancestors:
        path = folder / '.ezone.json'
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
            except (OSError, UnicodeError, ValueError):
                raise EzoneError('无法读取 .ezone.json；请检查文件权限和 JSON 格式', 2) from None
            if (not isinstance(data, dict) or set(data) - {'host', 'repo', 'company'}
                    or any(not isinstance(value, str) or not value.strip() for value in data.values())):
                raise EzoneError('.ezone.json 只接受非空字符串 host、repo、company；令牌不得写入项目配置', 2)
            if 'host' in data:
                data['host'] = canonical_host(data['host'])
            return data, str(path)
        if folder == boundary:
            break
    return {}, None


def context(host=None, repo=None, company=None):
    data, path = project_config()
    result = {key: explicit or os.environ.get('EZONE_' + key.upper()) or data.get(key)
              for key, explicit in [('host', host), ('repo', repo), ('company', company)]}
    if result['host']:
        result['host'] = canonical_host(result['host'])
    result['project_config'] = path
    return result


def credentials_path():
    return Path.home() / '.config/ezone/credentials.json'


def validate_token(token):
    if not isinstance(token, str) or not token or any(ord(c) < 33 or ord(c) > 126 for c in token):
        raise EzoneError('令牌必须为非空可打印 ASCII，不能包含空白或控制字符', 2)
    return token


def _credentials():
    path = credentials_path()
    if path.is_symlink():
        raise EzoneError('个人凭据文件不能是软链', 2)
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    except FileNotFoundError:
        return {}
    except OSError:
        raise EzoneError('无法读取个人凭据文件，请检查权限', 2) from None
    try:
        with os.fdopen(fd, encoding='utf-8') as source:
            metadata = os.fstat(source.fileno())
            if not stat.S_ISREG(metadata.st_mode):
                raise EzoneError('个人凭据必须是普通文件', 2)
            if os.name == 'posix' and stat.S_IMODE(metadata.st_mode) & 0o077:
                raise EzoneError('个人凭据权限过宽，请设置 chmod 600 ~/.config/ezone/credentials.json', 2)
            value = json.load(source)
    except (OSError, UnicodeError, ValueError):
        raise EzoneError('个人凭据文件不可读取或 JSON 损坏；原文件未修改', 2) from None
    if not isinstance(value, dict) or set(value) != {'hosts'} or not isinstance(value['hosts'], dict):
        raise EzoneError('个人凭据格式错误，应包含 hosts 对象；原文件未修改', 2)
    for host, token in value['hosts'].items():
        if canonical_host(host) != host:
            raise EzoneError('个人凭据的平台地址必须是规范化 HTTPS origin；原文件未修改', 2)
        validate_token(token)
    return value['hosts']


def load_token(host, explicit_host=None):
    token = os.environ.get('EZONE_TOKEN')
    if token:
        trusted_host = explicit_host or os.environ.get('EZONE_HOST')
        if not trusted_host or canonical_host(trusted_host) != canonical_host(host):
            raise EzoneError('使用 EZONE_TOKEN 时须同时设置 EZONE_HOST 或显式 --host；不能仅由项目配置决定令牌发送目标', 2)
        return validate_token(token), 'environment'
    if host:
        token = _credentials().get(canonical_host(host))
        if token:
            return token, 'credentials'
    return None, 'none'


def _write_credentials(hosts):
    path = credentials_path()
    temporary = None
    try:
        path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        # 同目录原子替换，避免写入中断损坏上一次可用凭据。
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as target:
            temporary = Path(target.name)
            if os.name == 'posix':
                os.fchmod(target.fileno(), 0o600)
            json.dump({'hosts': hosts}, target, ensure_ascii=False, indent=2)
            target.write('\n')
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary, path)
    except OSError:
        raise EzoneError('无法保存个人凭据；请检查磁盘和目录权限，原文件未替换', 2) from None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def save_token(host, token):
    host, token = canonical_host(host), validate_token(token)
    hosts = _credentials()
    hosts[host] = token
    _write_credentials(hosts)


def remove_token(host):
    host = canonical_host(host)
    hosts = _credentials()
    if host not in hosts:
        return False
    del hosts[host]
    _write_credentials(hosts)
    return True
