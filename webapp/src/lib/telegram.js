import crypto from "crypto";

export function verifyInitData(initData, botToken) {
  const params = new URLSearchParams(initData || "");
  const data = {};
  for (const [k, v] of params) data[k] = v;
  const hash = data.hash;
  if (!hash) return null;
  delete data.hash;

  const checkString = Object.keys(data).sort().map(k => `${k}=${data[k]}`).join("\n");
  const secret = crypto.createHash("sha256").update(botToken).digest();
  const hmac = crypto.createHmac("sha256", secret).update(checkString).digest("hex");
  if (hmac !== hash) return null;

  let user = null;
  try { user = JSON.parse(data.user || "{}"); } catch {}
  return { data, user };
}
