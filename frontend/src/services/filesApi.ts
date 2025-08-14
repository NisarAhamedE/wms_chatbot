import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';
import { RootState } from '@/store/store';
import { FileMetadata } from '@/store/slices/fileSlice';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000/api';

export interface FileUploadRequest {
  files: FileList;
  category?: string;
  tags?: string[];
  source: 'upload' | 'screenshot' | 'audio' | 'video' | 'document';
}

export interface FileUploadResponse {
  files: FileMetadata[];
  success: boolean;
  message: string;
}

export interface FileListRequest {
  page?: number;
  limit?: number;
  category?: string[];
  fileType?: string[];
  status?: string[];
  searchTerm?: string;
  sortBy?: 'uploadedAt' | 'filename' | 'fileSize' | 'status';
  sortOrder?: 'asc' | 'desc';
  dateRange?: {
    start: string;
    end: string;
  };
}

export interface FileListResponse {
  files: FileMetadata[];
  totalCount: number;
  currentPage: number;
  totalPages: number;
  hasNext: boolean;
  hasPrev: boolean;
}

export interface FileProcessingRequest {
  fileId: string;
  extractText?: boolean;
  categorize?: boolean;
  generateSummary?: boolean;
  extractKeywords?: boolean;
}

export interface FileProcessingResponse {
  fileId: string;
  status: 'processing' | 'completed' | 'failed';
  progress: number;
  results?: {
    extractedText?: string;
    categories?: string[];
    summary?: string;
    keywords?: string[];
    confidence?: number;
  };
  error?: string;
}

export interface BulkActionRequest {
  fileIds: string[];
  action: 'delete' | 'reprocess' | 'categorize' | 'export' | 'archive';
  params?: Record<string, any>;
}

export interface BulkActionResponse {
  success: boolean;
  message: string;
  processedCount: number;
  failedCount: number;
  results: Array<{
    fileId: string;
    success: boolean;
    error?: string;
  }>;
}

export interface FileExportRequest {
  fileIds?: string[];
  format: 'json' | 'csv' | 'excel' | 'pdf';
  includeContent?: boolean;
  includeMetadata?: boolean;
  filters?: FileListRequest;
}

export interface FileExportResponse {
  downloadUrl: string;
  filename: string;
  expiresAt: string;
}

export interface ProcessingStatsResponse {
  totalFiles: number;
  processingFiles: number;
  completedFiles: number;
  failedFiles: number;
  categorizedFiles: number;
  extractedTextFiles: number;
  vectorizedFiles: number;
  storageUsed: number;
  storageLimit: number;
  processingQueue: number;
  avgProcessingTime: number;
}

export interface FileSearchRequest {
  query: string;
  categories?: string[];
  fileTypes?: string[];
  semanticSearch?: boolean;
  limit?: number;
}

export interface FileSearchResponse {
  files: FileMetadata[];
  totalCount: number;
  searchTime: number;
  suggestions?: string[];
}

export const filesApi = createApi({
  reducerPath: 'filesApi',
  baseQuery: fetchBaseQuery({
    baseUrl: `${API_BASE_URL}/files`,
    prepareHeaders: (headers, { getState }) => {
      const token = (getState() as RootState).auth.token;
      if (token) {
        headers.set('authorization', `Bearer ${token}`);
      }
      return headers;
    },
  }),
  tagTypes: ['File', 'ProcessingStats', 'FileContent'],
  endpoints: (builder) => ({
    // File Upload and Management
    uploadFiles: builder.mutation<FileUploadResponse, FileUploadRequest>({
      query: ({ files, category, tags, source }) => {
        const formData = new FormData();
        Array.from(files).forEach((file) => {
          formData.append('files', file);
        });
        if (category) formData.append('category', category);
        if (tags) formData.append('tags', JSON.stringify(tags));
        formData.append('source', source);

        return {
          url: '/upload',
          method: 'POST',
          body: formData,
        };
      },
      invalidatesTags: ['File', 'ProcessingStats'],
    }),

    getFiles: builder.query<FileListResponse, FileListRequest>({
      query: (params) => ({
        url: '/',
        params,
      }),
      providesTags: ['File'],
    }),

    getFile: builder.query<FileMetadata, string>({
      query: (fileId) => `/${fileId}`,
      providesTags: (result, error, fileId) => [{ type: 'File', id: fileId }],
    }),

    updateFile: builder.mutation<FileMetadata, { fileId: string; updates: Partial<FileMetadata> }>({
      query: ({ fileId, updates }) => ({
        url: `/${fileId}`,
        method: 'PUT',
        body: updates,
      }),
      invalidatesTags: (result, error, { fileId }) => [
        { type: 'File', id: fileId },
        'File',
      ],
    }),

    deleteFile: builder.mutation<{ success: boolean; message: string }, string>({
      query: (fileId) => ({
        url: `/${fileId}`,
        method: 'DELETE',
      }),
      invalidatesTags: (result, error, fileId) => [
        { type: 'File', id: fileId },
        'File',
        'ProcessingStats',
      ],
    }),

    // File Processing
    processFile: builder.mutation<FileProcessingResponse, FileProcessingRequest>({
      query: ({ fileId, ...options }) => ({
        url: `/${fileId}/process`,
        method: 'POST',
        body: options,
      }),
      invalidatesTags: (result, error, { fileId }) => [
        { type: 'File', id: fileId },
        'ProcessingStats',
      ],
    }),

    getProcessingStatus: builder.query<FileProcessingResponse, string>({
      query: (fileId) => `/${fileId}/processing-status`,
      providesTags: (result, error, fileId) => [{ type: 'File', id: fileId }],
    }),

    retryProcessing: builder.mutation<FileProcessingResponse, string>({
      query: (fileId) => ({
        url: `/${fileId}/retry-processing`,
        method: 'POST',
      }),
      invalidatesTags: (result, error, fileId) => [
        { type: 'File', id: fileId },
        'ProcessingStats',
      ],
    }),

    // Bulk Operations
    bulkAction: builder.mutation<BulkActionResponse, BulkActionRequest>({
      query: (data) => ({
        url: '/bulk-action',
        method: 'POST',
        body: data,
      }),
      invalidatesTags: ['File', 'ProcessingStats'],
    }),

    bulkUpload: builder.mutation<FileUploadResponse, { 
      files: FileList; 
      options: Omit<FileUploadRequest, 'files'> 
    }>({
      query: ({ files, options }) => {
        const formData = new FormData();
        Array.from(files).forEach((file) => {
          formData.append('files', file);
        });
        Object.entries(options).forEach(([key, value]) => {
          if (value !== undefined) {
            formData.append(key, typeof value === 'object' ? JSON.stringify(value) : String(value));
          }
        });

        return {
          url: '/bulk-upload',
          method: 'POST',
          body: formData,
        };
      },
      invalidatesTags: ['File', 'ProcessingStats'],
    }),

    // Export and Download
    exportFiles: builder.mutation<FileExportResponse, FileExportRequest>({
      query: (data) => ({
        url: '/export',
        method: 'POST',
        body: data,
      }),
    }),

    downloadFile: builder.query<Blob, string>({
      query: (fileId) => ({
        url: `/${fileId}/download`,
        responseHandler: (response) => response.blob(),
      }),
    }),

    // Search and Discovery
    searchFiles: builder.query<FileSearchResponse, FileSearchRequest>({
      query: (params) => ({
        url: '/search',
        params,
      }),
      providesTags: ['File'],
    }),

    getFileSuggestions: builder.query<{ suggestions: string[] }, string>({
      query: (query) => ({
        url: '/suggestions',
        params: { query },
      }),
    }),

    // Content Access
    getFileContent: builder.query<{ content: string; metadata: FileMetadata }, string>({
      query: (fileId) => `/${fileId}/content`,
      providesTags: (result, error, fileId) => [{ type: 'FileContent', id: fileId }],
    }),

    getFilePreview: builder.query<{ previewUrl: string; type: string }, string>({
      query: (fileId) => `/${fileId}/preview`,
      providesTags: (result, error, fileId) => [{ type: 'FileContent', id: fileId }],
    }),

    // Statistics and Analytics
    getProcessingStats: builder.query<ProcessingStatsResponse, void>({
      query: () => '/stats',
      providesTags: ['ProcessingStats'],
    }),

    getFilesByCategory: builder.query<Record<string, number>, void>({
      query: () => '/stats/by-category',
      providesTags: ['ProcessingStats'],
    }),

    getProcessingHistory: builder.query<Array<{
      date: string;
      processed: number;
      failed: number;
      avgTime: number;
    }>, { days?: number }>({
      query: (params) => ({
        url: '/stats/processing-history',
        params,
      }),
      providesTags: ['ProcessingStats'],
    }),

    // File Relationships
    getRelatedFiles: builder.query<FileMetadata[], string>({
      query: (fileId) => `/${fileId}/related`,
      providesTags: (result, error, fileId) => [{ type: 'File', id: fileId }],
    }),

    getSimilarFiles: builder.query<FileMetadata[], { fileId: string; limit?: number }>({
      query: ({ fileId, limit = 10 }) => ({
        url: `/${fileId}/similar`,
        params: { limit },
      }),
      providesTags: (result, error, { fileId }) => [{ type: 'File', id: fileId }],
    }),

    // Validation and Health
    validateFiles: builder.mutation<{
      valid: number;
      invalid: number;
      details: Array<{ fileId: string; issues: string[] }>;
    }, { fileIds?: string[] }>({
      query: (data) => ({
        url: '/validate',
        method: 'POST',
        body: data,
      }),
    }),

    repairCorruptedFiles: builder.mutation<BulkActionResponse, { fileIds: string[] }>({
      query: (data) => ({
        url: '/repair',
        method: 'POST',
        body: data,
      }),
      invalidatesTags: ['File', 'ProcessingStats'],
    }),
  }),
});

export const {
  useUploadFilesMutation,
  useGetFilesQuery,
  useGetFileQuery,
  useUpdateFileMutation,
  useDeleteFileMutation,
  useProcessFileMutation,
  useGetProcessingStatusQuery,
  useRetryProcessingMutation,
  useBulkActionMutation,
  useBulkUploadMutation,
  useExportFilesMutation,
  useLazyDownloadFileQuery,
  useSearchFilesQuery,
  useGetFileSuggestionsQuery,
  useGetFileContentQuery,
  useGetFilePreviewQuery,
  useGetProcessingStatsQuery,
  useGetFilesByCategoryQuery,
  useGetProcessingHistoryQuery,
  useGetRelatedFilesQuery,
  useGetSimilarFilesQuery,
  useValidateFilesMutation,
  useRepairCorruptedFilesMutation,
} = filesApi;