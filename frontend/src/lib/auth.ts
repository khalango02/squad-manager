import Cookies from "js-cookie";

export function saveToken(token: string) {
  Cookies.set("token", token, { expires: 1, sameSite: "strict" });
}

export function clearToken() {
  Cookies.remove("token");
}

export function getToken() {
  return Cookies.get("token");
}
