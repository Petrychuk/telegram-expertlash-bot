import { useState } from "react";
import Rating from "./Rating";

export default function VideoItem({ v, token, onRated }) {
  const [liked, setLiked]   = useState(v.my_like);
  const [myRate, setMyRate] = useState(v.my_rating);

  async function toggleLike() {
    const r = await fetch(`/api/videos/${v.id}/like`, { method:"POST", headers:{Authorization:`Bearer ${token}`} });
    if (r.ok) {
      const j = await r.json();
      setLiked(j.liked);
    }
  }

  async function rate(n) {
    setMyRate(n);
    await fetch(`/api/videos/${v.id}/rate`, {
      method: "POST",
      headers: { "Content-Type":"application/json", Authorization:`Bearer ${token}`},
      body: JSON.stringify({ rate:n })
    });
    onRated?.();
  }

  return (
    <div className="p-4 bg-white rounded-2xl shadow-soft flex items-center justify-between">
      <div>
        <div className="font-semibold">{v.title}</div>
        <div className="text-xs opacity-60">~{v.duration_s || 0}s · media: {v.avg_rating ? v.avg_rating.toFixed(1) : "—"}</div>
      </div>
      <div className="flex items-center gap-3">
        <button onClick={toggleLike} className={`text-lg ${liked ? "text-roseSoft-600" : "text-roseSoft-300"}`}>♥</button>
        <Rating value={myRate} onChange={rate} />
        <a href={v.video_url} target="_blank" className="px-3 py-2 rounded-xl bg-roseSoft-600 text-white text-sm">Guarda</a>
      </div>
    </div>
  );
}
