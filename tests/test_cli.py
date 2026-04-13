"""Tests for CLI commands."""

from __future__ import annotations

from click.testing import CliRunner

from psgc.cli.main import cli


class TestCLI:
    def setup_method(self):
        self.runner = CliRunner()

    def test_version(self):
        result = self.runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "psgc" in result.output

    def test_info_version(self):
        result = self.runner.invoke(cli, ["info", "version"])
        assert result.exit_code == 0
        assert "psgc" in result.output
        assert "PSGC" in result.output

    def test_info_stats(self):
        result = self.runner.invoke(cli, ["info", "stats"])
        assert result.exit_code == 0
        assert "Regions" in result.output
        assert "Barangays" in result.output

    def test_search(self):
        result = self.runner.invoke(cli, ["search", "Manila"])
        assert result.exit_code == 0
        assert "Manila" in result.output

    def test_search_with_limit(self):
        result = self.runner.invoke(cli, ["search", "Manila", "-n", "2"])
        assert result.exit_code == 0

    def test_suggest(self):
        result = self.runner.invoke(cli, ["suggest", "mak"])
        assert result.exit_code == 0
        assert any("mak" in line.lower() for line in result.output.splitlines() if line.strip())

    def test_validate_valid(self):
        from psgc._loader import get_store
        code = get_store().barangays[0].psgc_code
        result = self.runner.invoke(cli, ["validate", code])
        assert result.exit_code == 0
        assert "Valid" in result.output

    def test_validate_invalid(self):
        result = self.runner.invoke(cli, ["validate", "0000000000"])
        assert result.exit_code == 0
        assert "Invalid" in result.output

    def test_zip(self):
        result = self.runner.invoke(cli, ["zip", "1000"])
        assert result.exit_code == 0
        assert "Ermita" in result.output

    def test_parse(self):
        result = self.runner.invoke(cli, ["parse", "Brgy. San Antonio, Makati City"])
        assert result.exit_code == 0
        assert "San Antonio" in result.output

    def test_export_json(self):
        result = self.runner.invoke(cli, ["export", "--format", "json", "--level", "region"])
        assert result.exit_code == 0
        assert "psgc_code" in result.output

    def test_export_csv(self):
        result = self.runner.invoke(cli, ["export", "--format", "csv", "--level", "region"])
        assert result.exit_code == 0
        assert "psgc_code" in result.output

    def test_distance(self):
        result = self.runner.invoke(cli, ["distance", "Ermita, Manila", "Intramuros, Manila"])
        assert result.exit_code == 0
        assert "km" in result.output
