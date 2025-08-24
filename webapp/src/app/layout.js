import './globals.css'
import Script from "next/script"

export const metadata = {
  title: 'ExpertLash — Online education platform',
  description: 'Закрытая платформа с видео и материалами',
}

export default function RootLayout({ children }) {
  return (
    <html lang="it">
      <body className="bg-gray-50">
        <Script src="https://telegram.org/js/telegram-web-app.js" strategy="beforeInteractive" />
        {children}
      </body>
    </html>
  )
}
