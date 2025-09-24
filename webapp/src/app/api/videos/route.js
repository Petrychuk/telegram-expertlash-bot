// /src/app/api/videos/route.js
import { NextResponse } from "next/server";
import { supaPublic } from "@/lib/supabase";

export async function GET(req) {
  const supa = supaPublic();
  const { searchParams } = new URL(req.url);
  const moduleId = searchParams.get("moduleId");

  const { data, error } = await supa
    .from("videos")
    .select("*")
    .eq("module_id", moduleId)
    .order("sort_order");

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json(data);
}

