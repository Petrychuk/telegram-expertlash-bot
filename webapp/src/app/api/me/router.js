import { NextResponse } from "next/server";
import jwt from "jsonwebtoken";
import { supaServer } from "@/lib/supabase";

const JWT_SECRET = process.env.JWT_SECRET || "dev";

export async function GET(req) {
  const auth = req.headers.get("authorization") || "";
  const token = auth.replace(/^Bearer\s+/i, "");
  if (!token) {
    return NextResponse.json({ error: "no_token" }, { status: 401 });
  }

  try {
    const payload = jwt.verify(token, JWT_SECRET);
    const userId = Number(payload.sub);
    const supa = supaServer();

    // получаем юзера
    const { data: user } = await supa
      .from("users")
      .select("id, telegram_id, username, first_name, last_name, role")
      .eq("id", userId)
      .single();

    // подписка
    const { data: sub } = await supa
      .from("subscriptions")
      .select("status, expires_at")
      .eq("user_id", user.id)
      .single();

    return NextResponse.json({
      id: user.id,
      tg_id: user.telegram_id,
      role: user.role || "student",
      username: user.username,
      first_name: user.first_name,
      last_name: user.last_name,
      subscription: sub || { status: "expired" },
    });
  } catch (e) {
    return NextResponse.json({ error: "bad_token" }, { status: 401 });
  }
}
