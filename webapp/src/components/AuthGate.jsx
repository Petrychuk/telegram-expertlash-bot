// webapp/src/components/AuthGate.jsx
"use client";
import { useEffect, useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { usePathname, useRouter } from 'next/navigation';

export default function AuthGate({ children }) {
  const { user, setUser } = useAuth();
  const [status, setStatus] = useState("loading");
  const [errorDetails, setErrorDetails] = useState("");

  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    // Если мы на странице ошибки или пользователь уже есть, ничего не делаем
    if (pathname === '/access-denied' || user) {
      setStatus('success');
      return;
    }

    // Получаем "сырые" данные от Telegram
    const initData = window.Telegram?.WebApp?.initData;

    // Если данных нет, показываем ошибку
    if (!initData) {
      setErrorDetails("Не удалось получить данные Telegram. Откройте приложение через Telegram.");
      setStatus('error');
      return;
    }

    const authenticateAndFetchUser = async () => {
      try {
        const authApiUrl = `${process.env.NEXT_PUBLIC_API_BASE}/api/auth/telegram`;
        
        // --- ГЛАВНОЕ ИСПРАВЛЕНИЕ ---
        // Отправляем initData "как есть", без encodeURIComponent
        const authRes = await fetch(authApiUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ init_data: initData }), 
        });

        // Если статус 403 - нет подписки, перенаправляем
        if (authRes.status === 403) {
          router.push('/access-denied');
          return;
        }

        // Если любой другой неуспешный статус - показываем ошибку
        if (!authRes.ok) {
          const errorData = await authRes.json().catch(() => ({ error: `Auth failed: ${authRes.status}` }));
          throw new Error(errorData.error || 'unknown_auth_error');
        }

        // Если аутентификация прошла успешно, запрашиваем профиль
        const meApiUrl = `${process.env.NEXT_PUBLIC_API_BASE}/api/auth/me`;
        const meRes = await fetch(meApiUrl); // cookie передадутся автоматически

        if (!meRes.ok) {
          const errorData = await meRes.json().catch(() => ({ error: `Profile fetch failed: ${meRes.status}` }));
          throw new Error(errorData.error || 'unknown_profile_error');
        }

        const userData = await meRes.json();
        setUser(userData.user); // Сохраняем пользователя в контекст
        setStatus('success');

      } catch (e) {
        setErrorDetails(e.message);
        setStatus('error');
      }
    };

    authenticateAndFetchUser();

  }, [pathname, router, setUser, user]);

  // --- Рендер компонента (без изменений) ---
  if (status === 'loading') {
    return <div className="flex items-center justify-center h-screen">Аутентификация...</div>;
  }

  if (status === 'error') {
    return (
      <div className="flex items-center justify-center h-screen text-center p-4">
        <div>
          <p className="font-bold text-red-600">Ошибка аутентификации</p>
          <p className="text-sm text-gray-600 mt-2">Пожалуйста, полностью закройте и перезапустите приложение.</p>
          <p className="text-xs text-gray-400 mt-4">Детали: {errorDetails}</p>
        </div>
      </div>
    );
  }

  return children;
}
