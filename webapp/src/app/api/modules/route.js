import { NextResponse } from "next/server";
import { supaPublic } from "@/lib/supabase";

export async function GET() {
  const supa = supaPublic();

  const { data, error } = await supa
    .from("modules")
    .select("id, title, description, position, is_free")
    .order("position");

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json(data);
}
