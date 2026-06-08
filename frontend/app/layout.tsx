import type { Metadata } from "next";
import "./globals.css";
import { NextIntlClientProvider } from "next-intl";
import { getMessages, getLocale } from "next-intl/server";
import { Providers } from "@/store/providers";
import { Shell } from "@/components/layout/Shell";
import { ToastContainer } from "@/components/ui/Toast";

export const metadata: Metadata = {
  title: "Pitchcraft",
  description: "AI-powered proposal automation for agency teams",
};

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const locale = await getLocale();
  const messages = await getMessages();
  return (
    <html lang={locale}>
      <body className="bg-gray-50">
        <NextIntlClientProvider locale={locale} messages={messages}>
          <Providers>
            <Shell>
              {children}
            </Shell>
            <ToastContainer />
          </Providers>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
