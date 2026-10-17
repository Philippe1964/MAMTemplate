"""Script d'initialisation de projet à partir du template Python 3.14 / Architecture 4 couches."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
from pathlib import Path

TEMPLATE_PROJECT_NAME = "MAMTemplate"
TEMPLATE_PACKAGE_NAME = "mamtemplate"
TEMPLATE_CONTAINER_PREFIX = "mamtemplate"

EXCLUDED_DIRS = {
    ".venv",
    ".git",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "htmlcov",
    "dist",
    "build",
    "node_modules",
}

EXCLUDED_FILES = {
    "uv.lock",
    ".coverage",
}

TEXT_EXTENSIONS = {
    ".py",
    ".toml",
    ".md",
    ".json",
    ".yaml",
    ".yml",
    ".ini",
    ".cfg",
    ".env",
    ".example",
    ".gitignore",
    ".dockerignore",
    ".conf",
    ".sql",
    ".sh",
    ".ps1",
    ".ts",
    ".tsx",
    ".html",
    ".css",
}

TEXT_FILENAMES = {
    ".gitignore",
    ".dockerignore",
    "Dockerfile",
}


def normalize_package_name(project_name: str) -> str:
    """Convertit un nom de projet en identifiant de package Python valide (snake_case).

    Args:
        project_name: Le nom du projet (ex. 'Mon-Projet-API').

    Returns:
        Le nom de package normalisé (ex. 'mon_projet_api').

    Raises:
        ValueError: Si le nom normalisé n'est pas un identifiant Python valide.
    """
    cleaned = re.sub(r"[^a-zA-Z0-9_]+", "_", project_name.strip()).strip("_").lower()
    if not cleaned or cleaned[0].isdigit() or not cleaned.isidentifier():
        msg = f"Impossible de générer un nom de package Python valide depuis '{project_name}'."
        raise ValueError(msg)
    return cleaned


def normalize_container_prefix(project_name: str) -> str:
    """Convertit un nom de projet en préfixe Docker valide en minuscules (kebab-case).

    Args:
        project_name: Le nom du projet (ex. 'MonProjet_API' ou 'Client Billing').

    Returns:
        Le préfixe de conteneur normalisé (ex. 'monprojet-api' ou 'client-billing').

    Raises:
        ValueError: Si le préfixe généré est vide.
    """
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", project_name.strip()).strip("-").lower()
    if not cleaned:
        msg = (
            f"Impossible de générer un préfixe de conteneur Docker valide depuis '{project_name}'."
        )
        raise ValueError(msg)
    return cleaned


def replace_tokens_in_text(
    content: str,
    project_name: str,
    package_name: str,
    container_prefix: str,
    template_root: Path,
    target_root: Path,
) -> str:
    """Remplace les références du template par celles du nouveau projet.

    Args:
        content: Le contenu texte original.
        project_name: Le nom d'affichage du projet.
        package_name: Le nom du package Python (snake_case).
        container_prefix: Le préfixe Docker pour les conteneurs (<prefix>-presentation, etc.).
        template_root: Le chemin absolu du dossier template source.
        target_root: Le chemin absolu du dossier cible.

    Returns:
        Le contenu texte mis à jour.
    """
    template_posix = template_root.resolve().as_posix()
    target_posix = target_root.resolve().as_posix()
    updated = content.replace(template_posix, target_posix)
    updated = updated.replace(template_posix.lower(), target_posix)
    updated = updated.replace(str(template_root.resolve()), str(target_root.resolve()))

    # Remplacement spécifique des identifiants Docker (<projet>-<tiers> et réseaux/volumes)
    for suffix in (
        "-presentation-net",
        "-data-net",
        "-presentation",
        "-business",
        "-data",
        "-pgdata",
    ):
        updated = updated.replace(
            f"{TEMPLATE_CONTAINER_PREFIX}{suffix}",
            f"{container_prefix}{suffix}",
        )
    updated = updated.replace(
        f"name: {TEMPLATE_CONTAINER_PREFIX}",
        f"name: {container_prefix}",
    )

    updated = updated.replace(TEMPLATE_PROJECT_NAME, project_name)
    return updated.replace(TEMPLATE_PACKAGE_NAME, package_name)


def scaffold_project(
    template_root: Path,
    target_dir: Path,
    project_name: str,
    package_name: str | None = None,
    container_prefix: str | None = None,
) -> Path:
    """Crée ou renomme un projet à partir du template.

    Args:
        template_root: Répertoire racine du template actuel.
        target_dir: Répertoire de destination du nouveau projet.
        project_name: Nom du nouveau projet.
        package_name: Nom du package Python (calculé automatiquement si omis).
        container_prefix: Préfixe des conteneurs Docker (calculé automatiquement si omis).

    Returns:
        Le chemin du package Python créé sous src/<package_name>.
    """
    pkg = package_name or normalize_package_name(project_name)
    docker_prefix = container_prefix or normalize_container_prefix(project_name)
    resolved_template = template_root.resolve()
    resolved_target = target_dir.resolve()
    in_place = resolved_template == resolved_target

    if not in_place:
        resolved_target.mkdir(parents=True, exist_ok=True)
        for item in resolved_template.iterdir():
            if item.name in EXCLUDED_DIRS or item.name in EXCLUDED_FILES:
                continue
            dest = resolved_target / item.name
            if item.is_dir():
                shutil.copytree(
                    item,
                    dest,
                    dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns(
                        *EXCLUDED_DIRS,
                        *EXCLUDED_FILES,
                        "*.egg-info",
                    ),
                )
            else:
                shutil.copy2(item, dest)

    old_pkg_dir = resolved_target / "src" / TEMPLATE_PACKAGE_NAME
    new_pkg_dir = resolved_target / "src" / pkg
    if old_pkg_dir.exists() and old_pkg_dir != new_pkg_dir:
        old_pkg_dir.rename(new_pkg_dir)

    for file_path in resolved_target.rglob("*"):
        if not file_path.is_file():
            continue
        if any(part in EXCLUDED_DIRS for part in file_path.parts):
            continue
        if file_path.name == "init_from_template.py":
            raw_script = file_path.read_text(encoding="utf-8")
            updated_script = (
                raw_script.replace(
                    f'TEMPLATE_PROJECT_NAME = "{TEMPLATE_PROJECT_NAME}"',
                    f'TEMPLATE_PROJECT_NAME = "{project_name}"',
                )
                .replace(
                    f'TEMPLATE_PACKAGE_NAME = "{TEMPLATE_PACKAGE_NAME}"',
                    f'TEMPLATE_PACKAGE_NAME = "{pkg}"',
                )
                .replace(
                    f'TEMPLATE_CONTAINER_PREFIX = "{TEMPLATE_CONTAINER_PREFIX}"',
                    f'TEMPLATE_CONTAINER_PREFIX = "{docker_prefix}"',
                )
            )
            if updated_script != raw_script:
                file_path.write_text(updated_script, encoding="utf-8")
            continue
        if file_path.suffix in TEXT_EXTENSIONS or file_path.name in TEXT_FILENAMES:
            raw = file_path.read_text(encoding="utf-8")
            updated = replace_tokens_in_text(
                raw,
                project_name,
                pkg,
                docker_prefix,
                resolved_template,
                resolved_target,
            )
            if updated != raw:
                file_path.write_text(updated, encoding="utf-8")

    return new_pkg_dir


def main() -> None:
    """Point d'entrée CLI pour générer un nouveau projet depuis ce template."""
    parser = argparse.ArgumentParser(
        description=(
            "Génère un nouveau projet Python 3.14 (Architecture 4 couches & Docker 3-Tiers) "
            "depuis ce template."
        ),
    )
    parser.add_argument(
        "--name",
        required=True,
        help="Nom du nouveau projet (ex: 'FacturationAPI' ou 'mon-projet').",
    )
    parser.add_argument(
        "--target",
        required=True,
        help="Chemin du dossier cible (ou '.' pour renommer le projet courant sur place).",
    )
    parser.add_argument(
        "--package",
        default=None,
        help="Nom du package Python dans src/ (par défaut déduit de --name en snake_case).",
    )
    parser.add_argument(
        "--no-venv",
        action="store_true",
        help="Ne pas lancer automatiquement 'uv venv' et 'uv sync' dans le nouveau projet.",
    )
    args = parser.parse_args()

    template_root = Path(__file__).resolve().parent.parent
    target_dir = Path(args.target).resolve()
    pkg = args.package or normalize_package_name(args.name)

    scaffold_project(
        template_root=template_root,
        target_dir=target_dir,
        project_name=args.name,
        package_name=pkg,
    )

    if not args.no_venv:
        clean_env = os.environ.copy()
        clean_env.pop("VIRTUAL_ENV", None)
        clean_env["UV_LINK_MODE"] = "copy"
        subprocess.run(
            ["uv", "venv", "--python", "3.14"],  # noqa: S607
            cwd=target_dir,
            env=clean_env,
            check=True,
        )
        subprocess.run(
            ["uv", "sync", "--link-mode=copy"],  # noqa: S607
            cwd=target_dir,
            env=clean_env,
            check=True,
        )
        frontend_target = target_dir / "frontend"
        template_node_modules = template_root / "frontend" / "node_modules"
        if frontend_target.is_dir() and not (frontend_target / "node_modules").exists():
            npm_bin = shutil.which("npm")
            if npm_bin is not None:
                subprocess.run(  # noqa: S603
                    [npm_bin, "install", "--no-audit", "--no-fund"],
                    cwd=frontend_target,
                    env=clean_env,
                    check=False,
                )
            elif template_node_modules.is_dir():
                shutil.copytree(
                    template_node_modules,
                    frontend_target / "node_modules",
                    dirs_exist_ok=True,
                )
        subprocess.run(
            ["git", "init"],  # noqa: S607
            cwd=target_dir,
            env=clean_env,
            check=False,
        )


if __name__ == "__main__":
    main()
