
"use client";

import { createContext, useContext, useEffect, useState } from "react";

// 1. Создаем "контекст" - пустое хранилище для наших данных
const TelegramContext = createContext({});

// 2. Создаем Провайдер - компонент, который будет "класть" данные в хранилище
export function TelegramProvider({ children }) {
  const [webApp, setWebApp] = useState(null);

  // Этот эффект выполнится один раз при загрузке приложения
  useEffect(() => {
    // Проверяем, что window.Telegram.WebApp доступен
    if (window.Telegram && window.Telegram.WebApp) {
      setWebApp(window.Telegram.WebApp);
    }
  }, []);


  // доступным для всех дочерних компонентов
  return (
    <TelegramContext.Provider value={{ webApp }}>
      {children}
    </TelegramContext.Provider>
  );
}

// 3. Создаем наш хук - удобный способ "брать" данные из хранилища
export default function useTelegram() {
  const { webApp } = useContext(TelegramContext);

  // Возвращаем сам объект webApp и удобные поля из него
  return {
    tg: webApp,
    user: webApp?.initDataUnsafe?.user,
    initData: webApp?.initData,
  };
}


