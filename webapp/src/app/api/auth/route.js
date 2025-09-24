import { NextResponse } from "next/server";
import jwt from "jsonwebtoken";
import { verifyInitData } from "@/lib/telegram";
import { supaServer } from "@/lib/supabase";

const BOT_TOKEN = process.env.BOT_TOKEN;
const JWT_SECRET = process.env.JWT_SECRET || "dev";

export async function POST(req) {
  try {
    const { init_data } = await req.json();

    const parsed = verifyInitData(init_data, BOT_TOKEN);
    if (!parsed || !parsed.user) {
      return NextResponse.json({ error: "bad_signature" }, { status: 401 });
    }
    const tg = parsed.user;
    const tgId = Number(tg.id);
    const supa = supaServer();

    // upsert пользователя
    await supa.from("users").upsert({
      telegram_id: tgId,
      username: tg.username || null,
      first_name: tg.first_name || null,
      last_name: tg.last_name || null,
    }, { onConflict: "telegram_id" });

    // получаем юзера с ролью
    const { data: user } = await supa
      .from("users")
      .select("id, telegram_id, username, first_name, last_name, role")
      .eq("telegram_id", tgId)
      .single();

    // подписка
    const { data: sub } = await supa
      .from("subscriptions")
      .select("status, expires_at")
      .eq("user_id", user.id)
      .single();

    // генерируем JWT
    const token = jwt.sign(
      { sub: String(user.id), role: user.role || "student" },
      JWT_SECRET,
      { expiresIn: "7d" }
    );

    return NextResponse.json({
      token,
      profile: {
        id: user.id,
        tg_id: tgId,
        role: user.role || "student",
        username: user.username,
        first_name: user.first_name,
        last_name: user.last_name,
        subscription: sub || { status: "expired" },
      },
    });
  } catch (e) {
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}
