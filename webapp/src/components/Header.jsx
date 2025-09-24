"use client";
// Intestazione / header dell'app
export default function Header({ profile }) {
  return (
    <header className="sticky top-0 z-20 backdrop-blur bg-roseSoft-50/70 border-b border-roseSoft-100">
      <div className="mx-auto max-w-6xl px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 rounded-xl bg-roseSoft-200 flex items-center justify-center">
            <span className="text-roseSoft-700 font-semibold">EL</span>
          </div>
          <div>
            <div className="text-sm text-roseSoft-700 font-semibold">
              ExpertLash — Платформа
            </div>
            <div className="text-xs text-gray-500">
              {profile?.username ? `@${profile.username}` : "Гость"}
            </div>
          </div>
        </div>

        <div className="text-xs text-gray-500">
          {profile?.role === "admin" || profile?.role === "dev"
            ? "Режим администратора"
            : "Ученик"}
        </div>
      </div>
    </header>
  );
}
