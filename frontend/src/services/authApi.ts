import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';
import { RootState } from '@/store/store';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000/api';

export interface LoginRequest {
  username: string;
  password: string;
  rememberMe?: boolean;
}

export interface LoginResponse {
  user: {
    id: string;
    username: string;
    email: string;
    role: string;
    preferences: {
      theme: 'light' | 'dark';
      language: string;
      notifications: boolean;
    };
  };
  token: string;
  refreshToken: string;
  expiresIn: number;
}

export interface RefreshTokenRequest {
  refreshToken: string;
}

export interface RefreshTokenResponse {
  token: string;
  refreshToken: string;
  expiresIn: number;
}

export interface RegisterRequest {
  username: string;
  email: string;
  password: string;
  confirmPassword: string;
  role?: string;
}

export interface PasswordResetRequest {
  email: string;
}

export interface PasswordResetConfirmRequest {
  token: string;
  newPassword: string;
  confirmPassword: string;
}

export interface UpdateProfileRequest {
  email?: string;
  preferences?: {
    theme?: 'light' | 'dark';
    language?: string;
    notifications?: boolean;
  };
}

export interface ChangePasswordRequest {
  currentPassword: string;
  newPassword: string;
  confirmPassword: string;
}

export const authApi = createApi({
  reducerPath: 'authApi',
  baseQuery: fetchBaseQuery({
    baseUrl: `${API_BASE_URL}/auth`,
    prepareHeaders: (headers, { getState }) => {
      const token = (getState() as RootState).auth.token;
      if (token) {
        headers.set('authorization', `Bearer ${token}`);
      }
      headers.set('content-type', 'application/json');
      return headers;
    },
  }),
  tagTypes: ['User', 'Auth'],
  endpoints: (builder) => ({
    // Authentication
    login: builder.mutation<LoginResponse, LoginRequest>({
      query: (credentials) => ({
        url: '/login',
        method: 'POST',
        body: credentials,
      }),
      invalidatesTags: ['User', 'Auth'],
    }),

    logout: builder.mutation<void, void>({
      query: () => ({
        url: '/logout',
        method: 'POST',
      }),
      invalidatesTags: ['User', 'Auth'],
    }),

    refreshToken: builder.mutation<RefreshTokenResponse, RefreshTokenRequest>({
      query: (data) => ({
        url: '/refresh',
        method: 'POST',
        body: data,
      }),
    }),

    register: builder.mutation<LoginResponse, RegisterRequest>({
      query: (userData) => ({
        url: '/register',
        method: 'POST',
        body: userData,
      }),
      invalidatesTags: ['User', 'Auth'],
    }),

    // Password Management
    requestPasswordReset: builder.mutation<{ message: string }, PasswordResetRequest>({
      query: (data) => ({
        url: '/password-reset',
        method: 'POST',
        body: data,
      }),
    }),

    confirmPasswordReset: builder.mutation<{ message: string }, PasswordResetConfirmRequest>({
      query: (data) => ({
        url: '/password-reset/confirm',
        method: 'POST',
        body: data,
      }),
    }),

    changePassword: builder.mutation<{ message: string }, ChangePasswordRequest>({
      query: (data) => ({
        url: '/change-password',
        method: 'POST',
        body: data,
      }),
      invalidatesTags: ['User'],
    }),

    // Profile Management
    getCurrentUser: builder.query<LoginResponse['user'], void>({
      query: () => '/me',
      providesTags: ['User'],
    }),

    updateProfile: builder.mutation<LoginResponse['user'], UpdateProfileRequest>({
      query: (data) => ({
        url: '/profile',
        method: 'PUT',
        body: data,
      }),
      invalidatesTags: ['User'],
    }),

    // Session Management
    validateSession: builder.query<{ valid: boolean; user?: LoginResponse['user'] }, void>({
      query: () => '/validate',
      providesTags: ['Auth'],
    }),

    // Security
    getUserSessions: builder.query<Array<{
      id: string;
      userAgent: string;
      ipAddress: string;
      createdAt: string;
      lastActive: string;
      current: boolean;
    }>, void>({
      query: () => '/sessions',
      providesTags: ['Auth'],
    }),

    revokeSession: builder.mutation<{ message: string }, { sessionId: string }>({
      query: ({ sessionId }) => ({
        url: `/sessions/${sessionId}`,
        method: 'DELETE',
      }),
      invalidatesTags: ['Auth'],
    }),

    revokeAllSessions: builder.mutation<{ message: string }, void>({
      query: () => ({
        url: '/sessions',
        method: 'DELETE',
      }),
      invalidatesTags: ['Auth'],
    }),

    // Two-Factor Authentication
    enableTwoFactor: builder.mutation<{ qrCode: string; secret: string }, void>({
      query: () => ({
        url: '/2fa/enable',
        method: 'POST',
      }),
      invalidatesTags: ['User'],
    }),

    confirmTwoFactor: builder.mutation<{ message: string }, { token: string }>({
      query: (data) => ({
        url: '/2fa/confirm',
        method: 'POST',
        body: data,
      }),
      invalidatesTags: ['User'],
    }),

    disableTwoFactor: builder.mutation<{ message: string }, { token: string }>({
      query: (data) => ({
        url: '/2fa/disable',
        method: 'POST',
        body: data,
      }),
      invalidatesTags: ['User'],
    }),

    verifyTwoFactor: builder.mutation<{ message: string }, { token: string }>({
      query: (data) => ({
        url: '/2fa/verify',
        method: 'POST',
        body: data,
      }),
    }),
  }),
});

export const {
  useLoginMutation,
  useLogoutMutation,
  useRefreshTokenMutation,
  useRegisterMutation,
  useRequestPasswordResetMutation,
  useConfirmPasswordResetMutation,
  useChangePasswordMutation,
  useGetCurrentUserQuery,
  useUpdateProfileMutation,
  useValidateSessionQuery,
  useGetUserSessionsQuery,
  useRevokeSessionMutation,
  useRevokeAllSessionsMutation,
  useEnableTwoFactorMutation,
  useConfirmTwoFactorMutation,
  useDisableTwoFactorMutation,
  useVerifyTwoFactorMutation,
} = authApi;