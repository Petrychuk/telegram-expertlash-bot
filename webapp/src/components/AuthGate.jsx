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
    // Если мы на странице ошибки или пользователь уже есть, ничего не делаем.
    if (pathname === '/access-denied' || user) {
      setStatus('success');
      return;
    }

    // Шаг 1: Получаем "сырую" строку initData.
    const initData = window.Telegram?.WebApp?.initData;
    if (!initData || !initData.includes("hash=")) {
    console.error("❌ Получено initData без hash, вероятно ты смотришь на initDataUnsafe");
    }

    const authenticateAndFetchUser = async () => {
      try {
        console.log("Sending initData to backend:", initData);
        
        // Шаг 2: Отправляем initData на бэкенд без каких-либо изменений.
        const authApiUrl = `${process.env.NEXT_PUBLIC_API_BASE}/api/auth/telegram`;
        const authRes = await fetch(authApiUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ init_data: initData }),
        });

        if (!authRes.ok) {
          const errorData = await authRes.json().catch(() => ({ error: `Authentication failed with status: ${authRes.status}` }));
          throw new Error(errorData.error || 'unknown_auth_error');
        }

        // Шаг 3: Если аутентификация успешна, бэкенд установил cookie.
        // Теперь делаем запрос к /me, чтобы получить данные пользователя.
        const meApiUrl = `${process.env.NEXT_PUBLIC_API_BASE}/api/auth/me`;
        const meRes = await fetch(meApiUrl); // fetch автоматически отправит cookie.

        if (!meRes.ok) {
          const errorData = await meRes.json().catch(() => ({ error: `Profile fetch failed with status: ${meRes.status}` }));
          throw new Error(errorData.error || 'unknown_profile_error');
        }

        const userData = await meRes.json();
        
        // Шаг 4: Проверяем права доступа (авторизация).
        if (!userData.user || !userData.user.hasSubscription) {
          router.push('/access-denied'); // Нет подписки -> редирект.
          return;
        }

        // Шаг 5: Успех! Сохраняем пользователя в глобальном состоянии.
        setUser(userData.user);
        setStatus('success');

      } catch (e) {
        setErrorDetails(e.message);
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
      <div className="flex items-center justify-center h-screen text-center p-4">
        <div>
          <p className="font-bold text-red-600">Ошибка аутентификации</p>
          <p className="text-sm text-gray-600 mt-2">Пожалуйста, полностью закройте и перезапустите приложение.</p>
          <p className="text-xs text-gray-400 mt-4">Детали: {errorDetails}</p>
        </div>
      </div>
    );
  }

  // Если статус 'success', показываем дочерний компонент.
  return children;
}
