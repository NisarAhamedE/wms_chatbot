import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';
import { RootState } from '@/store/store';
import { ChatMessage, ChatSession, AgentInfo } from '@/store/slices/chatSlice';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000/api';

export interface SendMessageRequest {
  content: string;
  sessionId?: string;
  agentId?: string;
  category?: string;
  subcategory?: string;
  contextFiles?: string[];
  attachments?: Array<{
    id: string;
    type: 'file' | 'image' | 'document';
    name: string;
  }>;
}

export interface SendMessageResponse {
  message: ChatMessage;
  session: ChatSession;
  suggestions?: string[];
}

export interface CreateSessionRequest {
  title: string;
  category?: string;
  agentId?: string;
  initialMessage?: string;
}

export interface GetSessionsRequest {
  page?: number;
  limit?: number;
  category?: string;
  searchTerm?: string;
  sortBy?: 'createdAt' | 'updatedAt' | 'title';
  sortOrder?: 'asc' | 'desc';
  dateRange?: {
    start: string;
    end: string;
  };
}

export interface GetSessionsResponse {
  sessions: ChatSession[];
  totalCount: number;
  currentPage: number;
  totalPages: number;
}

export interface GetMessagesRequest {
  sessionId: string;
  page?: number;
  limit?: number;
  beforeId?: string;
  afterId?: string;
}

export interface GetMessagesResponse {
  messages: ChatMessage[];
  hasMore: boolean;
  nextCursor?: string;
  prevCursor?: string;
}

export interface UpdateMessageRequest {
  messageId: string;
  content?: string;
  reactions?: {
    helpful?: boolean;
    accurate?: boolean;
    feedback?: string;
  };
}

export interface AgentConfigRequest {
  agentId: string;
  config: {
    temperature?: number;
    maxTokens?: number;
    systemPrompt?: string;
    enabledFeatures?: string[];
    contextWindow?: number;
  };
}

export interface ChatStatsResponse {
  totalSessions: number;
  totalMessages: number;
  avgResponseTime: number;
  mostUsedAgent: string;
  totalTokensUsed: number;
  categoriesUsed: Record<string, number>;
  dailyUsage: Array<{
    date: string;
    sessions: number;
    messages: number;
    tokens: number;
  }>;
}

export interface ExportChatRequest {
  sessionIds?: string[];
  format: 'json' | 'txt' | 'markdown' | 'pdf';
  includeMetadata?: boolean;
  dateRange?: {
    start: string;
    end: string;
  };
}

export interface ExportChatResponse {
  downloadUrl: string;
  filename: string;
  expiresAt: string;
}

export const chatApi = createApi({
  reducerPath: 'chatApi',
  baseQuery: fetchBaseQuery({
    baseUrl: `${API_BASE_URL}/chat`,
    prepareHeaders: (headers, { getState }) => {
      const token = (getState() as RootState).auth.token;
      if (token) {
        headers.set('authorization', `Bearer ${token}`);
      }
      headers.set('content-type', 'application/json');
      return headers;
    },
  }),
  tagTypes: ['Session', 'Message', 'Agent', 'ChatStats'],
  endpoints: (builder) => ({
    // Session Management
    createSession: builder.mutation<ChatSession, CreateSessionRequest>({
      query: (data) => ({
        url: '/sessions',
        method: 'POST',
        body: data,
      }),
      invalidatesTags: ['Session', 'ChatStats'],
    }),

    getSessions: builder.query<GetSessionsResponse, GetSessionsRequest>({
      query: (params) => ({
        url: '/sessions',
        params,
      }),
      providesTags: ['Session'],
    }),

    getSession: builder.query<ChatSession, string>({
      query: (sessionId) => `/sessions/${sessionId}`,
      providesTags: (result, error, sessionId) => [{ type: 'Session', id: sessionId }],
    }),

    updateSession: builder.mutation<ChatSession, { 
      sessionId: string; 
      updates: Partial<ChatSession> 
    }>({
      query: ({ sessionId, updates }) => ({
        url: `/sessions/${sessionId}`,
        method: 'PUT',
        body: updates,
      }),
      invalidatesTags: (result, error, { sessionId }) => [
        { type: 'Session', id: sessionId },
        'Session',
      ],
    }),

    deleteSession: builder.mutation<{ success: boolean; message: string }, string>({
      query: (sessionId) => ({
        url: `/sessions/${sessionId}`,
        method: 'DELETE',
      }),
      invalidatesTags: (result, error, sessionId) => [
        { type: 'Session', id: sessionId },
        'Session',
        'ChatStats',
      ],
    }),

    duplicateSession: builder.mutation<ChatSession, string>({
      query: (sessionId) => ({
        url: `/sessions/${sessionId}/duplicate`,
        method: 'POST',
      }),
      invalidatesTags: ['Session'],
    }),

    // Message Management
    sendMessage: builder.mutation<SendMessageResponse, SendMessageRequest>({
      query: (data) => ({
        url: '/messages',
        method: 'POST',
        body: data,
      }),
      invalidatesTags: (result, error, { sessionId }) => [
        { type: 'Session', id: sessionId },
        'Session',
        'Message',
        'ChatStats',
      ],
    }),

    getMessages: builder.query<GetMessagesResponse, GetMessagesRequest>({
      query: ({ sessionId, ...params }) => ({
        url: `/sessions/${sessionId}/messages`,
        params,
      }),
      providesTags: (result, error, { sessionId }) => [
        { type: 'Message', id: sessionId },
      ],
    }),

    updateMessage: builder.mutation<ChatMessage, UpdateMessageRequest>({
      query: ({ messageId, ...data }) => ({
        url: `/messages/${messageId}`,
        method: 'PUT',
        body: data,
      }),
      invalidatesTags: (result, error, { messageId }) => [
        { type: 'Message', id: messageId },
        'Message',
      ],
    }),

    deleteMessage: builder.mutation<{ success: boolean; message: string }, string>({
      query: (messageId) => ({
        url: `/messages/${messageId}`,
        method: 'DELETE',
      }),
      invalidatesTags: ['Message', 'Session'],
    }),

    regenerateResponse: builder.mutation<ChatMessage, {
      messageId: string;
      agentId?: string;
      temperature?: number;
    }>({
      query: ({ messageId, ...params }) => ({
        url: `/messages/${messageId}/regenerate`,
        method: 'POST',
        body: params,
      }),
      invalidatesTags: ['Message'],
    }),

    // Agent Management
    getAgents: builder.query<AgentInfo[], {
      category?: string;
      subcategory?: string;
      active?: boolean;
    }>({
      query: (params) => ({
        url: '/agents',
        params,
      }),
      providesTags: ['Agent'],
    }),

    getAgent: builder.query<AgentInfo, string>({
      query: (agentId) => `/agents/${agentId}`,
      providesTags: (result, error, agentId) => [{ type: 'Agent', id: agentId }],
    }),

    updateAgentConfig: builder.mutation<AgentInfo, AgentConfigRequest>({
      query: ({ agentId, config }) => ({
        url: `/agents/${agentId}/config`,
        method: 'PUT',
        body: config,
      }),
      invalidatesTags: (result, error, { agentId }) => [
        { type: 'Agent', id: agentId },
        'Agent',
      ],
    }),

    testAgent: builder.mutation<{
      success: boolean;
      response: string;
      metrics: {
        responseTime: number;
        tokensUsed: number;
        confidence: number;
      };
    }, {
      agentId: string;
      testMessage: string;
    }>({
      query: ({ agentId, testMessage }) => ({
        url: `/agents/${agentId}/test`,
        method: 'POST',
        body: { message: testMessage },
      }),
    }),

    // Search and Discovery
    searchMessages: builder.query<{
      messages: ChatMessage[];
      totalCount: number;
      searchTime: number;
    }, {
      query: string;
      sessionIds?: string[];
      categories?: string[];
      agents?: string[];
      dateRange?: {
        start: string;
        end: string;
      };
      limit?: number;
    }>({
      query: (params) => ({
        url: '/search',
        params,
      }),
      providesTags: ['Message'],
    }),

    getMessageSuggestions: builder.query<{ suggestions: string[] }, {
      sessionId?: string;
      agentId?: string;
      context?: string;
    }>({
      query: (params) => ({
        url: '/suggestions',
        params,
      }),
    }),

    // Analytics and Statistics
    getChatStats: builder.query<ChatStatsResponse, {
      dateRange?: {
        start: string;
        end: string;
      };
      granularity?: 'hour' | 'day' | 'week' | 'month';
    }>({
      query: (params) => ({
        url: '/stats',
        params,
      }),
      providesTags: ['ChatStats'],
    }),

    getAgentPerformance: builder.query<Array<{
      agentId: string;
      agentName: string;
      totalMessages: number;
      avgResponseTime: number;
      successRate: number;
      userSatisfaction: number;
      tokensUsed: number;
    }>, {
      dateRange?: {
        start: string;
        end: string;
      };
    }>({
      query: (params) => ({
        url: '/stats/agents',
        params,
      }),
      providesTags: ['ChatStats'],
    }),

    // Export and Backup
    exportChat: builder.mutation<ExportChatResponse, ExportChatRequest>({
      query: (data) => ({
        url: '/export',
        method: 'POST',
        body: data,
      }),
    }),

    importChat: builder.mutation<{
      success: boolean;
      importedSessions: number;
      importedMessages: number;
      errors: string[];
    }, {
      file: File;
      mergeStrategy: 'replace' | 'merge' | 'skip';
    }>({
      query: ({ file, mergeStrategy }) => {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('mergeStrategy', mergeStrategy);

        return {
          url: '/import',
          method: 'POST',
          body: formData,
        };
      },
      invalidatesTags: ['Session', 'Message', 'ChatStats'],
    }),

    // Real-time Features
    getTypingStatus: builder.query<{
      sessionId: string;
      isTyping: boolean;
      userId?: string;
    }, string>({
      query: (sessionId) => `/sessions/${sessionId}/typing`,
    }),

    setTypingStatus: builder.mutation<void, {
      sessionId: string;
      isTyping: boolean;
    }>({
      query: ({ sessionId, isTyping }) => ({
        url: `/sessions/${sessionId}/typing`,
        method: 'POST',
        body: { isTyping },
      }),
    }),

    // Context Management
    addContextFile: builder.mutation<{
      success: boolean;
      message: string;
    }, {
      sessionId: string;
      fileId: string;
    }>({
      query: ({ sessionId, fileId }) => ({
        url: `/sessions/${sessionId}/context`,
        method: 'POST',
        body: { fileId },
      }),
      invalidatesTags: (result, error, { sessionId }) => [
        { type: 'Session', id: sessionId },
      ],
    }),

    removeContextFile: builder.mutation<{
      success: boolean;
      message: string;
    }, {
      sessionId: string;
      fileId: string;
    }>({
      query: ({ sessionId, fileId }) => ({
        url: `/sessions/${sessionId}/context/${fileId}`,
        method: 'DELETE',
      }),
      invalidatesTags: (result, error, { sessionId }) => [
        { type: 'Session', id: sessionId },
      ],
    }),

    getContextFiles: builder.query<Array<{
      fileId: string;
      filename: string;
      fileType: string;
      addedAt: string;
    }>, string>({
      query: (sessionId) => `/sessions/${sessionId}/context`,
      providesTags: (result, error, sessionId) => [
        { type: 'Session', id: sessionId },
      ],
    }),
  }),
});

export const {
  useCreateSessionMutation,
  useGetSessionsQuery,
  useGetSessionQuery,
  useUpdateSessionMutation,
  useDeleteSessionMutation,
  useDuplicateSessionMutation,
  useSendMessageMutation,
  useGetMessagesQuery,
  useUpdateMessageMutation,
  useDeleteMessageMutation,
  useRegenerateResponseMutation,
  useGetAgentsQuery,
  useGetAgentQuery,
  useUpdateAgentConfigMutation,
  useTestAgentMutation,
  useSearchMessagesQuery,
  useGetMessageSuggestionsQuery,
  useGetChatStatsQuery,
  useGetAgentPerformanceQuery,
  useExportChatMutation,
  useImportChatMutation,
  useGetTypingStatusQuery,
  useSetTypingStatusMutation,
  useAddContextFileMutation,
  useRemoveContextFileMutation,
  useGetContextFilesQuery,
} = chatApi;