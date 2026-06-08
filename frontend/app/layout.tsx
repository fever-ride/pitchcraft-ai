import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "@/store/providers";
import { Shell } from "@/components/layout/Shell";
import { ToastContainer } from "@/components/ui/Toast";

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
      <body className="bg-gray-50">
        <Providers>
          <Shell>
            {children}
          </Shell>
          <ToastContainer />
        </Providers>
      </body>
    </html>
  );
}
