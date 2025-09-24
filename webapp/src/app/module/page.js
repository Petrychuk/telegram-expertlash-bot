"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import useAuth from "@/hooks/useAuth";
import Header from "@/components/Header";
import Protected from "@/components/Protected";
import VideoList from "@/components/VideoList";

export default function ModulePage() {
  const { id } = useParams();
  const { token, profile } = useAuth();
  const [videos, setVideos] = useState([]);

  useEffect(() => {
    if (!token) return;
    (async () => {
      const r = await fetch(`/api/modules/${id}/videos`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (r.ok) {
        setVideos(await r.json());
      }
    })();
  }, [token, id]);

  return (
    <>
      <Header profile={profile} />
      <main className="mx-auto max-w-4xl px-4 py-6">
        <Protected profile={profile}>
          <h1 className="text-2xl font-bold mb-4">Модуль {id}</h1>
          <VideoList videos={videos} token={token} onRefresh={() => {}} />
        </Protected>
      </main>
    </>
  );
}
