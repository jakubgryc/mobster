from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from mobster.cmd.upload.oidc import OIDCClientCredentials
from mobster.cmd.upload.tpa import TPAClient
from mobster.cmd.upload.upload import TPAUploadCommand, UploadReport


@pytest.fixture
def mock_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set up environment variables needed for the TPA upload command."""
    monkeypatch.setenv("MOBSTER_TPA_SSO_TOKEN_URL", "https://test.token.url")
    monkeypatch.setenv("MOBSTER_TPA_SSO_ACCOUNT", "test-account")
    monkeypatch.setenv("MOBSTER_TPA_SSO_TOKEN", "test-token")


@pytest.fixture
def mock_tpa_client() -> AsyncMock:
    """Create a mock TPA client that returns success for uploads."""
    mock = AsyncMock(spec=TPAClient)
    mock.upload_sbom = AsyncMock(
        return_value=httpx.Response(
            200, request=httpx.Request("POST", "https://example.com")
        )
    )
    return mock


@pytest.fixture
def mock_oidc_credentials() -> MagicMock:
    return MagicMock(spec=OIDCClientCredentials)


@pytest.fixture
def command_args() -> MagicMock:
    args = MagicMock()
    args.tpa_base_url = "https://test.tpa.url"
    args.workers = 2
    return args


@pytest.mark.asyncio
@patch("mobster.cmd.upload.upload.TPAUploadCommand.gather_sboms")
@patch("mobster.cmd.upload.upload.TPAClient")
@patch("mobster.cmd.upload.upload.OIDCClientCredentials")
async def test_execute_upload_from_directory(
    mock_oidc: MagicMock,
    mock_tpa_client_class: MagicMock,
    mock_gather_sboms: MagicMock,
    mock_env_vars: MagicMock,
    mock_tpa_client: MagicMock,
) -> None:
    """Test uploading SBOMs from a directory."""
    mock_tpa_client_class.return_value = mock_tpa_client
    mock_tpa_client.upload_sbom.return_value = httpx.Response(
        200, request=httpx.Request("POST", "https://example.com")
    )
    mock_oidc.return_value = MagicMock(spec=OIDCClientCredentials)

    file_list = [Path("/test/dir/file1.json"), Path("/test/dir/file2.json")]
    mock_gather_sboms.return_value = file_list

    args = MagicMock()
    args.from_dir = Path("/test/dir")
    args.file = None
    args.tpa_base_url = "https://test.tpa.url"
    args.workers = 2
    command = TPAUploadCommand(args)

    await command.execute()

    # Verify TPAClient is created with the correct parameters
    for call in mock_tpa_client_class.call_args_list:
        assert call[1]["base_url"] == "https://test.tpa.url"
        assert call[1]["auth"] == mock_oidc.return_value

    # Verify upload_sbom was called for each file
    assert mock_tpa_client.upload_sbom.call_count == len(file_list)

    # Verify the command's success flag is True since all uploads succeeded
    assert command.success is True


@pytest.mark.asyncio
@patch("mobster.cmd.upload.upload.TPAClient")
@patch("mobster.cmd.upload.upload.OIDCClientCredentials")
async def test_execute_upload_single_file(
    mock_oidc: MagicMock,
    mock_tpa_client_class: MagicMock,
    mock_env_vars: MagicMock,
    mock_tpa_client: MagicMock,
) -> None:
    """Test uploading a single SBOM file."""
    mock_tpa_client_class.return_value = mock_tpa_client
    mock_tpa_client.upload_sbom.return_value = httpx.Response(
        200, request=httpx.Request("POST", "https://example.com")
    )
    mock_oidc.return_value = MagicMock(spec=OIDCClientCredentials)

    # Create command with args
    args = MagicMock()
    args.from_dir = None
    args.file = Path("/test/single_file.json")
    args.tpa_base_url = "https://test.tpa.url"
    args.workers = 2
    command = TPAUploadCommand(args)

    await command.execute()

    # Verify TPA client was created with correct base URL
    mock_tpa_client_class.assert_called_once_with(
        base_url="https://test.tpa.url", auth=mock_oidc.return_value
    )

    # Verify upload_sbom was called once with the correct file
    mock_tpa_client.upload_sbom.assert_called_once_with(Path("/test/single_file.json"))

    # Verify the command's success flag is True
    assert command.success is True


@pytest.mark.asyncio
@patch("mobster.cmd.upload.upload.TPAUploadCommand.gather_sboms")
@patch("mobster.cmd.upload.upload.TPAClient")
@patch("mobster.cmd.upload.upload.OIDCClientCredentials")
async def test_execute_upload_failure(
    mock_oidc: MagicMock,
    mock_tpa_client_class: MagicMock,
    mock_gather_sboms: MagicMock,
    mock_env_vars: MagicMock,
) -> None:
    mock_tpa_client = AsyncMock(spec=TPAClient)
    # Simulate failure by raising an exception, which will be caught and return False
    mock_tpa_client.upload_sbom = AsyncMock(side_effect=Exception("Upload failed"))
    mock_tpa_client_class.return_value = mock_tpa_client
    mock_oidc.return_value = MagicMock(spec=OIDCClientCredentials)

    file_list = [Path("/test/dir/file1.json"), Path("/test/dir/file2.json")]
    mock_gather_sboms.return_value = file_list

    args = MagicMock()
    args.from_dir = Path("/test/dir")
    args.file = None
    args.tpa_base_url = "https://test.tpa.url"
    args.workers = 1
    command = TPAUploadCommand(args)

    await command.execute()

    # Verify upload_sbom was called for each file
    assert mock_tpa_client.upload_sbom.call_count == len(file_list)

    # Verify the command's success flag is False since all uploads failed
    assert command.success is False


@pytest.mark.asyncio
@patch("mobster.cmd.upload.upload.TPAUploadCommand.gather_sboms")
@patch("mobster.cmd.upload.upload.TPAClient")
@patch("mobster.cmd.upload.upload.OIDCClientCredentials")
async def test_execute_upload_exception(
    mock_oidc: MagicMock,
    mock_tpa_client_class: MagicMock,
    mock_gather_sboms: MagicMock,
    mock_env_vars: MagicMock,
) -> None:
    mock_tpa_client = AsyncMock(spec=TPAClient)
    mock_tpa_client.upload_sbom = AsyncMock(side_effect=Exception("Upload failed"))
    mock_tpa_client_class.return_value = mock_tpa_client
    mock_oidc.return_value = MagicMock(spec=OIDCClientCredentials)

    file_list = [Path("/test/dir/file1.json")]
    mock_gather_sboms.return_value = file_list

    args = MagicMock()
    args.from_dir = Path("/test/dir")
    args.file = None
    args.tpa_base_url = "https://test.tpa.url"
    args.workers = 1
    command = TPAUploadCommand(args)

    await command.execute()

    mock_tpa_client.upload_sbom.assert_called_once()

    # Verify the command's success flag is False
    assert command.success is False


@pytest.mark.asyncio
@patch("mobster.cmd.upload.upload.TPAUploadCommand.gather_sboms")
@patch("mobster.cmd.upload.upload.TPAClient")
@patch("mobster.cmd.upload.upload.OIDCClientCredentials")
async def test_execute_upload_mixed_results(
    mock_oidc: MagicMock,
    mock_tpa_client_class: MagicMock,
    mock_gather_sboms: MagicMock,
    mock_env_vars: MagicMock,
    capsys: Any,
) -> None:
    mock_tpa_client = AsyncMock(spec=TPAClient)
    # First upload succeeds, second one fails
    mock_tpa_client.upload_sbom.side_effect = [
        httpx.Response(200, request=httpx.Request("POST", "https://example.com")),
        Exception("Upload failed"),  # Failure
    ]
    mock_tpa_client_class.return_value = mock_tpa_client
    mock_oidc.return_value = MagicMock(spec=OIDCClientCredentials)

    file_list = [Path("/test/dir/file1.json"), Path("/test/dir/file2.json")]
    mock_gather_sboms.return_value = file_list

    args = MagicMock()
    args.from_dir = Path("/test/dir")
    args.file = None
    args.tpa_base_url = "https://test.tpa.url"
    args.workers = 1
    args.report = True
    command = TPAUploadCommand(args)

    await command.execute()

    expected_report = UploadReport(
        success=[Path("/test/dir/file1.json")],
        failure=[Path("/test/dir/file2.json")],
    )

    out, _ = capsys.readouterr()
    actual_report = UploadReport.model_validate_json(out)
    assert actual_report == expected_report

    # Verify upload_sbom was called for each file
    assert mock_tpa_client.upload_sbom.call_count == len(file_list)

    # Verify the command's success flag is False since at least one upload failed
    assert command.success is False


def test_gather_sboms(tmp_path: Path) -> None:
    (tmp_path / "file1.json").touch()
    (tmp_path / "file2.json").touch()
    (tmp_path / "subdir").mkdir()
    (tmp_path / "subdir" / "file3.json").touch()

    result = TPAUploadCommand.gather_sboms(tmp_path)

    assert len(result) == 3

    result_names = {p.name for p in result}
    expected_names = {"file1.json", "file2.json", "file3.json"}
    assert result_names == expected_names
