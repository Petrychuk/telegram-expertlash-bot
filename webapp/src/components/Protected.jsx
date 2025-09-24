"use client";

export default function Protected({ profile, children }) {
  if (!profile) {
    return (
      <div className="card p-6 text-center">
        <div className="text-lg font-semibold mb-1">Требуется вход</div>
        <div className="text-sm text-gray-500">
          Откройте мини-приложение через Telegram, чтобы продолжить.
        </div>
      </div>
    );
  }
  return children;
}
