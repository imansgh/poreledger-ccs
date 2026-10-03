import {
  ContributeData,
  ProjectIntro,
  SiteFooter,
  StatusGuide,
} from "@/components/AboutSections";
import { AssessmentWorkspace } from "@/components/AssessmentWorkspace";
import { EmbedHeight } from "@/components/EmbedHeight";
import { ServiceStatus } from "@/components/ServiceStatus";
import { ExistingDataSection } from "@/components/ExistingDataSection";

export default function Page() {
  return (
    <main className="shell">
      <header className="masthead">
        <div>
          <h1>PoreLedger CCS</h1>
          <p className="detail">CO₂ Storage Screening &amp; Uncertainty Analysis · By Iman</p>
          <p className="lede">
            Enter or upload your well data, check it, and get a screening capacity estimate with its
            uncertainty and reasons. Not a certified storage estimate.
          </p>
          <ServiceStatus />
        </div>
      </header>
      <AssessmentWorkspace />
      <h2 className="section-title">About this tool</h2>
      <ProjectIntro />
      <div className="about-grid">
        <StatusGuide />
        <ContributeData />
      </div>
      <ExistingDataSection />
      <SiteFooter />
      <EmbedHeight />
    </main>
  );
}
