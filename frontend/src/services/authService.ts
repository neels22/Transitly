export interface SignUpRequest {
  email: string;
  password: string;
  first_name: string;
  last_name: string;
  username: string;
  phone: string; // ← ADDED
}

export interface SignUpResponse {
  message: string;
  user_sub: string;
  confirmation_required: boolean;
}

export interface ConfirmSignUpRequest {
  username: string;
  code: string;
}

export interface ConfirmSignUpResponse {
  message: string;
}

export interface SignInRequest {
  email: string;
  password: string;
}

export interface SignInResponse {
  message: string;
  tokens: {
    access_token: string;
    id_token: string;
    refresh_token?: string;
    expires_in?: number;
  };
  user: {
    userId: string;
    email: string;
    name: string;
    phone: string; // ← ADDED
    email_verified: boolean;
  };
}

export interface ResendConfirmationRequest {
  username: string;
}

export interface ResendConfirmationResponse {
  message: string;
}
import { makeRequest, makeFormRequest } from "./http";

export const authService = {
  async signUp(request: SignUpRequest): Promise<SignUpResponse> {
    return makeFormRequest<SignUpResponse>("/signup", {
      email: request.email,
      password: request.password,
      first_name: request.first_name,
      last_name: request.last_name,
      username: request.username,
      phone: request.phone, // ← ADDED
    });
  },

  async confirmSignUp(
    request: ConfirmSignUpRequest
  ): Promise<ConfirmSignUpResponse> {
    return makeFormRequest<ConfirmSignUpResponse>("/confirm-signup", {
      username: request.username,
      code: request.code,
    });
  },

  async signIn(request: SignInRequest): Promise<SignInResponse> {
    return makeFormRequest<SignInResponse>("/signin", {
      email: request.email,
      password: request.password,
    });
  },

  async resendConfirmation(
    request: ResendConfirmationRequest
  ): Promise<ResendConfirmationResponse> {
    return makeFormRequest<ResendConfirmationResponse>("/resend-confirmation", {
      username: request.username,
    });
  },

  async getCurrentUser(accessToken: string) {
    return makeRequest("/me", {
      headers: {
        Authorization: `Bearer ${accessToken}`,
      },
    });
  },

  async refreshToken(refreshToken: string) {
    return makeFormRequest("/refresh-token", {
      refresh_token: refreshToken,
    });
  },
};
export { ApiError } from "./http";
