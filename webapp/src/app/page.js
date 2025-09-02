"use client";
import { useEffect, useState } from "react";

export default function Page() {
  const [status, setStatus] = useState("Жду…");
  const [token, setToken] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const tg = window?.Telegram?.WebApp;
        if (!tg?.initData) {
          setStatus("Откройте через кнопку в Telegram — initData не найден.");
          return;
        }
        setStatus("Нашёл initData, авторизуюсь…");
        const base = process.env.NEXT_PUBLIC_API_BASE || "";
        const r = await fetch(`${base}/api/auth/telegram`, {
          method: "POST",
          headers: {"Content-Type":"application/json"},
          body: JSON.stringify({ init_data: tg.initData }),
        });
        const data = await r.json();
        if (r.ok && data.token) { setToken(data.token); setStatus("OK: получили JWT"); }
        else { setStatus(`Ошибка: ${data.error || r.statusText}`); }
      } catch (e) { setStatus("Ошибка: " + e.message); }
    })();
  }, []);

  return (
    <main className="p-6">
      <div className="max-w-xl mx-auto bg-white rounded-2xl shadow p-6">
        <h1 className="text-xl font-semibold mb-2">ExpertLash — проверка WebApp</h1>
        <div>Статус: {status}</div>
        {token ? <pre className="text-xs break-all mt-2">{token}</pre> : null}
      </div>
    </main>
  );
}