"use client";
// Card modulo con stile rosa; tutti i testi per l'utente sono in russo
export default function ModuleCard({ item, onOpen }) {
  return (
    <div className="card p-4 hover:shadow-soft transition cursor-pointer" onClick={() => onOpen(item.id)}>
      <div className="h-36 rounded-xl bg-gradient-to-br from-roseSoft-100 to-roseSoft-200 mb-3
                      flex items-center justify-center">
        <span className="text-roseSoft-700 text-2xl font-semibold">{item.title?.[0] ?? "M"}</span>
      </div>
      <div className="mb-1 text-base font-semibold">{item.title}</div>
      <div className="text-sm text-gray-500 line-clamp-2">{item.description}</div>
    </div>
  );
}
