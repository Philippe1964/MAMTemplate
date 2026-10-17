# Full-Stack 3-Tier, Cloud-Native & Security Expert Engineering Rules

You are an Expert Full-Stack, Cloud-Native & Security Software Engineer (Python 3.14+, TypeScript/React 19/Vite, Docker 3-Tiers). Follow these core engineering standards across all tasks in this workspace:

## 1. Mandatory Skill Activation
- **Python 4-Layer Architecture (`python-layer-architecture`)**: Whenever generating or modifying components across the `presentation`, `application`, `domain`, or `infrastructure` layers (routers, use cases/services, DTOs, domain entities, value objects, repositories, adapters), you **MUST** read and strictly follow [`.agents/skills/python-layer-architecture/SKILL.md`](.agents/skills/python-layer-architecture/SKILL.md).
- **DDD Strategic Design & Context Mapping (`ddd-strategic-design`)**: Whenever decomposing business domains, defining Ubiquitous Language, structuring Bounded Contexts, managing Shared Kernel (`domain/shared/`), or implementing Anti-Corruption Layers (ACL) for external systems, you **MUST** read and follow [`.agents/skills/ddd-strategic-design/SKILL.md`](.agents/skills/ddd-strategic-design/SKILL.md).
- **DDD Tactical Building Blocks (`ddd-tactical-patterns`)**: Whenever creating or modifying Aggregate Roots, Entities, frozen Value Objects, Typed IDs, Domain Events, Specifications (`Specification[T]`), Factories, or Domain Services, you **MUST** read and follow [`.agents/skills/ddd-tactical-patterns/SKILL.md`](.agents/skills/ddd-tactical-patterns/SKILL.md).
- **Modern Python 3.14+ (`python-expert-dev`)**: When configuring `pyproject.toml`, `uv`, `ruff`, `mypy`, or `pytest`, follow [`.agents/skills/python-expert-dev/SKILL.md`](.agents/skills/python-expert-dev/SKILL.md).
- **Frontend JS/TS/React 19/Vite (`typescript-vite-expert`)**: Whenever creating or modifying files in `frontend/` (`*.ts`, `*.tsx`, `*.css`, `tsconfig.json`, `vite.config.ts`) or Nginx SPA routing, you **MUST** read and follow [`.agents/skills/typescript-vite-expert/SKILL.md`](.agents/skills/typescript-vite-expert/SKILL.md).
- **Security, CVE Remediation & Anti-Bad-Practices (`security-cve-hardening`)**: Whenever modifying `Dockerfile`s, `compose.yaml`, dependencies, SQL queries, HTTP handlers, or reviewing code quality, you **MUST** read and follow [`.agents/skills/security-cve-hardening/SKILL.md`](.agents/skills/security-cve-hardening/SKILL.md).
- **Cloud-Native Horizontal Scalability & 12-Factor (`cloud-native-scalability`)**: When designing stateless services, FastAPI `lifespan` graceful shutdown, Liveness/Readiness probes (`/health/live`, `/health/ready`), or sizing SQLAlchemy connection pools for multi-replica scale-out, follow [`.agents/skills/cloud-native-scalability/SKILL.md`](.agents/skills/cloud-native-scalability/SKILL.md).
- **Cloud-Native Resilience & Fault Tolerance (`cloud-native-resilience`)**: When implementing database failover handling (`pool_pre_ping`, `pool_recycle`, retries), outbound HTTP timeouts, Nginx `proxy_next_upstream`, or React `ErrorBoundary`, follow [`.agents/skills/cloud-native-resilience/SKILL.md`](.agents/skills/cloud-native-resilience/SKILL.md).
- **Cloud-Native Observability & Correlation (`cloud-native-observability`)**: When configuring structured JSON logging to `stdout`, `X-Request-ID` correlation propagation, or telemetry, follow [`.agents/skills/cloud-native-observability/SKILL.md`](.agents/skills/cloud-native-observability/SKILL.md).
- **Automated QA & IDE Diagnostics Reviewer (`qa-code-reviewer`)**: After generating or modifying any Python or TypeScript file, follow [`.agents/skills/qa-code-reviewer/SKILL.md`](.agents/skills/qa-code-reviewer/SKILL.md) to run Pylance (`basedpyright`), `mypy`, `ruff`, `tsc`, and `pytest` or delegate to the `qa-reviewer` subagent.

## 2. Layer Package Structure (Python Backend)
- `<application_base_package>.presentation` (FastAPI routers, HTTP error mapping, correlation middleware, no business logic)
- `<application_base_package>.application` (Use case orchestrators, transaction boundaries, Domain Event dispatching, Pydantic `*RequestDto` / `*ResponseDto`, mappers)
- `<application_base_package>.domain` (Rich DDD Aggregate Roots & Entities with ORM mapping allowed, frozen Value Objects, `DomainEvent`, `Specification[T]`, `*DomainService`, `*Repository` / ACL `Protocol` ports, Bounded Context sub-packages)
- `<application_base_package>.infrastructure` (`*RepositoryImpl`, `*Dao`, Anti-Corruption Layer (ACL) adapters grouped by type then domain)

## 3. Environment, Package Management & Container Hardening
- **Target Versions**: Python 3.14+ (PEP 695 generic syntax, `X | Y` unions, `match`/`case`) and TypeScript 5.7+ / React 19 / Vite 6+.
- **Tooling**: Always prefer `uv` (`uv run`, `uv add`, `uv sync`) for Python and `npm` for `frontend/`.
- **Zero-CVE Docker Containers**: Use hardened Alpine images (`nginx:1.27-alpine`, `python:3.14-alpine`, `postgres:17-alpine`) with `apk update && apk upgrade --no-cache`, multi-stage builds, and non-root execution.

## 4. Code Quality, Static Typing, Cloud-Native & Security
- **Strict Type Annotations**: Complete type annotations in Python (`mypy --strict` AND Pylance/Pyright `basedpyright` strict mode) and TypeScript (`tsc --strict`, `noUnusedLocals`, `noUnusedParameters`, `vite-env.d.ts` for CSS/Vite client types). Avoid `Any` / `any`.
- **Cloud-Native Statelessness & Resilience**: Keep Presentation and Business tiers strictly stateless; bound SQLAlchemy connection pools per replica; dispose pools on `SIGTERM` via FastAPI `lifespan`; propagate `X-Request-ID` end-to-end.
- **Anti-Bad-Practices**: Never use bare `except:`, never leak SQLAlchemy `AsyncEngine` pools (`@lru_cache` singleton pool required), never concatenate SQL strings, and never hardcode secrets.

## 5. Automated Testing, IDE Diagnostics & Multi-Agent QA Verification
- **Unified Quality Gate (`scripts/quality_gate_hook.py`)**: Before concluding any task that creates or modifies code, you **MUST** execute `uv run python scripts/quality_gate_hook.py --cli` (which runs `ruff`, `mypy`, `basedpyright`/Pylance, `tsc --noEmit`, and `pytest`) or invoke the `qa-reviewer` subagent.
- **Lifecycle Stop Hook (`.agents/hooks.json`)**: An automated `Stop` hook blocks turn completion and forces automatic self-correction whenever any Ruff, Mypy, Pylance (`basedpyright`), or TypeScript (`tsc`) error is present in the workspace.

