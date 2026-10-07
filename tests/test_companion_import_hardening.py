"""Adversarial filesystem fixtures stay in temp dirs and never fetch real content."""
from types import SimpleNamespace
from unittest.mock import Mock

from romarr import library
from romarr.downloaders import DebridClient, _stream_to
from romarr.platforms import resolve


class FixtureResponse:
    headers = {'Content-Disposition': 'attachment; filename="fixture.nes"'}
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def iter_content(self, chunk_size): yield b'fixture-data'


def test_download_does_not_follow_attacker_partial_symlink(tmp_path):
    target = tmp_path/'downloads'; target.mkdir()
    victim = tmp_path/'unrelated'; victim.write_bytes(b'original')
    (target/'fixture.nes.partial').symlink_to(victim)
    try:
        _stream_to(FixtureResponse(), target, 'https://fixture.invalid/fixture.nes')
    except (OSError, ValueError):
        pass
    assert victim.read_bytes() == b'original', 'Partial file followed a symlink outside download directory'


def test_import_does_not_escape_via_platform_directory_symlink(tmp_path):
    source = tmp_path/'fixture.nes'; source.write_bytes(b'fixture-data')
    root = tmp_path/'library'; root.mkdir()
    outside = tmp_path/'unrelated'; outside.mkdir()
    (root/'nes').symlink_to(outside, target_is_directory=True)
    try:
        library.import_rom(source, resolve('nes'), root)
    except (OSError, ValueError):
        pass
    assert not (outside/'fixture.nes').exists(), 'Importer wrote through an escaped platform symlink'


def test_import_does_not_read_download_directory_symlink_targets(tmp_path):
    downloads = tmp_path/'downloads'; downloads.mkdir()
    outside = tmp_path/'unrelated.nes'; outside.write_bytes(b'private-fixture')
    (downloads/'fixture.nes').symlink_to(outside)
    root = tmp_path/'library'
    try:
        library.import_rom(downloads, resolve('nes'), root)
    except (OSError, ValueError):
        pass
    assert not list(root.rglob('*.nes')), 'A file outside the selected download directory was imported'


def test_failed_copy_never_publishes_partial_rom(tmp_path, monkeypatch):
    source = tmp_path/'fixture.nes'; source.write_bytes(b'complete-fixture')
    root = tmp_path/'library'
    def interrupted(self, name, destination):
        destination.write_bytes(b'partial')
        raise OSError('simulated storage failure')
    monkeypatch.setattr(library._PathSource, 'copy', interrupted)
    try:
        library.import_rom(source, resolve('nes'), root)
    except OSError:
        pass
    assert not (root/'nes'/'fixture.nes').exists(), 'A failed import left a visible truncated ROM'


def test_debrid_provider_filename_cannot_escape_download_root(tmp_path):
    target = tmp_path/'downloads'; target.mkdir()
    client = DebridClient(SimpleNamespace(timeout=1))
    client._resolve = Mock(return_value=('../escaped.nes', 'https://fixture.invalid/data'))
    client._download = Mock(return_value=True)
    try:
        client._fetch_links(['fixture'], target)
    except (OSError, ValueError):
        pass
    for call in client._download.call_args_list:
        destination = call.args[1]
        assert destination.resolve().is_relative_to(target.resolve()), 'Provider-supplied filename escaped root'


def test_failed_overwrite_preserves_existing_rom(tmp_path, monkeypatch):
    source = tmp_path/'fixture.nes'; source.write_bytes(b'new-complete-fixture')
    root = tmp_path/'library'; (root/'nes').mkdir(parents=True)
    original = root/'nes'/'fixture.nes'; original.write_bytes(b'old-complete-fixture')
    def interrupted(self, name, destination):
        destination.write_bytes(b'partial')
        raise OSError('simulated storage failure')
    monkeypatch.setattr(library._PathSource, 'copy', interrupted)
    result = library.import_rom(source, resolve('nes'), root, overwrite=True)
    assert not result[0].ok
    assert original.read_bytes() == b'old-complete-fixture'


def test_failed_disc_member_copy_leaves_no_partial_set(tmp_path, monkeypatch):
    source = tmp_path/'download'; source.mkdir()
    (source/'Fixture.cue').write_text('FILE "Fixture.bin" BINARY\n  TRACK 01 MODE1/2352\n    INDEX 01 00:00:00\n')
    (source/'Fixture.bin').write_bytes(b'complete-data')
    root = tmp_path/'library'
    original_copy = library._PathSource.copy
    def interrupted(self, name, destination):
        if name.endswith('.bin'):
            destination.write_bytes(b'partial')
            raise OSError('simulated storage failure')
        original_copy(self, name, destination)
    monkeypatch.setattr(library._PathSource, 'copy', interrupted)
    result = library.import_rom(source, resolve('psx'), root)
    assert not result[0].ok
    assert not (root/'psx'/'Fixture').exists()
    assert not list((root/'psx').glob('.romarr-import-*'))


def test_concurrent_import_does_not_overwrite_newly_published_rom(tmp_path, monkeypatch):
    source = tmp_path/'fixture.nes'; source.write_bytes(b'our-data')
    root = tmp_path/'library'
    original_copy = library._PathSource.copy
    def competing_copy(self, name, destination):
        original_copy(self, name, destination)
        (root/'nes'/'fixture.nes').write_bytes(b'other-import-data')
    monkeypatch.setattr(library._PathSource, 'copy', competing_copy)
    result = library.import_rom(source, resolve('nes'), root)
    assert not result[0].ok
    assert (root/'nes'/'fixture.nes').read_bytes() == b'other-import-data'


def test_failed_disc_rollback_retains_recoverable_original(tmp_path, monkeypatch):
    from pathlib import Path
    source = tmp_path/'download'; source.mkdir()
    (source/'Fixture.cue').write_text('FILE "Fixture.bin" BINARY\n  TRACK 01 MODE1/2352\n    INDEX 01 00:00:00\n')
    (source/'Fixture.bin').write_bytes(b'new-data')
    root = tmp_path/'library'
    destination = root/'psx'/'Fixture'; destination.mkdir(parents=True)
    (destination/'Fixture.bin').write_bytes(b'old-complete-data')
    rename = Path.rename
    def failing_rename(self, target):
        if self.name in ('set', 'previous'):
            raise OSError('simulated publish and rollback failure')
        return rename(self, target)
    monkeypatch.setattr(Path, 'rename', failing_rename)
    result = library.import_rom(source, resolve('psx'), root, overwrite=True)
    assert not result[0].ok
    backups = list((root/'psx').glob('.romarr-previous-*/previous/Fixture.bin'))
    assert len(backups) == 1
    assert backups[0].read_bytes() == b'old-complete-data'


def test_zip_expansion_budget_prevents_visible_oversized_output(tmp_path, monkeypatch):
    import zipfile
    source = tmp_path/'fixture.zip'
    with zipfile.ZipFile(source, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('fixture.nes', b'0' * 4096)
    monkeypatch.setenv('ROMARR_MAX_IMPORT_BYTES', '128')
    root = tmp_path/'library'
    result = library.import_rom(source, resolve('nes'), root)
    assert not result[0].ok
    assert not list(root.rglob('*.nes'))
    assert not list(root.rglob('.romarr-import-*'))


def test_import_budget_counts_all_games_in_bundle(tmp_path, monkeypatch):
    import zipfile
    source = tmp_path/'fixture.zip'
    with zipfile.ZipFile(source, 'w') as archive:
        archive.writestr('A.nes', b'a' * 80)
        archive.writestr('B.nes', b'b' * 80)
    monkeypatch.setenv('ROMARR_MAX_IMPORT_BYTES', '100')
    root = tmp_path/'library'
    result = library.import_rom(source, resolve('nes'), root)
    assert sum(item.ok for item in result) == 1
    assert sum(p.stat().st_size for p in root.rglob('*.nes')) == 80


def test_metadata_read_limit_does_not_limit_streaming_dat_hash(tmp_path):
    import zipfile
    from romarr.dat import hash_bytes
    payload = b'NES\x1a' + bytes(12) + bytes(library.MAX_METADATA_BYTES + 5)
    plain = tmp_path/'fixture.nes'; plain.write_bytes(payload)
    archive = tmp_path/'fixture.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr('fixture.nes', payload)
    for source in (library._PathSource(plain), library._ZipSource(archive)):
        try:
            source.read('fixture.nes')
        except ValueError:
            pass
        else:
            raise AssertionError('Metadata reader accepted more than 1MiB')
        assert source.hashes('fixture.nes') == hash_bytes(payload, suffix='.nes')


def test_invalid_resource_settings_fail_before_copy(tmp_path, monkeypatch):
    source = tmp_path/'fixture.nes'; source.write_bytes(b'fixture')
    root = tmp_path/'library'
    for setting in ('ROMARR_MAX_IMPORT_BYTES', 'ROMARR_IMPORT_TIMEOUT_SECONDS'):
        for value in ('0', '-1', 'not-an-integer'):
            with monkeypatch.context() as patch:
                patch.setenv(setting, value)
                result = library.import_rom(source, resolve('nes'), root)
                assert not result[0].ok
                assert setting in result[0].reason
    assert not root.exists()


def test_archive_process_timeout_terminates_worker(tmp_path, monkeypatch):
    import subprocess
    import sys
    import time
    monkeypatch.setenv('ROMARR_IMPORT_TIMEOUT_SECONDS', '1')
    source = library._BsdtarSource(tmp_path/'unused', sys.executable)
    started = time.monotonic()
    try:
        source._stream(['-c', 'import time; time.sleep(30)'], __import__('io').BytesIO(), [100])
    except subprocess.CalledProcessError:
        pass
    else:
        raise AssertionError('Archive worker was not terminated')
    assert time.monotonic() - started < 5


def test_libarchive_treats_option_like_member_as_filename(tmp_path, monkeypatch):
    source = library._BsdtarSource(tmp_path/'fixture.7z', 'bsdtar')
    calls = []
    def capture(args, destination, budget):
        calls.append(args)
        destination.write(b'fixture')
    monkeypatch.setattr(source, '_stream', capture)
    member = '--use-compress-program=unexpected.nes'
    source.read(member)
    source.copy(member, tmp_path/'out.nes')
    assert all(args[-2:] == ['--', member] for args in calls)
