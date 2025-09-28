// webapp/src/app/layout.js
import "./globals.css";
import Script from "next/script";
import { Inter } from 'next/font/google';

import { AuthProvider } from "@/context/AuthContext";
import AuthGate from "@/components/AuthGate"; // <-- ИМПОРТИРУЕМ AuthGate

const inter = Inter({ subsets: ['latin'] });

export const metadata = {
  title: "ExpertLash — piattaforma educativa online",
  description: "Corso esclusivo di extension ciglia",
};

export default function RootLayout({ children }) {
  return (
    <html lang="it" suppressHydrationWarning> 
      <body className={`${inter.className} bg-gray-50`}>
        <Script
          src="https://telegram.org/js/telegram-web-app.js"
          strategy="beforeInteractive" // Ускоряем загрузку скрипта Telegram
        />
        <AuthProvider>
          <AuthGate> {/* <-- AuthGate теперь защищает всё приложение */}
            {children}
          </AuthGate>
        </AuthProvider>
      </body>
    </html>
   );
}
