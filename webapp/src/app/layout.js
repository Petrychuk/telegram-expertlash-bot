//layout.js
import "./globals.css";
import Script from "next/script";
import { Inter } from 'next/font/google'; //Manrope или Nunito (можно еще и такие попробывать)

import { AuthProvider } from "@/context/AuthContext";

const inter = Inter({ subsets: ['latin'] });

export const metadata = {
  title: "ExpertLash — education online platform",
  description: "Эксклюзивный курс по наращиванию ресниц",
};

export default function RootLayout({ children }) {
  return (
    // Ваш грамотный код остается без изменений
    <html lang="it" suppressHydrationWarning> 
      <body className={`${inter.className} bg-gray-50`}>
        
        {/* Ваш скрипт Telegram тоже на месте */}
        <Script
          src="https://telegram.org/js/telegram-web-app.js"
          strategy="afterInteractive"
        />

        {/* 
          ДОПОЛНЕНИЕ: Оборачиваем дочерние компоненты в провайдеры.
          Это позволит вам легко получать доступ к данным пользователя
          и статусу его подписки в любом компоненте приложения,
          не "прокидывая" их через props.
        */}
        <AuthProvider>
          {children}
        </AuthProvider>

      </body>
    </html>
   );
}

