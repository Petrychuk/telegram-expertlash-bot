// /app/page.js
import { redirect } from 'next/navigation';
import { cookies } from 'next/headers';
import Header from "@/components/Header";
import ModuleCard from "@/components/ModuleCard";
import Link from 'next/link';

// Серверная функция для проверки токена и получения профиля
async function getUserProfile(token) {
  if (!token) return null;
  const url = `${process.env.NEXT_PUBLIC_API_BASE}/api/auth/me`; // Запрос на бэкенд

  const res = await fetch(url, {
    headers: { 'Cookie': `auth_token=${token}` }, // Передаем токен как cookie
    cache: 'no-store',
  });

  if (!res.ok) return null;
  const { user } = await res.json(); // Бэкенд возвращает { user: ... }
  return user;
}

// Серверная функция для получения модулей
async function getModules(token) {
    // ... (ваш код для получения модулей, он корректен)
}

export default async function HomePage() {
  const token = (await cookies()).get('auth_token')?.value;
  const profile = await getUserProfile(token);

  // Главная проверка доступа
  if (!profile || !profile.hasSubscription) {
    redirect('/access-denied'); 
  }

  const modules = await getModules(token);

  return (
    <>
      <Header profile={profile} /> 
      <main className="mx-auto max-w-6xl px-4 py-6">
        {/* ... ваш JSX для отображения модулей ... */}
      </main>
    </>
  );
}
