import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Curated Curiosities Studio",
  description: "Private content studio for Curated Curiosities.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-dvh bg-background text-foreground">
        {children}
      </body>
    </html>
  );
}
