"""Tests for lima-spk."""

import json
import os
import shutil
from types import SimpleNamespace

import pytest


class TestGetLimaInstanceName:
    """Tests for get_lima_instance_name function."""

    def test_returns_string_starting_with_prefix(self, lima_spk):
        name = lima_spk.get_lima_instance_name("/home/user/my-app")
        assert name.startswith("sandstorm-")

    def test_includes_directory_basename(self, lima_spk):
        name = lima_spk.get_lima_instance_name("/home/user/my-app")
        assert "my-app" in name

    def test_deterministic_for_same_input(self, lima_spk):
        path = "/home/user/my-app"
        name1 = lima_spk.get_lima_instance_name(path)
        name2 = lima_spk.get_lima_instance_name(path)
        assert name1 == name2

    def test_different_for_different_paths(self, lima_spk):
        name1 = lima_spk.get_lima_instance_name("/home/user/app1")
        name2 = lima_spk.get_lima_instance_name("/home/user/app2")
        assert name1 != name2

    def test_sanitizes_special_characters(self, lima_spk):
        name = lima_spk.get_lima_instance_name("/home/user/My App_v2.0")
        # Should only contain valid hostname characters
        assert all(c.isalnum() or c == '-' for c in name)

    def test_lowercases_name(self, lima_spk):
        name = lima_spk.get_lima_instance_name("/home/user/MyApp")
        assert name == name.lower()


class TestGetLimaYamlContents:
    """Tests for get_lima_yaml_contents function."""

    def test_returns_valid_yaml_string(self, lima_spk):
        content = lima_spk.get_lima_yaml_contents()
        assert isinstance(content, str)
        assert len(content) > 0

    def test_contains_required_sections(self, lima_spk):
        content = lima_spk.get_lima_yaml_contents()
        assert "arch: x86_64" in content
        assert "vmType: qemu" in content
        assert "images:" in content
        assert "mounts:" in content
        assert "portForwards:" in content
        assert "provision:" in content

    def test_contains_sandstorm_port(self, lima_spk):
        content = lima_spk.get_lima_yaml_contents()
        assert str(lima_spk.SANDSTORM_PORT) in content

    def test_uses_debian_bookworm(self, lima_spk):
        content = lima_spk.get_lima_yaml_contents()
        assert "debian-12" in content or "bookworm" in content

    def test_mounts_host_sandstorm_folder(self, lima_spk):
        content = lima_spk.get_lima_yaml_contents()
        assert "~/.sandstorm" in content
        assert "/host-dot-sandstorm" in content


class TestGetLimaInstanceStatus:
    """Tests for get_lima_instance_status function."""

    def test_returns_running_status(self, lima_spk, fp):
        # fp is the fake_process fixture from pytest-subprocess
        fp.register_subprocess(
            ["limactl", "list", "--json"],
            stdout='{"name": "sandstorm-myapp-abc123", "status": "Running"}\n'
        )

        status = lima_spk.get_lima_instance_status("sandstorm-myapp-abc123")
        assert status == "Running"

    def test_returns_stopped_status(self, lima_spk, fp):
        fp.register_subprocess(
            ["limactl", "list", "--json"],
            stdout='{"name": "sandstorm-myapp-abc123", "status": "Stopped"}\n'
        )

        status = lima_spk.get_lima_instance_status("sandstorm-myapp-abc123")
        assert status == "Stopped"

    def test_returns_none_for_nonexistent_instance(self, lima_spk, fp):
        fp.register_subprocess(
            ["limactl", "list", "--json"],
            stdout='{"name": "other-instance", "status": "Running"}\n'
        )

        status = lima_spk.get_lima_instance_status("nonexistent")
        assert status is None

    def test_returns_none_on_empty_output(self, lima_spk, fp):
        fp.register_subprocess(
            ["limactl", "list", "--json"],
            stdout=''
        )

        status = lima_spk.get_lima_instance_status("sandstorm-myapp-abc123")
        assert status is None

    def test_returns_none_on_command_failure(self, lima_spk, fp):
        fp.register_subprocess(
            ["limactl", "list", "--json"],
            returncode=1
        )

        status = lima_spk.get_lima_instance_status("sandstorm-myapp-abc123")
        assert status is None

    def test_handles_multiple_instances(self, lima_spk, fp):
        output = (
            '{"name": "instance-1", "status": "Stopped"}\n'
            '{"name": "sandstorm-target-abc", "status": "Running"}\n'
            '{"name": "instance-3", "status": "Stopped"}\n'
        )
        fp.register_subprocess(
            ["limactl", "list", "--json"],
            stdout=output
        )

        status = lima_spk.get_lima_instance_status("sandstorm-target-abc")
        assert status == "Running"


class TestConfirmOverwrite:
    """Tests for confirm_overwrite function."""

    def test_returns_true_when_noninteractive(self, lima_spk, tmp_path):
        filepath = tmp_path / "existing_file"
        filepath.touch()

        result = lima_spk.confirm_overwrite(str(filepath), noninteractive=True)
        assert result is True

    def test_returns_true_when_file_does_not_exist(self, lima_spk, tmp_path, monkeypatch):
        filepath = tmp_path / "nonexistent_file"

        result = lima_spk.confirm_overwrite(str(filepath), noninteractive=False)
        assert result is True

    def test_returns_true_when_user_confirms(self, lima_spk, tmp_path, monkeypatch):
        filepath = tmp_path / "existing_file"
        filepath.touch()

        monkeypatch.setattr('builtins.input', lambda _: 'y')
        result = lima_spk.confirm_overwrite(str(filepath), noninteractive=False)
        assert result is True

    def test_returns_false_when_user_declines(self, lima_spk, tmp_path, monkeypatch):
        filepath = tmp_path / "existing_file"
        filepath.touch()

        monkeypatch.setattr('builtins.input', lambda _: 'n')
        result = lima_spk.confirm_overwrite(str(filepath), noninteractive=False)
        assert result is False

    def test_accepts_uppercase_y(self, lima_spk, tmp_path, monkeypatch):
        filepath = tmp_path / "existing_file"
        filepath.touch()

        monkeypatch.setattr('builtins.input', lambda _: 'Y')
        result = lima_spk.confirm_overwrite(str(filepath), noninteractive=False)
        # The function uses .lower() so uppercase Y should work
        assert result is True

    def test_returns_false_on_empty_input(self, lima_spk, tmp_path, monkeypatch):
        """Empty input (just pressing enter) should decline."""
        filepath = tmp_path / "existing_file"
        filepath.touch()

        monkeypatch.setattr('builtins.input', lambda _: '')
        result = lima_spk.confirm_overwrite(str(filepath), noninteractive=False)
        assert result is False

    def test_returns_false_on_other_input(self, lima_spk, tmp_path, monkeypatch):
        """Any input other than 'y' should decline."""
        filepath = tmp_path / "existing_file"
        filepath.touch()

        for response in ['yes', 'no', 'maybe', 'Y es', ' y']:
            monkeypatch.setattr('builtins.input', lambda _: response)
            result = lima_spk.confirm_overwrite(str(filepath), noninteractive=False)
            # Only exactly 'y' or 'Y' should return True
            if response.strip().lower() == 'y':
                assert result is True, f"Expected True for '{response}'"
            else:
                assert result is False, f"Expected False for '{response}'"


class TestCheckLimaInstalled:
    """Tests for check_lima_installed function."""

    def test_succeeds_when_lima_available(self, lima_spk, fp):
        fp.register_subprocess(
            ["limactl", "--version"],
            stdout="limactl version 0.18.0"
        )

        # Function returns None on success, just doesn't exit
        lima_spk.check_lima_installed()  # Should not raise

    def test_exits_when_lima_not_available(self, lima_spk, fp):
        fp.register_subprocess(
            ["limactl", "--version"],
            returncode=1
        )

        with pytest.raises(SystemExit):
            lima_spk.check_lima_installed()


class TestStackPlugin:
    """Tests for StackPlugin class."""

    def test_loads_valid_stack(self, lima_spk):
        # The 'static' stack should exist
        plugin = lima_spk.StackPlugin("static")
        assert plugin._plugin_name == "static"

    def test_raises_for_invalid_stack(self, lima_spk):
        with pytest.raises(Exception) as exc_info:
            lima_spk.StackPlugin("nonexistent_stack")
        assert "No stack plugin" in str(exc_info.value)

    def test_plugin_file_returns_correct_path(self, lima_spk):
        plugin = lima_spk.StackPlugin("static")
        path = plugin.plugin_file("setup.sh")
        assert path.endswith("stacks/static/setup.sh")
        assert os.path.exists(path)

    def test_init_args_returns_string(self, lima_spk):
        """Verify init_args returns a string (may be empty or contain args)."""
        plugin = lima_spk.StackPlugin("static")
        args = plugin.init_args()
        assert isinstance(args, str)

    def test_init_args_returns_empty_for_stack_without_initargs_file(self, lima_spk, tmp_path, monkeypatch):
        """Verify init_args returns empty string when no initargs file exists."""
        # Create a minimal stack without initargs
        stacks_dir = tmp_path / "stacks" / "test-stack"
        stacks_dir.mkdir(parents=True)
        (stacks_dir / "setup.sh").write_text("#!/bin/bash")
        (stacks_dir / "launcher.sh").write_text("#!/bin/bash")

        monkeypatch.setattr(lima_spk, 'CODE_DIR', str(tmp_path))

        plugin = lima_spk.StackPlugin("test-stack")
        args = plugin.init_args()
        assert args == ""


class TestPack:
    """Tests for pack function."""

    @pytest.fixture
    def setup_pack_env(self, lima_spk, tmp_path, monkeypatch, fp):
        """Set up environment for pack tests."""
        # Create .sandstorm directory with lima.yaml
        sandstorm_dir = tmp_path / ".sandstorm"
        sandstorm_dir.mkdir()
        (sandstorm_dir / "lima.yaml").write_text("# lima config")
        (sandstorm_dir / "sandstorm-pkgdef.capnp").write_text("# pkgdef")

        # Create a fake output package file that the "VM" would produce
        (tmp_path / "sandstorm-package.spk").write_bytes(b"fake spk content")

        # Mock limactl list to show running instance
        instance_name = lima_spk.get_lima_instance_name(str(tmp_path))
        fp.register_subprocess(
            ["limactl", "list", "--json"],
            stdout=f'{{"name": "{instance_name}", "status": "Running"}}\n'
        )

        # Mock limactl shell command
        fp.register_subprocess(
            ["limactl", "shell", fp.any()],
            returncode=0
        )

        return tmp_path, instance_name

    def test_pack_exits_without_output_file(self, lima_spk, tmp_path):
        args = SimpleNamespace(
            command_specific_args=[],
            work_directory=str(tmp_path)
        )

        with pytest.raises(SystemExit) as exc_info:
            lima_spk.pack(args)
        assert exc_info.value.code == 1

    def test_pack_checks_dot_sandstorm(self, lima_spk, tmp_path):
        args = SimpleNamespace(
            command_specific_args=["output.spk"],
            work_directory=str(tmp_path)
        )

        # No .sandstorm directory
        with pytest.raises(SystemExit):
            lima_spk.pack(args)

    def test_pack_requires_running_vm(self, lima_spk, tmp_path, fp):
        # Create .sandstorm directory
        sandstorm_dir = tmp_path / ".sandstorm"
        sandstorm_dir.mkdir()
        (sandstorm_dir / "lima.yaml").write_text("# lima config")

        # Mock limactl list to show stopped instance
        instance_name = lima_spk.get_lima_instance_name(str(tmp_path))
        fp.register_subprocess(
            ["limactl", "list", "--json"],
            stdout=f'{{"name": "{instance_name}", "status": "Stopped"}}\n'
        )

        args = SimpleNamespace(
            command_specific_args=["output.spk"],
            work_directory=str(tmp_path)
        )

        with pytest.raises(SystemExit):
            lima_spk.pack(args)

    def test_pack_moves_output_file(self, lima_spk, setup_pack_env, fp):
        tmp_path, instance_name = setup_pack_env
        output_file = tmp_path / "my-app.spk"

        args = SimpleNamespace(
            command_specific_args=[str(output_file)],
            work_directory=str(tmp_path)
        )

        lima_spk.pack(args)

        assert output_file.exists()
        assert output_file.read_bytes() == b"fake spk content"


class TestVerify:
    """Tests for verify function."""

    def test_verify_exits_without_spk_file(self, lima_spk, tmp_path):
        args = SimpleNamespace(
            command_specific_args=[],
            work_directory=str(tmp_path)
        )

        with pytest.raises(SystemExit) as exc_info:
            lima_spk.verify(args)
        assert exc_info.value.code == 1

    def test_verify_checks_dot_sandstorm(self, lima_spk, tmp_path):
        args = SimpleNamespace(
            command_specific_args=["test.spk"],
            work_directory=str(tmp_path)
        )

        with pytest.raises(SystemExit):
            lima_spk.verify(args)

    def test_verify_copies_and_removes_temp_file(self, lima_spk, tmp_path, fp):
        # Create .sandstorm directory
        sandstorm_dir = tmp_path / ".sandstorm"
        sandstorm_dir.mkdir()
        (sandstorm_dir / "lima.yaml").write_text("# lima config")

        # Create source spk file with specific content
        spk_file = tmp_path / "test.spk"
        spk_file.write_bytes(b"spk content for verification")

        temp_spk = sandstorm_dir / "test.spk"
        copy_verified = {"copied": False}

        # Mock limactl
        instance_name = lima_spk.get_lima_instance_name(str(tmp_path))
        fp.register_subprocess(
            ["limactl", "list", "--json"],
            stdout=f'{{"name": "{instance_name}", "status": "Running"}}\n'
        )

        def verify_copy_exists(process):
            # Verify the temp file exists and has correct content when command runs
            if temp_spk.exists() and temp_spk.read_bytes() == b"spk content for verification":
                copy_verified["copied"] = True

        fp.register_subprocess(
            ["limactl", "shell", fp.any()],
            returncode=0,
            callback=verify_copy_exists
        )

        args = SimpleNamespace(
            command_specific_args=[str(spk_file)],
            work_directory=str(tmp_path)
        )

        lima_spk.verify(args)

        # Verify the file was actually copied before the command ran
        assert copy_verified["copied"], "Temp file was not copied before running verify command"
        # Temp file should be removed after
        assert not temp_spk.exists(), "Temp file was not cleaned up"

    def test_verify_removes_temp_file_on_failure(self, lima_spk, tmp_path, fp):
        """Verify temp file cleanup happens even when the command fails."""
        sandstorm_dir = tmp_path / ".sandstorm"
        sandstorm_dir.mkdir()
        (sandstorm_dir / "lima.yaml").write_text("# lima config")

        spk_file = tmp_path / "test.spk"
        spk_file.write_bytes(b"spk content")

        instance_name = lima_spk.get_lima_instance_name(str(tmp_path))
        fp.register_subprocess(
            ["limactl", "list", "--json"],
            stdout=f'{{"name": "{instance_name}", "status": "Running"}}\n'
        )
        # Make the shell command fail
        fp.register_subprocess(
            ["limactl", "shell", fp.any()],
            returncode=1
        )

        args = SimpleNamespace(
            command_specific_args=[str(spk_file)],
            work_directory=str(tmp_path)
        )

        # The command should raise due to failure, but cleanup should still happen
        with pytest.raises(Exception):
            lima_spk.verify(args)

        temp_spk = sandstorm_dir / "test.spk"
        assert not temp_spk.exists(), "Temp file was not cleaned up after failure"


class TestPublish:
    """Tests for publish function."""

    def test_publish_exits_without_spk_file(self, lima_spk, tmp_path):
        args = SimpleNamespace(
            command_specific_args=[],
            work_directory=str(tmp_path)
        )

        with pytest.raises(SystemExit) as exc_info:
            lima_spk.publish(args)
        assert exc_info.value.code == 1

    def test_publish_checks_dot_sandstorm(self, lima_spk, tmp_path):
        args = SimpleNamespace(
            command_specific_args=["test.spk"],
            work_directory=str(tmp_path)
        )

        with pytest.raises(SystemExit):
            lima_spk.publish(args)

    def test_publish_copies_and_removes_temp_file(self, lima_spk, tmp_path, fp):
        # Create .sandstorm directory
        sandstorm_dir = tmp_path / ".sandstorm"
        sandstorm_dir.mkdir()
        (sandstorm_dir / "lima.yaml").write_text("# lima config")

        # Create source spk file with specific content
        spk_file = tmp_path / "test.spk"
        spk_file.write_bytes(b"spk content for publishing")

        temp_spk = sandstorm_dir / "test.spk"
        copy_verified = {"copied": False}

        # Mock limactl
        instance_name = lima_spk.get_lima_instance_name(str(tmp_path))
        fp.register_subprocess(
            ["limactl", "list", "--json"],
            stdout=f'{{"name": "{instance_name}", "status": "Running"}}\n'
        )

        def verify_copy_exists(process):
            if temp_spk.exists() and temp_spk.read_bytes() == b"spk content for publishing":
                copy_verified["copied"] = True

        fp.register_subprocess(
            ["limactl", "shell", fp.any()],
            returncode=0,
            callback=verify_copy_exists
        )

        args = SimpleNamespace(
            command_specific_args=[str(spk_file)],
            work_directory=str(tmp_path)
        )

        lima_spk.publish(args)

        assert copy_verified["copied"], "Temp file was not copied before running publish command"
        assert not temp_spk.exists(), "Temp file was not cleaned up"

    def test_publish_removes_temp_file_on_failure(self, lima_spk, tmp_path, fp):
        """Verify temp file cleanup happens even when the command fails."""
        sandstorm_dir = tmp_path / ".sandstorm"
        sandstorm_dir.mkdir()
        (sandstorm_dir / "lima.yaml").write_text("# lima config")

        spk_file = tmp_path / "test.spk"
        spk_file.write_bytes(b"spk content")

        instance_name = lima_spk.get_lima_instance_name(str(tmp_path))
        fp.register_subprocess(
            ["limactl", "list", "--json"],
            stdout=f'{{"name": "{instance_name}", "status": "Running"}}\n'
        )
        fp.register_subprocess(
            ["limactl", "shell", fp.any()],
            returncode=1
        )

        args = SimpleNamespace(
            command_specific_args=[str(spk_file)],
            work_directory=str(tmp_path)
        )

        with pytest.raises(Exception):
            lima_spk.publish(args)

        temp_spk = sandstorm_dir / "test.spk"
        assert not temp_spk.exists(), "Temp file was not cleaned up after failure"


class TestKeygen:
    """Tests for keygen function."""

    def test_keygen_checks_dot_sandstorm(self, lima_spk, tmp_path):
        args = SimpleNamespace(
            command_specific_args=[],
            work_directory=str(tmp_path)
        )

        with pytest.raises(SystemExit):
            lima_spk.keygen(args)

    def test_keygen_requires_running_vm(self, lima_spk, tmp_path, fp):
        sandstorm_dir = tmp_path / ".sandstorm"
        sandstorm_dir.mkdir()
        (sandstorm_dir / "lima.yaml").write_text("# lima config")

        instance_name = lima_spk.get_lima_instance_name(str(tmp_path))
        fp.register_subprocess(
            ["limactl", "list", "--json"],
            stdout=f'{{"name": "{instance_name}", "status": "Stopped"}}\n'
        )

        args = SimpleNamespace(
            command_specific_args=[],
            work_directory=str(tmp_path)
        )

        with pytest.raises(SystemExit):
            lima_spk.keygen(args)

    def test_keygen_calls_spk_command(self, lima_spk, tmp_path, fp):
        sandstorm_dir = tmp_path / ".sandstorm"
        sandstorm_dir.mkdir()
        (sandstorm_dir / "lima.yaml").write_text("# lima config")

        instance_name = lima_spk.get_lima_instance_name(str(tmp_path))
        fp.register_subprocess(
            ["limactl", "list", "--json"],
            stdout=f'{{"name": "{instance_name}", "status": "Running"}}\n'
        )
        fp.register_subprocess(
            ["limactl", "shell", fp.any()],
            returncode=0
        )

        args = SimpleNamespace(
            command_specific_args=[],
            work_directory=str(tmp_path)
        )

        lima_spk.keygen(args)  # Should not raise

    def test_keygen_passes_extra_args(self, lima_spk, tmp_path, fp, mocker):
        sandstorm_dir = tmp_path / ".sandstorm"
        sandstorm_dir.mkdir()
        (sandstorm_dir / "lima.yaml").write_text("# lima config")

        instance_name = lima_spk.get_lima_instance_name(str(tmp_path))
        fp.register_subprocess(
            ["limactl", "list", "--json"],
            stdout=f'{{"name": "{instance_name}", "status": "Running"}}\n'
        )

        # Track the command that was called
        mock_call = mocker.patch.object(lima_spk, 'call_spk_command')

        args = SimpleNamespace(
            command_specific_args=["--app-id", "abc123"],
            work_directory=str(tmp_path)
        )

        lima_spk.keygen(args)

        mock_call.assert_called_once()
        # call_spk_command(instance_name, spk_subcommand, extra_args)
        call_args, call_kwargs = mock_call.call_args
        assert call_args[1] == "keygen"  # spk_subcommand
        assert "--app-id" in call_args[2]  # extra_args
        assert "abc123" in call_args[2]


class TestListkeys:
    """Tests for listkeys function."""

    def test_listkeys_checks_dot_sandstorm(self, lima_spk, tmp_path):
        args = SimpleNamespace(
            command_specific_args=[],
            work_directory=str(tmp_path)
        )

        with pytest.raises(SystemExit):
            lima_spk.listkeys(args)

    def test_listkeys_requires_running_vm(self, lima_spk, tmp_path, fp):
        sandstorm_dir = tmp_path / ".sandstorm"
        sandstorm_dir.mkdir()
        (sandstorm_dir / "lima.yaml").write_text("# lima config")

        instance_name = lima_spk.get_lima_instance_name(str(tmp_path))
        fp.register_subprocess(
            ["limactl", "list", "--json"],
            stdout=f'{{"name": "{instance_name}", "status": "Stopped"}}\n'
        )

        args = SimpleNamespace(
            command_specific_args=[],
            work_directory=str(tmp_path)
        )

        with pytest.raises(SystemExit):
            lima_spk.listkeys(args)

    def test_listkeys_calls_spk_command(self, lima_spk, tmp_path, fp, mocker):
        sandstorm_dir = tmp_path / ".sandstorm"
        sandstorm_dir.mkdir()
        (sandstorm_dir / "lima.yaml").write_text("# lima config")

        instance_name = lima_spk.get_lima_instance_name(str(tmp_path))
        fp.register_subprocess(
            ["limactl", "list", "--json"],
            stdout=f'{{"name": "{instance_name}", "status": "Running"}}\n'
        )

        mock_call = mocker.patch.object(lima_spk, 'call_spk_command')

        args = SimpleNamespace(
            command_specific_args=[],
            work_directory=str(tmp_path)
        )

        lima_spk.listkeys(args)

        mock_call.assert_called_once()
        call_args, call_kwargs = mock_call.call_args
        assert call_args[0] == instance_name  # instance_name
        assert call_args[1] == "listkeys"  # spk_subcommand


class TestGetkey:
    """Tests for getkey function."""

    def test_getkey_exits_without_key_id(self, lima_spk, tmp_path):
        args = SimpleNamespace(
            command_specific_args=[],
            work_directory=str(tmp_path)
        )

        with pytest.raises(SystemExit) as exc_info:
            lima_spk.getkey(args)
        assert exc_info.value.code == 1

    def test_getkey_checks_dot_sandstorm(self, lima_spk, tmp_path):
        args = SimpleNamespace(
            command_specific_args=["some-key-id"],
            work_directory=str(tmp_path)
        )

        with pytest.raises(SystemExit):
            lima_spk.getkey(args)

    def test_getkey_requires_running_vm(self, lima_spk, tmp_path, fp):
        sandstorm_dir = tmp_path / ".sandstorm"
        sandstorm_dir.mkdir()
        (sandstorm_dir / "lima.yaml").write_text("# lima config")

        instance_name = lima_spk.get_lima_instance_name(str(tmp_path))
        fp.register_subprocess(
            ["limactl", "list", "--json"],
            stdout=f'{{"name": "{instance_name}", "status": "Stopped"}}\n'
        )

        args = SimpleNamespace(
            command_specific_args=["some-key-id"],
            work_directory=str(tmp_path)
        )

        with pytest.raises(SystemExit):
            lima_spk.getkey(args)

    def test_getkey_calls_spk_command_with_key_id(self, lima_spk, tmp_path, fp, mocker):
        sandstorm_dir = tmp_path / ".sandstorm"
        sandstorm_dir.mkdir()
        (sandstorm_dir / "lima.yaml").write_text("# lima config")

        instance_name = lima_spk.get_lima_instance_name(str(tmp_path))
        fp.register_subprocess(
            ["limactl", "list", "--json"],
            stdout=f'{{"name": "{instance_name}", "status": "Running"}}\n'
        )

        mock_call = mocker.patch.object(lima_spk, 'call_spk_command')

        args = SimpleNamespace(
            command_specific_args=["abc123xyz"],
            work_directory=str(tmp_path)
        )

        lima_spk.getkey(args)

        mock_call.assert_called_once()
        call_args, call_kwargs = mock_call.call_args
        assert call_args[0] == instance_name  # instance_name
        assert call_args[1] == "getkey"  # spk_subcommand
        # The key_id should be in the extra_args (quoted via shlex.quote)
        assert "abc123xyz" in call_args[2]
