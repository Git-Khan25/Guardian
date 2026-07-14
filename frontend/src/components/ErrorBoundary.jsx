import React from "react";

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error, info) {
    // eslint-disable-next-line no-console
    console.error("Contract Guardian crashed:", error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen flex items-center justify-center px-6">
          <div className="max-w-md text-center space-y-4">
            <div className="w-10 h-10 mx-auto rounded-sm border-2 border-verdict-contradicted flex items-center justify-center font-display text-verdict-contradicted">
              !
            </div>
            <h1 className="font-display text-2xl text-paper">Something went wrong</h1>
            <p className="text-sm text-paper/55 leading-relaxed">
              The scan hit an unexpected error — often caused by a site that's slow to load or
              blocks automated browsing. Your other scans and cached results are unaffected.
            </p>
            <button
              onClick={() => window.location.reload()}
              className="font-mono text-xs uppercase tracking-widest text-amber-accent border border-amber-accent/50 hover:bg-amber-accent hover:text-ink-950 rounded-sm px-5 py-2.5 transition-colors"
            >
              Reload
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
