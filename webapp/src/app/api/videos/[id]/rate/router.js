import { NextResponse } from "next/server";
import jwt from "jsonwebtoken";
import { supaServer } from "@/lib/supabase";

export async function POST(req, { params }) {
  const token = (req.headers.get("authorization") || "").replace(/^Bearer\s+/i, "");
  try {
    const { rate } = await req.json();
    const rating = Math.max(1, Math.min(5, Number(rate)));

    const { sub } = jwt.verify(token, process.env.JWT_SECRET || "dev");
    const supa = supaServer();
    const videoId = Number(params.id);

    const { data: existing } = await supa.from("video_reactions")
      .select("id").eq("video_id", videoId).eq("tg_id", sub).maybeSingle();

    if (existing) {
      await supa.from("video_reactions").update({ rating, updated_at: new Date().toISOString() }).eq("id", existing.id);
    } else {
      await supa.from("video_reactions").insert({ video_id: videoId, tg_id: sub, rating });
    }
    return NextResponse.json({ rating });
  } catch {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
}
