/**
 * Placeholder shown while a screening request is in flight.
 *
 * It occupies the result region so the previous number is gone the instant a
 * new run starts: a stale capacity sitting beside fresh inputs is worse than
 * no capacity at all. No animation -- the status text carries the state.
 */
export function ResultSkeleton() {
  return (
    <section className="panel" aria-labelledby="result-heading">
      <h2 id="result-heading">Result</h2>
      <p role="status" className="result-label">
        Running screening...
      </p>
      <div className="skeleton skeleton-value" aria-hidden="true" />
      <div className="skeleton skeleton-line" aria-hidden="true" />
      <div className="skeleton skeleton-line short" aria-hidden="true" />
    </section>
  );
}
