// webapp/src/app/module/[id]/page.js

import { redirect } from 'next/navigation';
import { cookies } from 'next/headers';
import Header from "@/components/Header";
// import VideoList from "@/components/VideoList"; // Предполагаем, что у вас есть такой компонент

// --- Такие же серверные функции, как на главной странице ---

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

// Новая функция для получения видео конкретного модуля
async function getVideosForModule(moduleId, token) {
  if (!token) return [];
  // Обратите внимание на URL: он включает ID модуля
  const url = `${process.env.NEXT_PUBLIC_API_BASE}/api/modules/${moduleId}/videos`; 
  try {
    const res = await fetch(url, {
      headers: { 'Cookie': `auth_token=${token}` },
      cache: 'no-store',
    });
    if (!res.ok) return [];
    return res.json();
  } catch (error) {
    console.error(`Error fetching videos for module ${moduleId}:`, error);
    return [];
  }
}

// --- Основной компонент страницы ---

// `params` содержит динамическую часть URL, в нашем случае `id` модуля
export default async function ModulePage({ params }) {
  const moduleId = params.id;
  const token = (await cookies()).get('auth_token')?.value;
  
  // 1. Проверяем доступ точно так же, как на главной
  const profile = await getUserProfile(token);
  if (!profile || !profile.hasSubscription) {
    redirect('/access-denied'); 
  }

  // 2. Загружаем видео для этого конкретного модуля
  const videos = await getVideosForModule(moduleId, token);

  return (
    <>
      <Header profile={profile} />
      <main className="mx-auto max-w-4xl px-4 py-6">
        {/* Здесь будет заголовок модуля и список видео */}
        <h1 className="text-3xl font-bold mb-6">Видео из Модуля {moduleId}</h1>
        
        {/* 
          Здесь вы можете использовать компонент VideoList или просто
          пройтись по массиву videos и отрендерить каждый элемент.
        */}
        <div className="space-y-4">
          {videos && videos.length > 0 ? (
            videos.map(video => (
              <div key={video.id} className="p-4 bg-white rounded-lg shadow-sm">
                <h2 className="text-xl font-semibold">{video.title}</h2>
                {/* Здесь будет ваш видеоплеер */}
              </div>
            ))
          ) : (
            <p className="text-gray-500">Видео в этом модуле не найдены.</p>
          )}
        </div>
      </main>
    </>
  );
}
