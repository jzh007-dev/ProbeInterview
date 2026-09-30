import {
  clearAuthSession,
  readAuthSession,
  type AuthSessionSnapshot,
} from "./auth-store"
import {
  clearCurrentUserSnapshot,
  readCurrentUserSnapshot,
  type CurrentUserSnapshot,
} from "./current-user-store"

export interface ValidSessionPair {
  session: AuthSessionSnapshot
  currentUser: CurrentUserSnapshot
}

export function readValidSessionPair(
  now: Date = new Date(),
): ValidSessionPair | null {
  const session = readAuthSession(now)
  if (session === null) {
    return null
  }
  const currentUser = readCurrentUserSnapshot(now)
  if (currentUser === null) {
    return null
  }
  return {session, currentUser}
}

export function clearAuthState(): void {
  clearAuthSession()
  clearCurrentUserSnapshot()
}
