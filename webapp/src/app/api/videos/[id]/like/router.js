import { NextResponse } from "next/server";
import jwt from "jsonwebtoken";
import { supaServer } from "@/lib/supabase";

export async function POST(req, { params }) {
  const token = (req.headers.get("authorization") || "").replace(/^Bearer\s+/i, "");
  try {
    const { sub } = jwt.verify(token, process.env.JWT_SECRET || "dev");
    const supa = supaServer();
    const videoId = Number(params.id);

    const { data: existing } = await supa.from("video_reactions")
      .select("id, liked").eq("video_id", videoId).eq("tg_id", sub).maybeSingle();

    if (existing) {
      await supa.from("video_reactions").update({ liked: !existing.liked, updated_at: new Date().toISOString() })
        .eq("id", existing.id);
      return NextResponse.json({ liked: !existing.liked });
    } else {
      await supa.from("video_reactions").insert({ video_id: videoId, tg_id: sub, liked: true });
      return NextResponse.json({ liked: true });
    }
  } catch {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
}
