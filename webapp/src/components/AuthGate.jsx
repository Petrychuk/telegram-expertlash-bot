// webapp/src/components/AuthGate.jsx
"use client";
import { useEffect, useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { usePathname, useRouter } from 'next/navigation'; 

export default function AuthGate({ children }) {
  const { user, setUser } = useAuth();
  const [status, setStatus] = useState("loading"); // 'loading', 'error', 'success'
  const [errorDetails, setErrorDetails] = useState("");

  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    // Если мы уже на странице ошибки, ничего не делаем
    if (pathname === '/access-denied') {
      setStatus('success'); // Позволяем отобразить страницу ошибки
      return;
    }

    // Если пользователь уже есть, не перезапускаем аутентификацию
    if (user) {
      setStatus('success');
      return;
    }

    const initData = window.Telegram?.WebApp?.initData;
    if (!initData) {
      setErrorDetails("Не удалось получить данные Telegram. Откройте приложение через Telegram.");
      setStatus('error');
      return;
    }
    console.log("FRONTEND initData:", initData);
    const authenticateAndFetchUser = async () => {
      try {
        // Этап 1: Аутентификация
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

        // Этап 2: Получение профиля
        const meApiUrl = `${process.env.NEXT_PUBLIC_API_BASE}/api/auth/me`;
        const meRes = await fetch(meApiUrl);

        if (!meRes.ok) {
          const errorData = await meRes.json();
          throw new Error(errorData.error || `Не удалось получить профиль: ${meRes.status}`);
        }

        const userData = await meRes.json();
        
        // Этап 3: Проверка прав доступа (авторизация)
        if (!userData.user || !userData.user.hasSubscription) {
          router.push('/access-denied'); // Перенаправляем на страницу ошибки
          return; // Прерываем выполнение
        }

        // Успех!
        setUser(userData.user);
        setStatus('success');

      } catch (e) {
        setErrorDetails(e.message || "Сетевая ошибка.");
        setStatus('error');
      }
    };

    authenticateAndFetchUser();
    
  }, [pathname, router, setUser, user]);

  // --- Логика отображения ---

  if (status === 'loading') {
    return <div className="flex items-center justify-center h-screen">Аутентификация...</div>;
  }

  if (status === 'error') {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center p-4 max-w-sm">
          <p className="font-bold text-red-600">Ошибка аутентификации</p>
          <p className="text-sm text-gray-600 mt-2">
            Пожалуйста, полностью закройте и перезапустите приложение.
          </p>
          <p className="text-xs text-gray-400 mt-4">Детали: {errorDetails}</p>
        </div>
      </div>
    );
  }

  // Если статус 'success', показываем дочерний компонент
  // (либо саму страницу, либо /access-denied, куда нас уже перенаправили)
  return children;
}
