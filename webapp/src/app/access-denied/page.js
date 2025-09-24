// /app/access-denied/page.js

export default function AccessDeniedPage() {
  return (
    <div className="flex items-center justify-center h-screen bg-gray-100">
      <div className="text-center p-8 bg-white rounded-lg shadow-lg max-w-sm">
        <h1 className="text-2xl font-bold mb-4 text-red-600">Доступ запрещен</h1>
        <p className="text-gray-700 mb-6">
          У вас нет активной подписки для просмотра этого контента. Пожалуйста, оформите подписку через нашего Telegram-бота.
        </p>
        <a 
          href="https://t.me/ExpertLash_bot" // <-- ВАЖНО: Укажите имя вашего бота
          target="_blank" 
          rel="noopener noreferrer"
          className="inline-block bg-blue-500 text-white font-bold py-3 px-6 rounded-lg hover:bg-blue-600 transition-colors"
        >
          Перейти к боту
        </a>
      </div>
    </div>
   );
}
