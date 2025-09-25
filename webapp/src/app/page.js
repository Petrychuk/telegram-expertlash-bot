// webapp/src/app/page.js

import { redirect } from 'next/navigation';
import { cookies } from 'next/headers';
import Header from "@/components/Header";
import ModuleCard from "@/components/ModuleCard";
import Link from 'next/link';

// --- Серверные функции, которые обращаются к Python-бэкенду ---

async function getUserProfile(token) {
  if (!token) return null;
  const url = `${process.env.NEXT_PUBLIC_API_BASE}/api/auth/me`;
  const res = await fetch(url, {
    headers: { 'Cookie': `auth_token=${token}` },
    cache: 'no-store',
  });
  if (!res.ok) return null;
  const { user } = await res.json();
  return user;
}

// ИСПРАВЛЕННАЯ ВЕРСИЯ getModules
async function getModules(token) {
  if (!token) return [];
  // Указываем URL нашего Python-бэкенда
  const url = `${process.env.NEXT_PUBLIC_API_BASE}/api/modules`; 
  try {
    const res = await fetch(url, {
      headers: { 'Cookie': `auth_token=${token}` }, // Передаем cookie для аутентификации
      cache: 'no-store',
    });
    if (!res.ok) return [];
    return res.json(); // Получаем JSON-массив модулей
  } catch (error) {
    console.error("Error fetching modules:", error);
    return [];
  }
}

// --- Основной компонент страницы ---

export default async function HomePage() {
  const token = (await cookies()).get('auth_token')?.value;
  const profile = await getUserProfile(token);

  if (!profile || !profile.hasSubscription) {
    redirect('/access-denied'); 
  }

  const modules = await getModules(token);

  return (
    <>
      <Header profile={profile} /> 
      <main className="mx-auto max-w-6xl px-4 py-6">
        <section className="mb-8 text-center">
          <div className="bg-white p-6 rounded-lg shadow-sm">
            <h1 className="text-3xl font-bold text-gray-800 mb-2">Курс - ExpertLash</h1>
            <p className="text-md text-gray-600 max-w-2xl mx-auto">
              Откройте для себя мир профессионального наращивания ресниц. Наши модули проведут вас от базовых техник до экспертного уровня.
            </p>
          </div>
        </section>
        <section>
          {modules && modules.length > 0 ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
              {modules.map((module) => (
                <Link href={`/module/${module.id}`} key={module.id}>
                  <ModuleCard item={module} />
                </Link>
              ))}
            </div>
          ) : (
            <div className="text-center py-10 px-6 bg-white rounded-lg shadow-sm">
              <p className="text-gray-500">Модули не найдены.</p>
            </div>
          )}
        </section>
      </main>
    </>
  );
}
