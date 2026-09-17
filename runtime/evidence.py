"""E1 verifier. Hash integrity is not a business-outcome or content-quality check."""
from __future__ import annotations
from pathlib import Path
from hashlib import sha256
from datetime import datetime, timezone
from typing import Any
from kernel.validation import ProtocolError
MAX_FILE_BYTES = 16 * 1024 * 1024

def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()

def scoped_file(path: str | Path, root: str | Path) -> Path:
    base = Path(root).expanduser().resolve(strict=True)
    target = Path(path).expanduser().resolve(strict=True)
    if not base.is_dir() or not target.is_file() or not target.is_relative_to(base):
        raise ProtocolError('File must be inside the explicitly allowed root.')
    if target.stat().st_size > MAX_FILE_BYTES:
        raise ProtocolError('E1 file verification is limited to 16 MiB per file.')
    return target

def file_digest(path: str | Path, root: str | Path) -> tuple[Path, str]:
    target = scoped_file(path, root)
    # Recheck after open; reject symlink escapes that can be detected by resolving again.
    with target.open('rb') as stream:
        data = stream.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise ProtocolError('File grew beyond the permitted size.')
    if scoped_file(path, root) != target:
        raise ProtocolError('File target changed during verification.')
    return target, sha256(data).hexdigest()

def check(criterion: dict[str, Any], evidence: dict[str, Any], run: dict[str, Any], now: datetime | None = None) -> tuple[bool,str]:
    now = now or datetime.now(timezone.utc)
    if evidence['run_id'] != run['run_id'] or evidence['contract_id'] != run['contract_id'] or evidence['contract_version'] != run['contract_version']:
        return False, '证据属于其他任务或旧版完成标准。'
    if evidence['criterion_id'] != criterion['criterion_id']:
        return False, '证据未绑定当前完成条件。'
    if evidence['simulated'] != bool(run['simulated']):
        return False, '模拟证据与真实任务不能混用。'
    if evidence['revoked_at']:
        return False, '证据已撤销。'
    if evidence['type'] not in criterion['accepted_types']:
        return False, '证据种类不满足完成条件。'
    captured = datetime.fromisoformat(evidence['captured_at'])
    if captured.tzinfo is None:
        return False, '证据时间缺少时区。'
    age = (now-captured).total_seconds()
    if age < -5:
        return False, '证据时间处于未来。'
    if criterion['max_age_seconds'] is not None and age > criterion['max_age_seconds']:
        return False, '证据已超过有效期。'
    if criterion['verification'] != 'local_artifact_sha256':
        return False, '此条件需要人工或外部核验器；本地参考实现不代签通过。'
    if evidence['level'] != 'E1' or criterion['minimum_level'] != 'E1' or evidence['source'] != 'local_verifier' or evidence['checked_by'] != 'g-local-sha256-v1':
        return False, '缺少本地核验器出具的 E1 文件记录。'
    if not evidence['uri'] or not evidence['scope_root']:
        return False, '缺少文件或授权范围。'
    try:
        _, digest = file_digest(evidence['uri'], evidence['scope_root'])
    except (OSError, ValueError) as exc:
        return False, f'文件不可核验：{type(exc).__name__}'
    if digest != evidence['content_sha256']:
        return False, '文件内容已变化，请重新提交对应版本。'
    return True, '已确认指定文件存在且内容与登记哈希一致；未判断内容质量。'
