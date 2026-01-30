"""Tests for vagrant-spk."""

import os
import shutil
from types import SimpleNamespace

import pytest


class TestSwitchToHttpsCdnResources:
    """Tests for switch_to_https_cdn_resources function."""

    def test_converts_http_fonts_to_https(self, vagrant_spk):
        input_html = '<link href="http://fonts.googleapis.com/css?family=Roboto">'
        result = vagrant_spk.switch_to_https_cdn_resources(input_html)
        assert "https://fonts.googleapis.com" in result
        assert "http://fonts.googleapis.com" not in result

    def test_handles_single_quotes(self, vagrant_spk):
        input_html = "<link href='http://fonts.googleapis.com/css?family=Roboto'>"
        result = vagrant_spk.switch_to_https_cdn_resources(input_html)
        assert "https://fonts.googleapis.com" in result
        assert "http://fonts.googleapis.com" not in result

    def test_leaves_https_unchanged(self, vagrant_spk):
        input_html = '<link href="https://fonts.googleapis.com/css?family=Roboto">'
        result = vagrant_spk.switch_to_https_cdn_resources(input_html)
        assert result == input_html

    def test_leaves_unrelated_content_unchanged(self, vagrant_spk):
        input_html = '<div>Hello World</div>'
        result = vagrant_spk.switch_to_https_cdn_resources(input_html)
        assert result == input_html

    def test_handles_multiple_occurrences(self, vagrant_spk):
        input_html = '''
        <link href="http://fonts.googleapis.com/css?family=Roboto">
        <link href="http://fonts.googleapis.com/css?family=Open+Sans">
        '''
        result = vagrant_spk.switch_to_https_cdn_resources(input_html)
        assert result.count("https://fonts.googleapis.com") == 2
        assert "http://fonts.googleapis.com" not in result


class TestVagrantfileContents:
    """Tests for the VAGRANTFILE_CONTENTS constant."""

    def test_contains_vagrant_api_version(self, vagrant_spk):
        assert 'VAGRANTFILE_API_VERSION = "2"' in vagrant_spk.VAGRANTFILE_CONTENTS

    def test_contains_debian_bookworm(self, vagrant_spk):
        assert 'debian/bookworm64' in vagrant_spk.VAGRANTFILE_CONTENTS

    def test_contains_port_forwarding(self, vagrant_spk):
        assert 'forwarded_port' in vagrant_spk.VAGRANTFILE_CONTENTS
        assert '6090' in vagrant_spk.VAGRANTFILE_CONTENTS

    def test_contains_provisioning(self, vagrant_spk):
        assert 'global-setup.sh' in vagrant_spk.VAGRANTFILE_CONTENTS
        assert 'setup.sh' in vagrant_spk.VAGRANTFILE_CONTENTS

    def test_contains_synced_folders(self, vagrant_spk):
        assert '/opt/app' in vagrant_spk.VAGRANTFILE_CONTENTS
        assert '/host-dot-sandstorm' in vagrant_spk.VAGRANTFILE_CONTENTS


class TestGlobalSetupScript:
    """Tests for the GLOBAL_SETUP_SCRIPT constant."""

    def test_starts_with_shebang(self, vagrant_spk):
        assert vagrant_spk.GLOBAL_SETUP_SCRIPT.startswith("#!/bin/bash")

    def test_uses_strict_mode(self, vagrant_spk):
        assert "set -euo pipefail" in vagrant_spk.GLOBAL_SETUP_SCRIPT

    def test_installs_sandstorm(self, vagrant_spk):
        assert "install.sandstorm.io" in vagrant_spk.GLOBAL_SETUP_SCRIPT

    def test_adds_vagrant_to_sandstorm_group(self, vagrant_spk):
        assert "usermod" in vagrant_spk.GLOBAL_SETUP_SCRIPT
        assert "sandstorm" in vagrant_spk.GLOBAL_SETUP_SCRIPT
        assert "vagrant" in vagrant_spk.GLOBAL_SETUP_SCRIPT


class TestStackPlugin:
    """Tests for StackPlugin class."""

    def test_loads_valid_stack(self, vagrant_spk):
        plugin = vagrant_spk.StackPlugin("static")
        assert plugin._plugin_name == "static"

    def test_raises_for_invalid_stack(self, vagrant_spk):
        with pytest.raises(Exception) as exc_info:
            vagrant_spk.StackPlugin("nonexistent_stack")
        assert "No stack plugin" in str(exc_info.value)

    def test_plugin_file_returns_correct_path(self, vagrant_spk):
        plugin = vagrant_spk.StackPlugin("static")
        path = plugin.plugin_file("setup.sh")
        assert path.endswith("stacks/static/setup.sh")
        assert os.path.exists(path)


class TestCheckDotSandstorm:
    """Tests for check_dot_sandstorm function."""

    def test_raises_when_no_sandstorm_dir(self, vagrant_spk, tmp_path, monkeypatch):
        monkeypatch.setattr(vagrant_spk, 'PWD', str(tmp_path))

        with pytest.raises(Exception) as exc_info:
            vagrant_spk.check_dot_sandstorm()
        assert ".sandstorm" in str(exc_info.value)

    def test_raises_when_no_vagrantfile(self, vagrant_spk, tmp_path, monkeypatch):
        sandstorm_dir = tmp_path / ".sandstorm"
        sandstorm_dir.mkdir()
        monkeypatch.setattr(vagrant_spk, 'PWD', str(tmp_path))

        with pytest.raises(Exception) as exc_info:
            vagrant_spk.check_dot_sandstorm()
        assert "Vagrantfile" in str(exc_info.value)

    def test_succeeds_with_valid_setup(self, vagrant_spk, tmp_path, monkeypatch):
        sandstorm_dir = tmp_path / ".sandstorm"
        sandstorm_dir.mkdir()
        (sandstorm_dir / "Vagrantfile").touch()
        monkeypatch.setattr(vagrant_spk, 'PWD', str(tmp_path))

        # Should not raise
        vagrant_spk.check_dot_sandstorm()


class TestPack:
    """Tests for pack function."""

    @pytest.fixture
    def setup_pack_env(self, vagrant_spk, tmp_path, monkeypatch, fp):
        """Set up environment for pack tests."""
        # Create .sandstorm directory with Vagrantfile
        sandstorm_dir = tmp_path / ".sandstorm"
        sandstorm_dir.mkdir()
        (sandstorm_dir / "Vagrantfile").write_text("# Vagrantfile")
        (sandstorm_dir / "sandstorm-pkgdef.capnp").write_text("# pkgdef")

        # Create a fake output package file that the "VM" would produce
        # vagrant-spk looks for it in the current directory, not work_directory
        monkeypatch.chdir(tmp_path)
        (tmp_path / "sandstorm-package.spk").write_bytes(b"fake spk content")

        # Mock vagrant ssh command
        fp.register_subprocess(
            ["vagrant", "ssh", fp.any()],
            returncode=0
        )

        return tmp_path, sandstorm_dir

    def test_pack_calls_vagrant_command(self, vagrant_spk, setup_pack_env, fp, mocker):
        # Note: vagrant-spk pack doesn't validate args before calling vagrant,
        # it just accesses args.command_specific_args[0] directly.
        # This is a difference from lima-spk that could be considered a bug.
        tmp_path, sandstorm_dir = setup_pack_env
        output_file = tmp_path / "my-app.spk"

        mock_call = mocker.patch.object(vagrant_spk, 'call_vagrant_command', return_value=0)

        args = SimpleNamespace(
            command_specific_args=[str(output_file)],
            work_directory=str(tmp_path)
        )

        vagrant_spk.pack(args)

        mock_call.assert_called_once()
        # Check that it was called with ssh and the pack command
        call_args = mock_call.call_args
        assert "ssh" in call_args[0]

    def test_pack_moves_output_file(self, vagrant_spk, setup_pack_env, mocker):
        tmp_path, sandstorm_dir = setup_pack_env
        output_file = tmp_path / "my-app.spk"

        # Mock call_vagrant_command to do nothing
        mocker.patch.object(vagrant_spk, 'call_vagrant_command', return_value=0)

        args = SimpleNamespace(
            command_specific_args=[str(output_file)],
            work_directory=str(tmp_path)
        )

        vagrant_spk.pack(args)

        assert output_file.exists()
        assert output_file.read_bytes() == b"fake spk content"


class TestVerify:
    """Tests for verify function."""

    def test_verify_copies_and_removes_temp_file(self, vagrant_spk, tmp_path, mocker):
        # Create .sandstorm directory
        sandstorm_dir = tmp_path / ".sandstorm"
        sandstorm_dir.mkdir()
        (sandstorm_dir / "Vagrantfile").write_text("# Vagrantfile")

        # Create source spk file with specific content
        spk_file = tmp_path / "test.spk"
        spk_file.write_bytes(b"spk content for verification")

        temp_spk = sandstorm_dir / "test.spk"
        copy_verified = {"copied": False}

        def mock_vagrant_call(*args, **kwargs):
            # Verify the temp file exists when command runs
            if temp_spk.exists() and temp_spk.read_bytes() == b"spk content for verification":
                copy_verified["copied"] = True
            return 0

        mocker.patch.object(vagrant_spk, 'call_vagrant_command', side_effect=mock_vagrant_call)

        args = SimpleNamespace(
            command_specific_args=[str(spk_file)],
            work_directory=str(tmp_path)
        )

        vagrant_spk.verify(args)

        assert copy_verified["copied"], "Temp file was not copied before running verify command"
        assert not temp_spk.exists(), "Temp file was not cleaned up"

    def test_verify_removes_temp_file_on_failure(self, vagrant_spk, tmp_path, mocker):
        """Verify temp file cleanup happens even when the command fails."""
        sandstorm_dir = tmp_path / ".sandstorm"
        sandstorm_dir.mkdir()
        (sandstorm_dir / "Vagrantfile").write_text("# Vagrantfile")

        spk_file = tmp_path / "test.spk"
        spk_file.write_bytes(b"spk content")

        def mock_vagrant_fail(*args, **kwargs):
            raise Exception("vagrant command failed")

        mocker.patch.object(vagrant_spk, 'call_vagrant_command', side_effect=mock_vagrant_fail)

        args = SimpleNamespace(
            command_specific_args=[str(spk_file)],
            work_directory=str(tmp_path)
        )

        with pytest.raises(Exception):
            vagrant_spk.verify(args)

        temp_spk = sandstorm_dir / "test.spk"
        assert not temp_spk.exists(), "Temp file was not cleaned up after failure"

    def test_verify_calls_vagrant_with_spk_verify(self, vagrant_spk, tmp_path, mocker):
        sandstorm_dir = tmp_path / ".sandstorm"
        sandstorm_dir.mkdir()
        (sandstorm_dir / "Vagrantfile").write_text("# Vagrantfile")

        spk_file = tmp_path / "test.spk"
        spk_file.write_bytes(b"spk content")

        mock_call = mocker.patch.object(vagrant_spk, 'call_vagrant_command', return_value=0)

        args = SimpleNamespace(
            command_specific_args=[str(spk_file)],
            work_directory=str(tmp_path)
        )

        vagrant_spk.verify(args)

        mock_call.assert_called_once()
        call_args_str = str(mock_call.call_args)
        assert "spk verify" in call_args_str


class TestPublish:
    """Tests for publish function."""

    def test_publish_exits_without_spk_file(self, vagrant_spk, tmp_path):
        args = SimpleNamespace(
            command_specific_args=[],
            work_directory=str(tmp_path)
        )

        with pytest.raises(SystemExit) as exc_info:
            vagrant_spk.publish(args)
        assert exc_info.value.code == 1

    def test_publish_copies_and_removes_temp_file(self, vagrant_spk, tmp_path, mocker):
        sandstorm_dir = tmp_path / ".sandstorm"
        sandstorm_dir.mkdir()
        (sandstorm_dir / "Vagrantfile").write_text("# Vagrantfile")

        spk_file = tmp_path / "test.spk"
        spk_file.write_bytes(b"spk content for publishing")

        temp_spk = sandstorm_dir / "test.spk"
        copy_verified = {"copied": False}

        def mock_vagrant_call(*args, **kwargs):
            if temp_spk.exists() and temp_spk.read_bytes() == b"spk content for publishing":
                copy_verified["copied"] = True
            return 0

        mocker.patch.object(vagrant_spk, 'call_vagrant_command', side_effect=mock_vagrant_call)

        args = SimpleNamespace(
            command_specific_args=[str(spk_file)],
            work_directory=str(tmp_path)
        )

        vagrant_spk.publish(args)

        assert copy_verified["copied"], "Temp file was not copied before running publish command"
        assert not temp_spk.exists(), "Temp file was not cleaned up"

    def test_publish_removes_temp_file_on_failure(self, vagrant_spk, tmp_path, mocker):
        """Verify temp file cleanup happens even when the command fails."""
        sandstorm_dir = tmp_path / ".sandstorm"
        sandstorm_dir.mkdir()
        (sandstorm_dir / "Vagrantfile").write_text("# Vagrantfile")

        spk_file = tmp_path / "test.spk"
        spk_file.write_bytes(b"spk content")

        def mock_vagrant_fail(*args, **kwargs):
            raise Exception("vagrant command failed")

        mocker.patch.object(vagrant_spk, 'call_vagrant_command', side_effect=mock_vagrant_fail)

        args = SimpleNamespace(
            command_specific_args=[str(spk_file)],
            work_directory=str(tmp_path)
        )

        with pytest.raises(Exception):
            vagrant_spk.publish(args)

        temp_spk = sandstorm_dir / "test.spk"
        assert not temp_spk.exists(), "Temp file was not cleaned up after failure"

    def test_publish_calls_vagrant_with_spk_publish(self, vagrant_spk, tmp_path, mocker):
        sandstorm_dir = tmp_path / ".sandstorm"
        sandstorm_dir.mkdir()
        (sandstorm_dir / "Vagrantfile").write_text("# Vagrantfile")

        spk_file = tmp_path / "test.spk"
        spk_file.write_bytes(b"spk content")

        mock_call = mocker.patch.object(vagrant_spk, 'call_vagrant_command', return_value=0)

        args = SimpleNamespace(
            command_specific_args=[str(spk_file)],
            work_directory=str(tmp_path)
        )

        vagrant_spk.publish(args)

        mock_call.assert_called_once()
        call_args_str = str(mock_call.call_args)
        assert "spk publish" in call_args_str
        assert "keyring" in call_args_str


class TestKeygen:
    """Tests for keygen function."""

    def test_keygen_calls_vagrant_command(self, vagrant_spk, tmp_path, mocker):
        sandstorm_dir = tmp_path / ".sandstorm"
        sandstorm_dir.mkdir()
        (sandstorm_dir / "Vagrantfile").write_text("# Vagrantfile")

        mock_call = mocker.patch.object(vagrant_spk, 'call_vagrant_command', return_value=0)

        args = SimpleNamespace(
            command_specific_args=[],
            work_directory=str(tmp_path)
        )

        vagrant_spk.keygen(args)

        mock_call.assert_called_once()
        call_args_str = str(mock_call.call_args)
        assert "spk keygen" in call_args_str
        assert "keyring" in call_args_str

    def test_keygen_passes_extra_args(self, vagrant_spk, tmp_path, mocker):
        sandstorm_dir = tmp_path / ".sandstorm"
        sandstorm_dir.mkdir()
        (sandstorm_dir / "Vagrantfile").write_text("# Vagrantfile")

        mock_call = mocker.patch.object(vagrant_spk, 'call_vagrant_command', return_value=0)

        args = SimpleNamespace(
            command_specific_args=["--app-id", "abc123"],
            work_directory=str(tmp_path)
        )

        vagrant_spk.keygen(args)

        mock_call.assert_called_once()
        call_args_str = str(mock_call.call_args)
        assert "--app-id" in call_args_str
        assert "abc123" in call_args_str


class TestListkeys:
    """Tests for listkeys function."""

    def test_listkeys_calls_vagrant_command(self, vagrant_spk, tmp_path, mocker):
        sandstorm_dir = tmp_path / ".sandstorm"
        sandstorm_dir.mkdir()
        (sandstorm_dir / "Vagrantfile").write_text("# Vagrantfile")

        mock_call = mocker.patch.object(vagrant_spk, 'call_vagrant_command', return_value=0)

        args = SimpleNamespace(
            command_specific_args=[],
            work_directory=str(tmp_path)
        )

        vagrant_spk.listkeys(args)

        mock_call.assert_called_once()
        call_args_str = str(mock_call.call_args)
        assert "spk listkeys" in call_args_str
        assert "keyring" in call_args_str


class TestGetkey:
    """Tests for getkey function."""

    def test_getkey_calls_vagrant_command_with_key_id(self, vagrant_spk, tmp_path, mocker):
        sandstorm_dir = tmp_path / ".sandstorm"
        sandstorm_dir.mkdir()
        (sandstorm_dir / "Vagrantfile").write_text("# Vagrantfile")

        mock_call = mocker.patch.object(vagrant_spk, 'call_vagrant_command', return_value=0)

        args = SimpleNamespace(
            command_specific_args=["abc123xyz"],
            work_directory=str(tmp_path)
        )

        vagrant_spk.getkey(args)

        mock_call.assert_called_once()
        call_args_str = str(mock_call.call_args)
        assert "spk getkey" in call_args_str
        assert "abc123xyz" in call_args_str
        assert "keyring" in call_args_str

    def test_getkey_disables_tty(self, vagrant_spk, tmp_path, mocker):
        """Verify getkey passes -T to disable TTY allocation."""
        sandstorm_dir = tmp_path / ".sandstorm"
        sandstorm_dir.mkdir()
        (sandstorm_dir / "Vagrantfile").write_text("# Vagrantfile")

        mock_call = mocker.patch.object(vagrant_spk, 'call_vagrant_command', return_value=0)

        args = SimpleNamespace(
            command_specific_args=["abc123xyz"],
            work_directory=str(tmp_path)
        )

        vagrant_spk.getkey(args)

        call_args = mock_call.call_args[0]
        # Should have -T flag to disable TTY
        assert "-T" in call_args
