// /src/app/api/modules/[id]/videos/route.js
import { NextResponse } from "next/server";
import { supaPublic } from "@/lib/supabase";

export async function GET(req, { params }) {
  const { id } = params;
  const supa = supaPublic();

  const { data, error } = await supa
    .from("videos")
    .select("id, title, description, url, duration_sec, position")
    .eq("module_id", id)
    .order("position");

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json(data);
}
