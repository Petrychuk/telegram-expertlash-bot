// webapp/src/components/AuthGate.jsx
"use client";
import { useEffect, useState } from "react";

// Простой компонент для отображения статуса загрузки
function Loader({ message }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', padding: '20px', textAlign: 'center' }}>
      <p style={{ fontSize: '18px', color: '#333' }}>{message}</p>
    </div>
  );
}

export default function AuthGate({ children }) {
  // Состояния остаются теми же
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  // Этот эффект будет выполняться один раз при монтировании компонента
  useEffect(() => {
    // Получаем initData напрямую из объекта Telegram
    const initData = window.Telegram?.WebApp?.initData;

    // Если по какой-то причине initData нет (например, открыли в обычном браузере),
    // сразу устанавливаем ошибку.
    if (!initData) {
      setError("Не удалось получить данные Telegram. Откройте приложение через Telegram.");
      setIsLoading(false);
      return;
    }

    const authenticate = async () => {
      try {
        const apiUrl = `${process.env.NEXT_PUBLIC_API_BASE}/api/auth/telegram`;
        
        const res = await fetch(apiUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ init_data: initData }),
        });

        if (res.ok) {
          setIsAuthenticated(true);
        } else {
          const errorData = await res.json();
          setError(errorData.error || `Ошибка сервера: ${res.status}`);
        }
      } catch (e) {
        setError("Сетевая ошибка. Проверьте URL бэкенда и настройки CORS.");
        console.error("Authentication fetch error:", e);
      } finally {
        setIsLoading(false);
      }
    };

    authenticate();
    
  }, []); // Пустой массив зависимостей означает, что эффект выполнится один раз

  // --- Логика отображения состояний остается прежней ---

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
          {/* Раскомментируйте для отладки, чтобы видеть детали ошибки */}
          {/* <p className="text-xs text-gray-400 mt-4">Детали: {error}</p> */}
        </div>
      </div>
    );
  }

  if (isAuthenticated) {
    // Успех! Показываем приложение.
    return children;
  }

  // Если ни одно из условий не выполнилось (что маловероятно),
  // можно показать пустой экран, чтобы избежать моргания.
  return null; 
}