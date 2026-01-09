import type { Metadata } from "next";
import { Inter, Playfair_Display, Newsreader } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/context/AuthContext";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

const playfair = Playfair_Display({
  subsets: ["latin"],
  variable: "--font-playfair",
  weight: ["400", "500", "600", "700"],
});

const newsreader = Newsreader({
  subsets: ["latin"],
  variable: "--font-newsreader",
  style: ["italic"],
  weight: ["300", "400", "500"],
});

export const metadata: Metadata = {
  title: "Financial Underwriting AI - Valiance Capital",
  description: "AI-powered financial underwriting and analysis platform for commercial real estate",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body
        className={`${inter.variable} ${playfair.variable} ${newsreader.variable} ${inter.className}`}
      >
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
