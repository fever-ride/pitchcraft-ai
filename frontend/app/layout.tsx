import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "@/store/providers";
import { Nav } from "@/components/layout/Nav";

export const metadata: Metadata = {
  title: "Pitchcraft",
  description: "AI-powered proposal automation for agency teams",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-gray-50">
        <Providers>
          <Nav />
          {children}
        </Providers>
      </body>
    </html>
  );
}
