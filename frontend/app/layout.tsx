import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CCS screening",
  description:
    "Scenario-based CO2 storage screening with a full provenance audit trail.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
