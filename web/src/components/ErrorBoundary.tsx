import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("joga.panel.render_error", error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="app-shell">
          <main className="page">
            <div className="notice notice--error" role="alert">
              <p>O painel encontrou um erro inesperado. Recarregue a página.</p>
              <button
                type="button"
                className="button button--primary"
                onClick={() => window.location.reload()}
              >
                Recarregar
              </button>
            </div>
          </main>
        </div>
      );
    }

    return this.props.children;
  }
}
