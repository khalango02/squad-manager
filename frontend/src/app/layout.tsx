import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Squad Manager",
  description: "Manage and connect your AI agents",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
