"""Safe, actionable failure messages without exposing provider error text."""

DETAILS = {
    'incomplete': 'The download is incomplete: the provider could not supply enough data. Review availability and repair results in the client before choosing another release.',
    'repair': 'The client could not repair the downloaded files. Review its repair results before choosing another release.',
    'password': 'The archive needs a password. Review the release information and client settings.',
    'storage': 'The client reports insufficient disk space. Free space in its download and temporary folders before retrying.',
    'unpack': 'The client could not unpack the download. Review archive integrity and extraction settings.',
}


def sab_failure_code(message):
    """Classify known diagnostic phrases; never return the original string."""
    text = str(message or '').casefold()
    for code, phrases in (
        ('storage', ('no space left', 'not enough disk space', 'disk full')),
        ('password', ('password required', 'password protected', 'wrong password')),
        ('incomplete', ('cannot be completed', 'not enough articles', 'missing articles', 'not enough repair blocks')),
        ('repair', ('repair failed', 'repairing failed')),
        ('unpack', ('unpack failed', 'unpacking failed', 'extraction failed')),
    ):
        if any(phrase in text for phrase in phrases):
            return code
    return ''
