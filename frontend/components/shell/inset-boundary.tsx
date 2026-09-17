"use client";

import { Component, type ErrorInfo, type ReactNode } from "react";

interface InsetBoundaryProps {
  /** What this inset shows, in the words its heading uses ("Production outlook"). */
  label: string;
  children: ReactNode;
}

interface InsetBoundaryState {
  error: Error | null;
}

/** Keeps one failing inset from taking the whole sheet down with it.
 *
 * Without this, an exception thrown while a single client widget renders - the
 * chart, the map, the review register - unmounts everything up to the route's
 * error.tsx, so one bad payload blanks the page, the navigation's context and
 * every other working panel. Here the failure stays in the inset that failed:
 * it says so in place, keeps its neighbours on screen, and can try again.
 *
 * It catches render-time errors in client components only. Server rendering
 * failures still reach the route's error.tsx, which is where they belong.
 */
export class InsetBoundary extends Component<InsetBoundaryProps, InsetBoundaryState> {
  state: InsetBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): InsetBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Reported, not swallowed: the page stays usable and the cause stays findable.
    console.error(`[inset: ${this.props.label}] failed to render`, error, info.componentStack);
  }

  private retry = () => {
    this.setState({ error: null });
  };

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;
    const reason = error.message ? error.message.slice(0, 160) : null;
    return (
      <div role="alert" className="inset-failure">
        <p className="inset-failure-title">{this.props.label} could not be drawn</p>
        <p className="inset-failure-detail">
          The rest of this sheet is unaffected.{reason ? ` ${reason}` : ""}
        </p>
        <button type="button" className="inset-failure-retry" onClick={this.retry}>
          Try again
        </button>
      </div>
    );
  }
}
