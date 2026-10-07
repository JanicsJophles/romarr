"""Non-secret download identities and conservative legacy correlation."""
import base64
import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlsplit


@dataclass(frozen=True)
class HandoffReceipt:
    accepted: bool
    job_id: str = ""


def safe_job_id(value):
    """Client IDs are opaque tokens, never arbitrary URLs or diagnostic text."""
    return value if isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_-]{1,128}', value) else ''


def magnet_job_id(url):
    parsed = urlsplit(url)
    if parsed.scheme.lower() != 'magnet':
        return ''
    hashes = set()
    for xt in parse_qs(parsed.query).get('xt', []):
        if not xt.lower().startswith('urn:btih:'):
            continue
        value = xt[9:]
        if re.fullmatch(r'[a-fA-F0-9]{40}', value):
            hashes.add(value.lower())
        elif re.fullmatch(r'[a-zA-Z2-7]{32}', value):
            hashes.add(base64.b32decode(value.upper()).hex())
    return next(iter(hashes)) if len(hashes) == 1 else ''


def matches_job(job_id, client, title, report):
    """IDs override titles. A missing/mismatched ID must never become a match."""
    if client and report.get('client') != client:
        return False
    if job_id:
        return job_id == report.get('job_id')
    return bool(title) and title.casefold() == str(report.get('release', report.get('name', ''))).casefold()
