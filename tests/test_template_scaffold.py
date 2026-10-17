"""Unit tests for the template scaffolding script."""

from pathlib import Path

import pytest
from scripts.init_from_template import (
    normalize_container_prefix,
    normalize_package_name,
    scaffold_project,
)


@pytest.mark.parametrize(
    ("raw_name", "expected_pkg"),
    [
        ("MonProjetAPI", "monprojetapi"),
        ("Mon-Projet-API", "mon_projet_api"),
        ("  Client Billing 2026 ", "client_billing_2026"),
    ],
)
def test_normalize_package_name_valid(raw_name: str, expected_pkg: str) -> None:
    """Verify valid project names are normalized to snake_case identifiers."""
    assert normalize_package_name(raw_name) == expected_pkg


@pytest.mark.parametrize(
    ("raw_name", "expected_prefix"),
    [
        ("SampleProject", "sampleproject"),
        ("Mon-Projet_API", "mon-projet-api"),
        ("  Client Billing 2026 ", "client-billing-2026"),
    ],
)
def test_normalize_container_prefix_valid(raw_name: str, expected_prefix: str) -> None:
    """Verify valid project names are normalized to lowercase hyphenated Docker prefixes."""
    assert normalize_container_prefix(raw_name) == expected_prefix


def test_normalize_package_name_invalid_raises() -> None:
    """Verify invalid project names starting with digits or empty raise ValueError."""
    with pytest.raises(ValueError, match="Impossible de générer"):
        normalize_package_name("123-invalid")


def test_scaffold_project_creates_renamed_structure_and_docker_tiers(tmp_path: Path) -> None:
    """Verify scaffold_project copies template, renames package, and updates 3-tier Docker files."""
    template_root = Path(__file__).resolve().parent.parent
    target_dir = tmp_path / "BillingService"

    pkg_dir = scaffold_project(
        template_root=template_root,
        target_dir=target_dir,
        project_name="BillingService",
        package_name="billing_service",
    )

    assert pkg_dir == target_dir / "src" / "billing_service"
    assert pkg_dir.is_dir()
    assert not (target_dir / "src" / "mamtemplate").exists()
    assert (target_dir / ".agents" / "skills" / "python-layer-architecture" / "SKILL.md").is_file()
    assert (target_dir / ".agents" / "skills" / "ddd-strategic-design" / "SKILL.md").is_file()
    assert (target_dir / ".agents" / "skills" / "ddd-tactical-patterns" / "SKILL.md").is_file()
    assert (target_dir / ".agents" / "skills" / "python-expert-dev" / "SKILL.md").is_file()
    assert (target_dir / ".agents" / "skills" / "typescript-vite-expert" / "SKILL.md").is_file()
    assert (target_dir / ".agents" / "skills" / "security-cve-hardening" / "SKILL.md").is_file()
    assert (target_dir / ".agents" / "skills" / "cloud-native-scalability" / "SKILL.md").is_file()
    assert (target_dir / ".agents" / "skills" / "cloud-native-resilience" / "SKILL.md").is_file()
    assert (target_dir / ".agents" / "skills" / "cloud-native-observability" / "SKILL.md").is_file()

    pyproject_content = (target_dir / "pyproject.toml").read_text(encoding="utf-8")
    assert 'name = "billing_service"' in pyproject_content

    router_content = (
        target_dir / "src" / "billing_service" / "presentation" / "health" / "health_router.py"
    ).read_text(encoding="utf-8")
    assert "from billing_service.application.health.health_service import" in router_content

    compose_content = (target_dir / "compose.yaml").read_text(encoding="utf-8")
    assert "image: billingservice-presentation:latest" in compose_content
    assert "image: billingservice-business:latest" in compose_content
    assert "image: billingservice-data:latest" in compose_content
    assert "- billingservice-presentation" in compose_content
    assert "- billingservice-business" in compose_content
    assert "- billingservice-data" in compose_content

    nginx_content = (target_dir / "docker" / "presentation" / "nginx.conf").read_text(
        encoding="utf-8"
    )
    assert "server billingservice-business:8000" in nginx_content

    business_dockerfile = (target_dir / "docker" / "business" / "Dockerfile").read_text(
        encoding="utf-8"
    )
    assert '"billing_service.presentation.api.app:app"' in business_dockerfile

    frontend_health_page = (
        target_dir / "frontend" / "src" / "pages" / "HealthCheckPage.tsx"
    ).read_text(encoding="utf-8")
    assert "billingservice-presentation" in frontend_health_page
    assert "billingservice-business" in frontend_health_page
    assert "billingservice-data" in frontend_health_page

    frontend_home_page = (
        target_dir / "frontend" / "src" / "pages" / "ApplicationHomePage.tsx"
    ).read_text(encoding="utf-8")
    assert "billingservice-presentation" in frontend_home_page
    assert "billingservice-business" in frontend_home_page
    assert "billingservice-data" in frontend_home_page
