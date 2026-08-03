import { Component, ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-screen items-center justify-center bg-vellum-grid">
          <div className="relative w-full max-w-md border-[1.5px] border-ink bg-white p-10 text-center shadow-sheet">
            <span className="tick tick-tl" />
            <span className="tick tick-tr" />
            <span className="tick tick-bl" />
            <span className="tick tick-br" />

            <p className="font-display text-2xl font-bold text-redline">
              Something went wrong
            </p>
            <p className="mt-2 font-mono-tech text-xs text-muted">
              SHEET ERR-500 · UNEXPECTED ERROR
            </p>
            <p className="mt-4 break-words text-sm text-muted-foreground">
              {this.state.error?.message || "An unexpected error occurred."}
            </p>
            <button
              onClick={() => this.setState({ hasError: false, error: null })}
              className="mt-6 inline-flex items-center justify-center rounded-[2px] border-[1.5px] border-redline bg-redline px-5 py-2.5 font-display text-[13.5px] font-semibold text-white transition-colors hover:bg-redline-dark"
            >
              Try again
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
