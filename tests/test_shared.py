"""Tests for functionality shared between lima-spk and vagrant-spk.

These tests use the parameterized `spk_script` fixture to run against both scripts.
"""

import pytest


class TestFormatShellGrainChoices:
    """Tests for format_shell_grain_choices function (shared by both scripts)."""

    def test_returns_string(self, spk_script):
        supervisors = [{"grain_id": "abc123"}]
        result = spk_script.format_shell_grain_choices(supervisors)
        assert isinstance(result, str)

    def test_includes_grain_id(self, spk_script):
        supervisors = [{"grain_id": "my-test-grain-id"}]
        result = spk_script.format_shell_grain_choices(supervisors)
        assert "my-test-grain-id" in result

    def test_includes_numbered_list(self, spk_script):
        supervisors = [
            {"grain_id": "grain-1"},
            {"grain_id": "grain-2"},
            {"grain_id": "grain-3"},
        ]
        result = spk_script.format_shell_grain_choices(supervisors)
        assert "1. grain-1" in result
        assert "2. grain-2" in result
        assert "3. grain-3" in result

    def test_includes_default_choice_hint(self, spk_script):
        supervisors = [{"grain_id": "abc123"}]
        result = spk_script.format_shell_grain_choices(supervisors)
        assert "[1]" in result

    def test_includes_instructions(self, spk_script):
        supervisors = [{"grain_id": "abc123"}]
        result = spk_script.format_shell_grain_choices(supervisors)
        assert "shell" in result.lower()
        assert "grain" in result.lower()

    def test_raises_on_empty_list(self, spk_script):
        with pytest.raises(AssertionError):
            spk_script.format_shell_grain_choices([])


class TestGitignoreContents:
    """Tests for GITIGNORE_CONTENTS constant (shared by both scripts)."""

    def test_ignores_log_files(self, spk_script):
        assert "*.log" in spk_script.GITIGNORE_CONTENTS


class TestGitattributesContents:
    """Tests for GITATTRIBUTES_CONTENTS constant (shared by both scripts)."""

    def test_sets_shell_scripts_to_lf(self, spk_script):
        assert "*.sh" in spk_script.GITATTRIBUTES_CONTENTS
        assert "eol=lf" in spk_script.GITATTRIBUTES_CONTENTS


class TestGlobalSetupScript:
    """Tests for GLOBAL_SETUP_SCRIPT constant (shared by both scripts)."""

    def test_is_bash_script(self, spk_script):
        assert spk_script.GLOBAL_SETUP_SCRIPT.startswith("#!/bin/bash")

    def test_uses_strict_mode(self, spk_script):
        assert "set -euo pipefail" in spk_script.GLOBAL_SETUP_SCRIPT

    def test_downloads_sandstorm_installer(self, spk_script):
        assert "install.sandstorm.io" in spk_script.GLOBAL_SETUP_SCRIPT

    def test_caches_sandstorm_package(self, spk_script):
        assert "/host-dot-sandstorm/caches" in spk_script.GLOBAL_SETUP_SCRIPT

    def test_configures_sandstorm_user(self, spk_script):
        # Both scripts should add 'vagrant' user to sandstorm group
        assert "vagrant" in spk_script.GLOBAL_SETUP_SCRIPT
        assert "sandstorm" in spk_script.GLOBAL_SETUP_SCRIPT


class TestStackPluginClass:
    """Tests for StackPlugin class (shared by both scripts)."""

    def test_exists_in_both_scripts(self, spk_script):
        assert hasattr(spk_script, "StackPlugin")

    def test_can_load_static_stack(self, spk_script):
        plugin = spk_script.StackPlugin("static")
        assert plugin._plugin_name == "static"

    def test_can_load_lemp_stack(self, spk_script):
        plugin = spk_script.StackPlugin("lemp")
        assert plugin._plugin_name == "lemp"

    def test_can_load_meteor_stack(self, spk_script):
        plugin = spk_script.StackPlugin("meteor")
        assert plugin._plugin_name == "meteor"

    def test_raises_for_nonexistent_stack(self, spk_script):
        with pytest.raises(Exception):
            spk_script.StackPlugin("this-stack-does-not-exist")

    def test_init_args_returns_string(self, spk_script):
        plugin = spk_script.StackPlugin("static")
        args = plugin.init_args()
        assert isinstance(args, str)


class TestEnsureHostSandstormFolderExists:
    """Tests for ensure_host_sandstorm_folder_exists function."""

    def test_function_exists(self, spk_script):
        assert hasattr(spk_script, "ensure_host_sandstorm_folder_exists")

    def test_creates_sandstorm_folder(self, spk_script, tmp_path, monkeypatch):
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setenv("HOME", str(home))

        # Update the module's view of the home directory
        if hasattr(spk_script, 'USER_SANDSTORM_DIR'):
            monkeypatch.setattr(spk_script, 'USER_SANDSTORM_DIR', str(home / ".sandstorm"))

        spk_script.ensure_host_sandstorm_folder_exists()

        assert (home / ".sandstorm").exists()
        assert (home / ".sandstorm" / "caches").exists()
