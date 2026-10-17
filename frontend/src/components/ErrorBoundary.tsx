import { Component, type ErrorInfo, type ReactNode } from "react";

interface ErrorBoundaryProps {
  readonly children: ReactNode;
}

interface ErrorBoundaryState {
  readonly hasError: boolean;
  readonly errorMessage: string | null;
}

export class ErrorBoundary extends Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, errorMessage: null };
  }

  static getDerivedStateFromError(error: unknown): ErrorBoundaryState {
    const message =
      error instanceof Error
        ? error.message
        : "Une erreur inattendue est survenue dans le tiers Présentation.";
    return { hasError: true, errorMessage: message };
  }

  override componentDidCatch(error: unknown, info: ErrorInfo): void {
    console.error("React ErrorBoundary caught an error:", error, info);
  }

  private readonly handleReset = (): void => {
    this.setState({ hasError: false, errorMessage: null });
  };

  override render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div className="dashboard-container">
          <div className="error-banner" style={{ marginTop: "2rem" }}>
            <h2 style={{ marginBottom: "0.5rem" }}>
              Isolation de panne UI (ErrorBoundary Cloud-Native)
            </h2>
            <p style={{ marginBottom: "1rem" }}>{this.state.errorMessage}</p>
            <button
              type="button"
              className="btn-refresh"
              onClick={this.handleReset}
            >
              Réessayer le rendu
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;

