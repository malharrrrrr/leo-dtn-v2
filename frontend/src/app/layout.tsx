import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "LEO-DTN | Satellite Network Simulator",
  description: "A deterministic, contact-aware delay-tolerant network simulation dashboard.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
