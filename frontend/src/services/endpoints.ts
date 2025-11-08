export const AuthEndpoints = {
  SIGN_UP: "/signup",
  CONFIRM_SIGNUP: "/confirm-signup",
  SIGN_IN: "/signin",
  RESEND_CONFIRMATION: "/resend-confirmation",
  ME: "/me",
  REFRESH_TOKEN: "/refresh-token",
} as const;

export const MoveEndpoints = {
  SUBMIT_MOVE: "/move",
  CHECKLISTS: "/checklists",
} as const;

export type AuthEndpoint = typeof AuthEndpoints[keyof typeof AuthEndpoints];
export type MoveEndpoint = typeof MoveEndpoints[keyof typeof MoveEndpoints];






