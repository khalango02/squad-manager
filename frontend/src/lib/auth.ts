// Token is stored as an httpOnly cookie by the backend.
// The browser sends it automatically — never read or write it from JS.

export function isAuthError(status: number) {
  return status === 401 || status === 403;
}
