import React from 'react';

interface ErrorBoundaryProps {
  children: React.ReactNode;
}

interface ErrorBoundaryState {
  error: Error | null;
}

/**
 * Catches render errors anywhere below it so a bug in one component shows a
 * readable message instead of unmounting the whole app (a blank white screen).
 */
export class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('Studio UI crashed:', error, info.componentStack);
  }

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;

    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center p-6">
        <div className="bg-white rounded-2xl border border-rose-200 shadow-lg max-w-lg w-full p-6 text-gray-900">
          <h1 className="text-lg font-bold text-rose-700">Something went wrong in the Studio</h1>
          <p className="text-sm text-gray-600 mt-2">
            The page hit an unexpected error. Your pipelines keep running on the server. Reload to continue.
          </p>
          <pre className="mt-3 text-xs bg-rose-50 border border-rose-100 rounded-lg p-3 overflow-auto whitespace-pre-wrap text-rose-800">
            {error.message}
          </pre>
          <div className="mt-4 flex gap-3">
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="px-4 py-2 text-sm font-semibold text-white bg-amber-600 hover:bg-amber-700 rounded-lg"
            >
              Reload
            </button>
            <button
              type="button"
              onClick={() => this.setState({ error: null })}
              className="px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-lg"
            >
              Try again
            </button>
          </div>
        </div>
      </div>
    );
  }
}
