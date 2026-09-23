import { ScreeningWorkspace } from "@/components/ScreeningWorkspace";

export default function Page() {
  return (
    <main className="shell">
      <header className="masthead">
        <div>
          <h1>CO2 storage screening</h1>
          <p className="sub">
            Scenario-based capacity with a full provenance audit trail
          </p>
        </div>
        <p className="sub">
          Screening tool. Not a certified storage estimate.
        </p>
      </header>
      <ScreeningWorkspace />
    </main>
  );
}
