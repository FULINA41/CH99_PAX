import type { Metadata, Viewport } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans, IBM_Plex_Serif } from "next/font/google";
import "./globals.css";

// One superfamily in three roles. Plex was drawn for institutional and technical documents,
// which is what a tariff schedule is, and its serif, sans and mono share proportions -- so a
// code set in mono sits beside prose set in sans without either looking borrowed.
const sans = IBM_Plex_Sans({
  subsets: ["latin"], weight: ["400", "500", "600"], variable: "--font-plex-sans",
});
const serif = IBM_Plex_Serif({
  subsets: ["latin"], weight: ["400", "600"], variable: "--font-plex-serif",
});
const mono = IBM_Plex_Mono({
  subsets: ["latin"], weight: ["400", "500", "600"], variable: "--font-plex-mono",
});

export const metadata: Metadata = {
  // Every page carried the same title, so tabs, history and bookmarks were indistinguishable.
  title: { default: "Chapter 99", template: "%s · Chapter 99" },
  description:
    "What Chapter 99 of the US tariff schedule does to the duty on a good, and how every "
    + "step of that answer was reached.",
};

export const viewport: Viewport = { width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${sans.variable} ${serif.variable} ${mono.variable}`}>
      <body>{children}</body>
    </html>
  );
}
