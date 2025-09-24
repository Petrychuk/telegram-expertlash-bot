// /webapp/src/hooks/useAuth.js

"use client";

import { createContext, useContext, useEffect, useState } from "react";
import useTelegram from "./useTelegram"; // Импортируем наш хук Telegram

// 1. Создаем контекст для данных аутентификации
const AuthContext = createContext({});

// 2. Создаем Провайдер
export function AuthProvider({ children }) {
  const { initData } = useTelegram(); // Получаем initData из Telegram-контекста
  const [token, setToken] = useState(null);
  const [profile, setProfile] = useState(null);
  const [isLoading, setIsLoading] = useState(true); // Добавим состояние загрузки

  useEffect(() => {
    // Эта функция будет запрашивать токен у нашего бэкенда
    const authenticate = async () => {
      // Если initData еще не загрузились, ничего не делаем
      if (!initData) {
        // Если мы в браузере, а не в телеграме, то загрузку можно завершать
        if (typeof window !== 'undefined' && !window.Telegram?.WebApp?.initData) {
          setIsLoading(false);
        }
        return;
      }

      try {
        const res = await fetch("/api/auth", { // Запрос на ваш API-роут
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ initData }), // Отправляем initData на бэкенд
        });

        if (res.ok) {
          const { token: apiToken, profile: userProfile } = await res.json();
          setToken(apiToken);
          setProfile(userProfile);
        }
      } catch (error) {
        console.error("Authentication failed:", error);
      } finally {
        // Вне зависимости от результата, завершаем загрузку
        setIsLoading(false);
      }
    };

    authenticate();
  }, [initData]); // Запускаем аутентификацию, как только появятся initData

  // Провайдер делает токен, профиль и статус загрузки доступными всему приложению
  return (
    <AuthContext.Provider value={{ token, profile, isLoading }}>
      {children}
    </AuthContext.Provider>
  );
}
// 3. Создаем хук для удобного доступа к данным
export default function useAuth() {
  return useContext(AuthContext);
}
