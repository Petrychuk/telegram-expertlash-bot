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
  const [status, setStatus] = useState("loading"); // "loading", "error", "success"

  useEffect(() => {
    const authenticate = async () => {
      // 1. Если cookie уже есть, значит мы аутентифицированы. Просто показываем приложение.
      if (document.cookie.includes("auth_token=")) {
        setStatus("success");
        return;
      }

      // 2. Если cookie нет, начинаем процесс аутентификации
      const tg = window.Telegram?.WebApp;
      if (!tg || !tg.initData) {
        // Эта ситуация возможна, если открыть приложение не через Telegram
        setStatus("error");
        return;
      }

      try {
        // 3. Отправляем initData на наш бэкенд
        const response = await fetch('/api/auth/telegram', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ init_data: tg.initData }),
        });

        // 4. Анализируем ответ бэкенда
        if (response.ok) {
          // УСПЕХ! Бэкенд проверил нас и установил cookie.
          // Перезагружаем страницу, чтобы серверные компоненты "увидели" новый cookie.
          window.location.reload();
        } else {
          // ОШИБКА ДОСТУПА. Бэкенд нас проверил и отказал (например, нет подписки).
          // Перенаправляем на страницу "Доступ запрещен".
          window.location.href = '/access-denied';
        }
      } catch (err) {
        // Ошибка сети или другая проблема
        console.error("Auth fetch error:", err);
        setStatus("error");
      }
    };

    authenticate();
  }, []); // Пустой массив [] гарантирует, что эффект выполнится только один раз

  // --- Отображение в зависимости от статуса ---

  if (status === "loading") {
    return <Loader message="Аутентификация..." />;
  }

  if (status === "error") {
    return <Loader message="Ошибка аутентификации. Пожалуйста, перезапустите приложение через Telegram." />;
  }

  // Если статус "success", показываем основное приложение
  return children;
}
