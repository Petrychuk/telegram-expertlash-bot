// webapp/src/app/page.js
"use client"; 

import { useEffect, useState } from 'react';
import { useAuth } from '@/context/AuthContext'; 
import Header from "@/components/Header";
import ModuleCard from "@/components/ModuleCard";
import Link from 'next/link';

// Клиентская функция для загрузки модулей
async function getModules() {
  const url = `${process.env.NEXT_PUBLIC_API_BASE}/api/modules`; 
  try {
    // fetch автоматически использует cookie, установленные для домена
    const res = await fetch(url); 
    if (!res.ok) {
      console.error("Failed to fetch modules:", res.status);
      return [];
    }
    return res.json();
  } catch (error) {
    console.error("Error fetching modules:", error);
    return [];
  }
}

export default function HomePage() {
  const { user } = useAuth(); // Получаем пользователя из контекста
  const [modules, setModules] = useState([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // Загружаем модули, только если пользователь аутентифицирован
    if (user) { 
      getModules().then(data => {
        setModules(data);
        setIsLoading(false);
      });
    }
  }, [user]); // Эффект зависит от user

  // Если user еще не загружен (AuthGate работает), показываем заглушку
  if (!user) {
    return <div className="flex items-center justify-center h-screen">Загрузка данных пользователя...</div>;
  }

  // Основной рендер компонента
  return (
    <>
      <Header profile={user} /> 
      <main className="mx-auto max-w-6xl px-4 py-6">
        <section className="mb-8 text-center">
          <div className="bg-white p-6 rounded-lg shadow-sm">
            <h1 className="text-3xl font-bold text-gray-800 mb-2">Курс - ExpertLash</h1>
            <p className="text-md text-gray-600 max-w-2xl mx-auto">
              Откройте для себя мир профессионального наращивания ресниц.
            </p>
          </div>
        </section>
        <section>
          {isLoading ? (
            <div className="text-center py-10">Загрузка модулей...</div>
          ) : modules.length > 0 ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
              {modules.map((module) => (
                <Link href={`/module/${module.id}`} key={module.id}>
                  <ModuleCard item={module} />
                </Link>
              ))}
            </div>
          ) : (
            <div className="text-center py-10 px-6 bg-white rounded-lg shadow-sm">
              <p className="text-gray-500">Модули курса скоро появятся.</p>
            </div>
          )}
        </section>
      </main>
    </>
  );
}
