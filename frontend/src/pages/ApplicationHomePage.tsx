interface ApplicationHomePageProps {
  onNavigate: (path: string) => void;
}

export function ApplicationHomePage({ onNavigate }: ApplicationHomePageProps) {
  return (
    <div className="dashboard-container">
      <header className="topbar">
        <div className="brand-section">
          <h1>
            <span>MAMTemplate — Application Métier</span>
            <span className="status-pill healthy">
              <span className="pulse-dot" />
              3-Tiers Prêt
            </span>
          </h1>
          <p className="brand-subtitle">
            Socle applicatif React 19 (Présentation) • Python 3.14 / FastAPI 4-Couches (Business) • PostgreSQL 17 (Data)
          </p>
        </div>

        <div className="controls-bar">
          <button
            type="button"
            className="btn-refresh"
            onClick={() => onNavigate("/health-check")}
          >
            Ouvrir le Health Check (/health-check)
          </button>
        </div>
      </header>

      <section className="section-card">
        <div className="section-header">
          <h2 className="section-title">
            Déploiement Unifié dans les 3 Conteneurs du Projet
          </h2>
        </div>

        <div className="tiers-grid" style={{ marginBottom: 0 }}>
          <div className="sub-box">
            <div className="sub-box-title">
              <span>1. Conteneur Présentation (mamtemplate-presentation)</span>
            </div>
            <p style={{ fontSize: "0.9rem", color: "#cbd5e1", marginBottom: "0.75rem" }}>
              Ce conteneur Nginx + React 19 héberge à la fois votre application métier sur{" "}
              <code>/</code> (et vos futures routes frontales) ainsi que la page de supervision
              sur <code>/health-check</code>.
            </p>
            <div className="kv-item">
              <span className="kv-label">Point d&apos;entrée UI Métier</span>
              <span className="kv-value">frontend/src/pages/ApplicationHomePage.tsx</span>
            </div>
          </div>

          <div className="sub-box">
            <div className="sub-box-title">
              <span>2. Conteneur Business (mamtemplate-business)</span>
            </div>
            <p style={{ fontSize: "0.9rem", color: "#cbd5e1", marginBottom: "0.75rem" }}>
              Exécute l&apos;API FastAPI selon l&apos;architecture 4 couches (Presentation,
              Application, Domain, Infrastructure). Toutes les routes <code>/api/*</code> sont
              routées automatiquement par Nginx vers ce conteneur.
            </p>
            <div className="kv-item">
              <span className="kv-label">Documentation OpenAPI Interactive</span>
              <span className="kv-value">
                <a href="/docs" style={{ color: "#38bdf8" }}>
                  /docs (Swagger UI)
                </a>
              </span>
            </div>
          </div>

          <div className="sub-box">
            <div className="sub-box-title">
              <span>3. Conteneur Data (mamtemplate-data)</span>
            </div>
            <p style={{ fontSize: "0.9rem", color: "#cbd5e1", marginBottom: "0.75rem" }}>
              Instance PostgreSQL 17 isolée sur le réseau interne <code>data_net</code>. Vos
              entités du domaine (<code>BaseEntity</code>) partagent le pool de connexions
              SQLAlchemy asynchrone avec la sonde de Health Check.
            </p>
            <div className="kv-item">
              <span className="kv-label">Pool SQLAlchemy partagé</span>
              <span className="kv-value">get_async_session() (AsyncSession)</span>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
export default ApplicationHomePage;

