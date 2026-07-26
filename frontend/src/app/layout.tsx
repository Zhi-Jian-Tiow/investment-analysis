import type { Metadata } from "next";
import { Instrument_Sans, Spline_Sans_Mono } from "next/font/google";
import "./globals.css";

// Matches the BursaTrack Design (BursaTrack.dc.html) exactly: Instrument Sans
// for UI text, Spline Sans Mono for stock codes / numeric figures.
const instrumentSans = Instrument_Sans({
  variable: "--font-instrument-sans",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

const splineSansMono = Spline_Sans_Mono({
  variable: "--font-spline-mono",
  subsets: ["latin"],
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  title: "BursaTrack",
  description: "The dividend investor's source of truth for Bursa Malaysia portfolios.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${instrumentSans.variable} ${splineSansMono.variable}`}>
      <body className="antialiased">{children}</body>
    </html>
  );
}
