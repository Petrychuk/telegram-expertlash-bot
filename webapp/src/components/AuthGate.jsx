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
    if (pathname === '/access-denied' || user) {
      setStatus('success');
      return;
    }

    const initData = window.Telegram?.WebApp?.initData;
    if (!initData) {
      setErrorDetails("Не удалось получить данные Telegram. Откройте приложение через Telegram.");
      setStatus('error');
      return;
    }

    const authenticateAndFetchUser = async () => {
      try {
        const authApiUrl = `${process.env.NEXT_PUBLIC_API_BASE}/api/auth/telegram`;
       
        // Шаг 1: Авторизация
        const authRes = await fetch(authApiUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({ init_data: initData }),
        });

        if (authRes.status === 403) {
          router.push('/access-denied');
          return;
        }

        if (!authRes.ok) {
          const errorData = await authRes.json().catch(() => ({ 
            error: `Auth failed: ${authRes.status}` 
          }));
          throw new Error(errorData.error || 'unknown_auth_error');
        }

        // ИЗМЕНЕНИЕ: Получаем токен из ответа
        const authData = await authRes.json();
        const token = authData.token;

        if (token) {
          // Сохраняем токен в localStorage
          localStorage.setItem('auth_token', token);
        }

        // Шаг 2: Получаем данные пользователя
        const meApiUrl = `${process.env.NEXT_PUBLIC_API_BASE}/api/auth/me`;
        
        // ИЗМЕНЕНИЕ: Используем токен из ответа или localStorage
        const headers = {
          'Content-Type': 'application/json',
        };
        
        if (token) {
          headers['Authorization'] = `Bearer ${token}`;
        }

        const meRes = await fetch(meApiUrl, {
          method: 'GET',
          headers: headers,
          credentials: 'include', // Оставляем на случай если cookie работают
        });

        if (!meRes.ok) {
          const errorData = await meRes.json().catch(() => ({ 
            error: `Profile fetch failed: ${meRes.status}` 
          }));
          throw new Error(errorData.error || 'unknown_profile_error');
        }

        const userData = await meRes.json();
        setUser(userData.user);
        setStatus('success');

      } catch (e) {
        console.error('Auth error:', e);
        setErrorDetails(e.message);
        setStatus('error');
      }
    };

    authenticateAndFetchUser();
  }, [pathname, router, setUser, user]);

  if (status === 'loading') {
    return (
      <div className="flex items-center justify-center h-screen">
        Аутентификация...
      </div>
    );
  }

  if (status === 'error') {
    return (
      <div className="flex items-center justify-center h-screen text-center p-4">
        <div>
          <p className="font-bold text-red-600">Ошибка аутентификации</p>
          <p className="text-sm text-gray-600 mt-2">
            Пожалуйста, полностью закройте и перезапустите приложение.
          </p>
          <p className="text-xs text-gray-400 mt-4">Детали: {errorDetails}</p>
        </div>
      </div>
    );
  }

  return children;
}