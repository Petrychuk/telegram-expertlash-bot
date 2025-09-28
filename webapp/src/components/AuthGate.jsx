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

  // --- Шаг 1. Получаем initData ---
  let initData = window.Telegram?.WebApp?.initData || "";

  // Fallback: Telegram Desktop иногда кладёт initData в query-параметр tgWebAppData
  if (!initData || !initData.includes("hash=")) {
    const params = new URLSearchParams(window.location.search);
    const fallback = params.get("tgWebAppData");
    if (fallback) {
      console.warn("⚠️ Использую tgWebAppData из URL вместо initData");
      initData = fallback;
    }
  }

  if (!initData || !initData.includes("hash=")) {
    console.error("❌ initData не содержит hash (Telegram не передал данные).");
    setErrorDetails("Telegram не передал данные авторизации.");
    setStatus('error');
    return;
  }

  const authenticateAndFetchUser = async () => {
    try {
      console.log("➡️ Отправляю initData на бэкенд:", initData);

      // --- Шаг 2. Аутентификация ---
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

      // --- Шаг 3. Запрос профиля ---
      const meApiUrl = `${process.env.NEXT_PUBLIC_API_BASE}/api/auth/me`;
      const meRes = await fetch(meApiUrl); // куки придут автоматически
      if (!meRes.ok) {
        const errorData = await meRes.json().catch(() => ({ error: `Profile fetch failed with status: ${meRes.status}` }));
        throw new Error(errorData.error || 'unknown_profile_error');
      }

      const userData = await meRes.json();

      // --- Шаг 4. Проверяем подписку ---
      if (!userData.user || !userData.user.hasSubscription) {
        router.push('/access-denied');
        return;
      }

      // --- Шаг 5. Сохраняем пользователя ---
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
