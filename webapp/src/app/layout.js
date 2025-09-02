import "./globals.css";
import Script from "next/script";

export const metadata = {
  title: "ExpertLash — education online platform",
  description: "Закрытая платформа",
};

export default function RootLayout({ children }) {
  return (
    // важное: подавляем различия сервер/клиент, т.к. Telegram меняет style на <html>
    <html lang="it" suppressHydrationWarning>
      <body className="bg-gray-50">
        {/* можно afterInteractive — скрипт загрузится после гидратации */}
        <Script
          src="https://telegram.org/js/telegram-web-app.js"
          strategy="afterInteractive"
        />
        {children}
      </body>
    </html>
  );
}
