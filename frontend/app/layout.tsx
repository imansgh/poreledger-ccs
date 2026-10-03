import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PoreLedger CCS | CO₂ Storage Screening",
  description:
    "Research software for conditional geological CO₂ storage screening, with explicit inputs, Monte Carlo uncertainty and reproducible results.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
