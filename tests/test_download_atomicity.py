from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from romarr.downloaders import _stream_to, DebridClient


class Response:
    headers={'Content-Disposition':'attachment; filename="fixture.nes"'}
    def __enter__(self): return self
    def __exit__(self,*args): pass
    def iter_content(self,chunk_size):
        yield b'complete fixture'


def test_existing_final_file_is_never_overwritten(tmp_path):
    target=tmp_path/'fixture.nes';target.write_bytes(b'existing')
    with pytest.raises(FileExistsError):
        _stream_to(Response(),tmp_path,'https://example.invalid/fixture.nes')
    assert target.read_bytes()==b'existing'
    assert not list(tmp_path.glob('.romarr-download-*'))


def test_failed_stream_leaves_no_visible_or_partial_file(tmp_path):
    class Broken(Response):
        def iter_content(self,chunk_size):
            yield b'incomplete'
            raise OSError('interrupted fixture stream')
    with pytest.raises(OSError):
        _stream_to(Broken(),tmp_path,'https://example.invalid/fixture.nes')
    assert list(tmp_path.iterdir())==[]


def test_provider_directory_name_cannot_escape_save_path(tmp_path):
    client=DebridClient(SimpleNamespace(timeout=1,save_path=str(tmp_path),api_token='fixture'))
    client._finished=Mock(return_value=[('../outside',['fixture'])])
    client._fetch_links=Mock()
    assert client.completed()==[]
    client._fetch_links.assert_not_called()


def test_explicit_container_mask_applies_only_to_finished_download(tmp_path,monkeypatch):
    monkeypatch.setenv('UMASK','002')
    _stream_to(Response(),tmp_path,'https://example.invalid/fixture.nes')
    assert (tmp_path/'fixture.nes').stat().st_mode & 0o777 == 0o664


def test_actual_download_bytes_enforce_cap_without_trusting_headers(tmp_path,monkeypatch):
    monkeypatch.setenv('ROMARR_MAX_DOWNLOAD_BYTES','4')
    with pytest.raises(ValueError,match='byte limit'):
        _stream_to(Response(),tmp_path,'https://example.invalid/fixture.nes')
    assert list(tmp_path.iterdir())==[]


def test_advertised_oversize_never_creates_a_partial_file(tmp_path,monkeypatch):
    monkeypatch.setenv('ROMARR_MAX_DOWNLOAD_BYTES','4')
    class Large(Response):
        headers={'Content-Length':'500'}
        def iter_content(self,chunk_size):
            raise AssertionError('Oversize response should not be consumed')
    with pytest.raises(ValueError,match='byte limit'):
        _stream_to(Large(),tmp_path,'https://example.invalid/fixture.nes')
    assert list(tmp_path.iterdir())==[]
