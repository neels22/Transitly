export interface SignUpRequest {
  email: string;
  password: string;
  first_name: string;
  last_name: string;
  username: string;
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
    email_verified: boolean;
  };
}

export interface ResendConfirmationRequest {
  username: string;
}

export interface ResendConfirmationResponse {
  message: string;
}

const API_BASE_URL = 'http://localhost:8000';

class ApiError extends Error {
  public status: number;
  
  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

async function makeRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  
  try {
    const response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    });

    const data = await response.json();

    if (!response.ok) {
      throw new ApiError(response.status, data.detail || 'An error occurred');
    }

    return data;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    throw new ApiError(0, 'Network error or server unavailable');
  }
}

async function makeFormRequest<T>(
  endpoint: string,
  formData: Record<string, string>
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  
  try {
    const body = new URLSearchParams(formData);
    
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: body.toString(),
    });

    const data = await response.json();

    if (!response.ok) {
      throw new ApiError(response.status, data.detail || 'An error occurred');
    }

    return data;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    throw new ApiError(0, 'Network error or server unavailable');
  }
}

export const authService = {
  async signUp(request: SignUpRequest): Promise<SignUpResponse> {
    return makeFormRequest<SignUpResponse>('/signup', {
      email: request.email,
      password: request.password,
      first_name: request.first_name,
      last_name: request.last_name,
      username: request.username,
    });
  },

  async confirmSignUp(request: ConfirmSignUpRequest): Promise<ConfirmSignUpResponse> {
    return makeFormRequest<ConfirmSignUpResponse>('/confirm-signup', {
      username: request.username,
      code: request.code,
    });
  },

  async signIn(request: SignInRequest): Promise<SignInResponse> {
    return makeFormRequest<SignInResponse>('/signin', {
      email: request.email,
      password: request.password,
    });
  },

  async resendConfirmation(request: ResendConfirmationRequest): Promise<ResendConfirmationResponse> {
    return makeFormRequest<ResendConfirmationResponse>('/resend-confirmation', {
      username: request.username,
    });
  },

  async getCurrentUser(accessToken: string) {
    return makeRequest('/me', {
      headers: {
        Authorization: `Bearer ${accessToken}`,
      },
    });
  },

  async refreshToken(refreshToken: string) {
    return makeFormRequest('/refresh-token', {
      refresh_token: refreshToken,
    });
  },
};

export { ApiError };
