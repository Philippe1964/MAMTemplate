# Template Python 3.14 — Architecture 4 Couches & Docker 3-Tiers (`MAMTemplate`)

Ce dépôt sert de **template de référence** pour démarrer un projet Python 3.14+ avec :
- **Environnement & Qualité** : `uv`, `ruff` (lint + format), `mypy` (mode `strict`), `pytest` (`pytest-asyncio`, `pytest-cov`).
- **Stack Applicative** : `FastAPI`, `Pydantic v2`, `pydantic-settings`, `SQLAlchemy 2.0 (AsyncSession)`, `asyncpg` & `aiosqlite`.
- **Hébergement Conteneurisé 3-Tiers (`compose.yaml` & `docker/`)** :
  - `<projet>-presentation` : Application **React 19 / TypeScript / Vite** & Reverse Proxy **Nginx 1.27 Alpine** (`docker/presentation/`).
  - `<projet>-business` : API **Python 3.14 Alpine / FastAPI** en build multi-stage durci (0 CVE, `apk upgrade`, non-root) avec `uv` (`docker/business/`).
  - `<projet>-data` : Base de données relationnelle **PostgreSQL 17 Alpine** isolée sur réseau interne (`docker/data/`).
  - **Pipeline CI/CD** : Workflow GitHub Actions (`.github/workflows/ci-docker.yml`) exécutant Ruff, Mypy, Pytest puis le build et le test de santé des 3 conteneurs.
- **Skills & Règles IA embarqués (`.agents/skills/` & `AGENTS.md`)** :
  - [`python-layer-architecture`](.agents/skills/python-layer-architecture/SKILL.md) : Architecture 4 couches (`presentation`, `application`, `domain`, `infrastructure`), DDD, OWASP, stratégie de tests par couche.
  - [`python-expert-dev`](.agents/skills/python-expert-dev/SKILL.md) : Bonnes pratiques Python 3.14+, idiomes PEP 695 et configuration outillage.
  - [`typescript-vite-expert`](.agents/skills/typescript-vite-expert/SKILL.md) : Développement expert JavaScript / TypeScript 5.7+ / React 19 / Vite 6+, typage strict et intégration SPA Nginx.
  - [`security-cve-hardening`](.agents/skills/security-cve-hardening/SKILL.md) : Remédiation des CVE Docker/Python/NPM, durcissement Alpine, conformité OWASP Top 10 et interdiction des mauvaises pratiques de codage.
  - [`cloud-native-scalability`](.agents/skills/cloud-native-scalability/SKILL.md) : Scalabilité horizontale 12-Factor, statelessness, `lifespan` Graceful Shutdown (`SIGTERM`), sondes `/health/live` & `/health/ready` et calibrage du pool SQLAlchemy multi-réplicas.
  - [`cloud-native-resilience`](.agents/skills/cloud-native-resilience/SKILL.md) : Tolérance aux pannes, résilience aux failovers de BDD managée (`pool_pre_ping`, `pool_recycle`), timeouts stricts, `proxy_next_upstream` Nginx et `ErrorBoundary` React 19.
  - [`cloud-native-observability`](.agents/skills/cloud-native-observability/SKILL.md) : Corrélation de bout-en-bout (`X-Request-ID`) et logs structurés JSON sur `stdout`.

---

## Réutiliser ce template pour un nouveau projet

### Option A — Générer un nouveau projet dans un nouveau dossier (Recommandé)
Depuis ce dossier, exécutez le script de génération en indiquant le nom du nouveau projet et son dossier de destination :

```powershell
uv run python scripts/init_from_template.py --name "MonNouveauProjet" --target "E:\SourceCode\MonNouveauProjet"
```

Ce script effectue automatiquement :
1. La copie propre de toute la structure (`.agents/skills/`, `.vscode/`, `docker/`, `.github/workflows/`, `compose.yaml`, `AGENTS.md`, `src/`, `tests/`, `pyproject.toml`).
2. Le renommage du package `src/mamtemplate` en `src/mon_nouveau_projet` et la mise à jour de tous les imports, tests et fichiers de configuration.
3. Le renommage automatique des 3 conteneurs Docker :
   - `monnouveauprojet-presentation`
   - `monnouveauprojet-business`
   - `monnouveauprojet-data`
4. La création automatique du nouvel environnement virtuel Python 3.14 (`uv venv --python 3.14`), l'installation des dépendances (`uv sync`) et l'initialisation Git (`git init`).

---

## Déploiement Docker 3-Tiers & Application de Health Checking

### Architecture des conteneurs
| Tiers | Nom du conteneur | Technologie | Rôle & Réseau |
| :--- | :--- | :--- | :--- |
| **Presentation** | `<projet>-presentation` | React 19 (TypeScript/Vite) + Nginx 1.27 Alpine | Sert l'application web React sur `/health-check` et agit en Reverse Proxy HTTP exposé sur le port `8080` (`presentation_net`). |
| **Business** | `<projet>-business` | Python 3.14 + FastAPI (`uv`, `psutil`, `httpx`) | Exécute la logique applicative 4 couches et l'orchestration du diagnostic 3-tiers sur le port interne `8000` (`presentation_net` + `data_net`). |
| **Data** | `<projet>-data` | PostgreSQL 17 Alpine | Persistance des données et sonde système SQL sur le port interne `5432` (réseau isolé `data_net`, non exposé sur l'hôte). |

### URLs de Health Checking (sans authentification)
- **Tableau de bord Web React (Navigateur)** : [`http://localhost:8080/health-check`](http://localhost:8080/health-check)
  - Affiche la chaîne de liaison complète (`Navigateur Client` ➔ `Tiers 1 Presentation` ➔ `Tiers 2 Business` ➔ `Tiers 3 Data`), les latences par saut et toutes les caractéristiques **Hardware** (CPU, cœurs, charge %, RAM utilisée/totale, Disque utilisé/total) et **Software** (Hostname, OS, Kernel, Architecture, Uptime, versions logicielles) de chaque tiers.
- **API JSON de diagnostic 3-Tiers** : [`http://localhost:8080/api/health-check`](http://localhost:8080/api/health-check)
- **Sonde légère de vivacité (Docker Healthcheck)** : [`http://localhost:8080/health`](http://localhost:8080/health)

### Commandes Docker Compose
- **Construire et démarrer les 3 conteneurs en arrière-plan (avec attente des healthchecks)** :
  ```powershell
  docker compose up -d --build --wait
  ```
- **Vérifier l'état des 3 conteneurs** :
  ```powershell
  docker ps --filter "name=mamtemplate-"
  ```
- **Tester l'API 3-tiers complète à travers le conteneur Presentation** :
  ```powershell
  curl http://localhost:8080/api/health-check
  ```
- **Arrêter les conteneurs** :
  ```powershell
  docker compose down
  ```

---

## Commandes de développement local (hors Docker)

- **Synchroniser l'environnement virtuel** : `uv sync`
- **Démarrer le serveur FastAPI en local** : `uv run uvicorn mamtemplate.presentation.api.app:app --reload`
- **Exécuter les tests et la couverture** : `uv run pytest -v --cov`
- **Vérifier le typage statique (`mypy`)** : `uv run mypy .`
- **Vérifier et formater le code (`ruff`)** : `uv run ruff check --fix . && uv run ruff format .`
