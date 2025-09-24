"use client";
import { useEffect, useState } from "react";
import useAuth from "@/hooks/useAuth";
import { isAdmin, isDev } from "@/lib/roles";
import Header from "@/components/Header";

export default function AdminPage() {
  const { token, profile } = useAuth();
  const [me, setMe] = useState(null);

  useEffect(() => {
    (async () => {
      if (!token) return;
      const r = await fetch("/api/me", { headers: { Authorization:`Bearer ${token}` }});
      if (r.ok) setMe(await r.json());
    })();
  }, [token]);

  const allowed = isAdmin(me?.role) || isDev(me?.role);

  if (!allowed) return (
    <>
      <Header profile={profile} />
      <main className="max-w-xl mx-auto mt-10 p-6 bg-white rounded-2xl shadow-soft text-center">
        <div className="font-semibold">Nessun accesso</div>
        <div className="text-sm opacity-70">Solo per amministratori/sviluppatori.</div>
      </main>
    </>
  );

  return (
    <>
      <Header profile={profile} />
      <main className="mx-auto max-w-5xl px-4 py-6">
        <h2 className="text-xl font-semibold mb-4">Pannello di amministrazione</h2>
        <div className="grid md:grid-cols-2 gap-4">
          <div className="p-4 bg-white rounded-2xl shadow-soft">
            <div className="font-semibold mb-2">Gestione moduli</div>
            <div className="text-sm opacity-70">CRUD для модулей и видео (можно добавить формы позднее).</div>
          </div>
          <div className="p-4 bg-white rounded-2xl shadow-soft">
            <div className="font-semibold mb-2">Статусы подписок</div>
            <div className="text-sm opacity-70">Просмотр/поиск пользователей, ручная активация (опционально).</div>
          </div>
        </div>
      </main>
    </>
  );
}
