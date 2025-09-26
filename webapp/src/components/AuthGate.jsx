// webapp/src/components/AuthGate.jsx
"use client";
import { useEffect, useState } from "react";
import { useAuth } from "@/context/AuthContext"; // Импортируем хук

export default function AuthGate({ children }) {
  const { setUser } = useAuth(); // Получаем функцию для установки пользователя
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const initData = window.Telegram?.WebApp?.initData;

    if (!initData) {
      setError("Не удалось получить данные Telegram. Откройте приложение через Telegram.");
      setIsLoading(false);
      return;
    }

    const authenticateAndFetchUser = async () => {
      try {
        // --- ЭТАП 1: АУТЕНТИФИКАЦИЯ И УСТАНОВКА COOKIE ---
        const authApiUrl = `${process.env.NEXT_PUBLIC_API_BASE}/api/auth/telegram`;
        const authRes = await fetch(authApiUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ init_data: initData }),
        });

        if (!authRes.ok) {
          const errorData = await authRes.json();
          throw new Error(errorData.error || `Ошибка аутентификации: ${authRes.status}`);
        }

        // --- ЭТАП 2: ПОЛУЧЕНИЕ ДАННЫХ ПОЛЬЗОВАТЕЛЯ ---
        // Cookie уже установлена, теперь делаем авторизованный запрос
        const meApiUrl = `${process.env.NEXT_PUBLIC_API_BASE}/api/auth/me`;
        const meRes = await fetch(meApiUrl); // GET-запрос, cookie отправится автоматически

        if (!meRes.ok) {
          const errorData = await meRes.json();
          throw new Error(errorData.error || `Не удалось получить профиль: ${meRes.status}`);
        }

        const userData = await meRes.json();
        setUser(userData.user); // Сохраняем пользователя в глобальном состоянии

      } catch (e) {
        setError(e.message || "Сетевая ошибка. Проверьте URL бэкенда и CORS.");
        console.error("Auth process error:", e);
      } finally {
        setIsLoading(false);
      }
    };

    authenticateAndFetchUser();
    
  }, [setUser]); // Добавляем setUser в зависимости

  if (isLoading) {
    return <div className="flex items-center justify-center h-screen">Аутентификация...</div>;
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center p-4 max-w-sm">
          <p className="font-bold text-red-600">Ошибка аутентификации</p>
          <p className="text-sm text-gray-600 mt-2">
            Пожалуйста, полностью закройте и перезапустите приложение через Telegram.
          </p>
          <p className="text-xs text-gray-400 mt-4">Детали: {error}</p>
        </div>
      </div>
    );
  }
  
  // Если нет ошибки и загрузка завершена, значит пользователь успешно аутентифицирован
  // и его данные сохранены в контексте. Показываем приложение.
  return children;
}
