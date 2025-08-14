import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';
import { RootState } from '@/store/store';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000/api';

export interface DatabaseConnection {
  id: string;
  name: string;
  type: 'postgresql' | 'mssql' | 'mysql' | 'weaviate';
  host: string;
  port: number;
  database: string;
  username: string;
  status: 'connected' | 'disconnected' | 'error' | 'testing';
  isDefault: boolean;
  createdAt: string;
  lastConnected?: string;
  error?: string;
}

export interface DatabaseSchema {
  tables: Array<{
    name: string;
    schema: string;
    type: 'table' | 'view';
    rowCount?: number;
    columns: Array<{
      name: string;
      type: string;
      nullable: boolean;
      primaryKey: boolean;
      foreignKey?: {
        table: string;
        column: string;
      };
      description?: string;
    }>;
    indexes: Array<{
      name: string;
      columns: string[];
      unique: boolean;
      type: string;
    }>;
    description?: string;
  }>;
  views: Array<{
    name: string;
    schema: string;
    definition: string;
    dependencies: string[];
  }>;
  procedures: Array<{
    name: string;
    schema: string;
    parameters: Array<{
      name: string;
      type: string;
      direction: 'in' | 'out' | 'inout';
    }>;
  }>;
  functions: Array<{
    name: string;
    schema: string;
    returnType: string;
    parameters: Array<{
      name: string;
      type: string;
    }>;
  }>;
}

export interface DatabaseConnectionRequest {
  name: string;
  type: 'postgresql' | 'mssql' | 'mysql';
  host: string;
  port: number;
  database: string;
  username: string;
  password: string;
  ssl?: boolean;
  timeout?: number;
  poolSize?: number;
  isDefault?: boolean;
}

export interface QueryRequest {
  connectionId: string;
  query: string;
  limit?: number;
  timeout?: number;
  explain?: boolean;
}

export interface QueryResponse {
  success: boolean;
  data?: Array<Record<string, any>>;
  columns?: Array<{
    name: string;
    type: string;
  }>;
  rowCount?: number;
  executionTime: number;
  error?: string;
  warnings?: string[];
  explain?: {
    plan: string;
    cost: number;
    rows: number;
  };
}

export interface QueryHistory {
  id: string;
  connectionId: string;
  connectionName: string;
  query: string;
  executedAt: string;
  executionTime: number;
  rowCount?: number;
  success: boolean;
  error?: string;
  userId: string;
}

export interface SavedQuery {
  id: string;
  name: string;
  description?: string;
  query: string;
  connectionId?: string;
  category?: string;
  tags: string[];
  isPublic: boolean;
  createdBy: string;
  createdAt: string;
  updatedAt: string;
  usage: number;
}

export interface QueryBuilderRequest {
  connectionId: string;
  operation: 'select' | 'insert' | 'update' | 'delete';
  table: string;
  columns?: string[];
  conditions?: Array<{
    column: string;
    operator: '=' | '!=' | '>' | '<' | '>=' | '<=' | 'LIKE' | 'IN' | 'BETWEEN';
    value: any;
    logic?: 'AND' | 'OR';
  }>;
  joins?: Array<{
    type: 'INNER' | 'LEFT' | 'RIGHT' | 'FULL';
    table: string;
    on: string;
  }>;
  groupBy?: string[];
  having?: string;
  orderBy?: Array<{
    column: string;
    direction: 'ASC' | 'DESC';
  }>;
  limit?: number;
  offset?: number;
  values?: Record<string, any>;
}

export interface DataExportRequest {
  connectionId: string;
  query?: string;
  table?: string;
  format: 'csv' | 'excel' | 'json' | 'sql';
  limit?: number;
  includeHeaders?: boolean;
}

export interface DataExportResponse {
  downloadUrl: string;
  filename: string;
  recordCount: number;
  fileSize: number;
  expiresAt: string;
}

export interface VectorStoreRequest {
  connectionId: string;
  data: Array<{
    id: string;
    content: string;
    metadata?: Record<string, any>;
    category?: string;
  }>;
  collection?: string;
}

export interface VectorSearchRequest {
  query: string;
  collection?: string;
  limit?: number;
  threshold?: number;
  filters?: Record<string, any>;
}

export interface VectorSearchResponse {
  results: Array<{
    id: string;
    content: string;
    metadata?: Record<string, any>;
    score: number;
    distance: number;
  }>;
  searchTime: number;
  totalResults: number;
}

export const databaseApi = createApi({
  reducerPath: 'databaseApi',
  baseQuery: fetchBaseQuery({
    baseUrl: `${API_BASE_URL}/database`,
    prepareHeaders: (headers, { getState }) => {
      const token = (getState() as RootState).auth.token;
      if (token) {
        headers.set('authorization', `Bearer ${token}`);
      }
      headers.set('content-type', 'application/json');
      return headers;
    },
  }),
  tagTypes: ['Connection', 'Schema', 'Query', 'SavedQuery', 'History'],
  endpoints: (builder) => ({
    // Connection Management
    getConnections: builder.query<DatabaseConnection[], void>({
      query: () => '/connections',
      providesTags: ['Connection'],
    }),

    getConnection: builder.query<DatabaseConnection, string>({
      query: (connectionId) => `/connections/${connectionId}`,
      providesTags: (result, error, connectionId) => [{ type: 'Connection', id: connectionId }],
    }),

    createConnection: builder.mutation<DatabaseConnection, DatabaseConnectionRequest>({
      query: (data) => ({
        url: '/connections',
        method: 'POST',
        body: data,
      }),
      invalidatesTags: ['Connection'],
    }),

    updateConnection: builder.mutation<DatabaseConnection, {
      connectionId: string;
      updates: Partial<DatabaseConnectionRequest>;
    }>({
      query: ({ connectionId, updates }) => ({
        url: `/connections/${connectionId}`,
        method: 'PUT',
        body: updates,
      }),
      invalidatesTags: (result, error, { connectionId }) => [
        { type: 'Connection', id: connectionId },
        'Connection',
      ],
    }),

    deleteConnection: builder.mutation<{ success: boolean; message: string }, string>({
      query: (connectionId) => ({
        url: `/connections/${connectionId}`,
        method: 'DELETE',
      }),
      invalidatesTags: (result, error, connectionId) => [
        { type: 'Connection', id: connectionId },
        'Connection',
        'Schema',
      ],
    }),

    testConnection: builder.mutation<{
      success: boolean;
      message: string;
      details?: {
        version: string;
        serverInfo: Record<string, any>;
        responseTime: number;
      };
    }, string>({
      query: (connectionId) => ({
        url: `/connections/${connectionId}/test`,
        method: 'POST',
      }),
      invalidatesTags: (result, error, connectionId) => [
        { type: 'Connection', id: connectionId },
      ],
    }),

    // Schema Management
    getSchema: builder.query<DatabaseSchema, string>({
      query: (connectionId) => `/connections/${connectionId}/schema`,
      providesTags: (result, error, connectionId) => [{ type: 'Schema', id: connectionId }],
    }),

    refreshSchema: builder.mutation<DatabaseSchema, string>({
      query: (connectionId) => ({
        url: `/connections/${connectionId}/schema/refresh`,
        method: 'POST',
      }),
      invalidatesTags: (result, error, connectionId) => [
        { type: 'Schema', id: connectionId },
      ],
    }),

    getTableInfo: builder.query<{
      table: DatabaseSchema['tables'][0];
      sampleData: Array<Record<string, any>>;
      statistics: {
        rowCount: number;
        columnCount: number;
        dataSize: string;
        lastUpdated?: string;
      };
    }, {
      connectionId: string;
      tableName: string;
      schema?: string;
    }>({
      query: ({ connectionId, tableName, schema }) => ({
        url: `/connections/${connectionId}/tables/${tableName}`,
        params: { schema },
      }),
      providesTags: (result, error, { connectionId, tableName }) => [
        { type: 'Schema', id: `${connectionId}-${tableName}` },
      ],
    }),

    // Query Execution
    executeQuery: builder.mutation<QueryResponse, QueryRequest>({
      query: ({ connectionId, ...data }) => ({
        url: `/connections/${connectionId}/query`,
        method: 'POST',
        body: data,
      }),
      invalidatesTags: ['History'],
    }),

    buildQuery: builder.mutation<{ query: string }, QueryBuilderRequest>({
      query: ({ connectionId, ...data }) => ({
        url: `/connections/${connectionId}/build-query`,
        method: 'POST',
        body: data,
      }),
    }),

    explainQuery: builder.mutation<{
      plan: string;
      cost: number;
      estimatedRows: number;
      warnings: string[];
    }, {
      connectionId: string;
      query: string;
    }>({
      query: ({ connectionId, query }) => ({
        url: `/connections/${connectionId}/explain`,
        method: 'POST',
        body: { query },
      }),
    }),

    validateQuery: builder.mutation<{
      valid: boolean;
      errors: string[];
      warnings: string[];
      suggestions: string[];
    }, {
      connectionId: string;
      query: string;
    }>({
      query: ({ connectionId, query }) => ({
        url: `/connections/${connectionId}/validate`,
        method: 'POST',
        body: { query },
      }),
    }),

    // Query History
    getQueryHistory: builder.query<{
      history: QueryHistory[];
      totalCount: number;
      currentPage: number;
    }, {
      connectionId?: string;
      page?: number;
      limit?: number;
      searchTerm?: string;
      dateRange?: {
        start: string;
        end: string;
      };
    }>({
      query: (params) => ({
        url: '/query-history',
        params,
      }),
      providesTags: ['History'],
    }),

    deleteQueryHistory: builder.mutation<{ success: boolean; message: string }, {
      historyIds?: string[];
      olderThan?: string;
      connectionId?: string;
    }>({
      query: (data) => ({
        url: '/query-history',
        method: 'DELETE',
        body: data,
      }),
      invalidatesTags: ['History'],
    }),

    // Saved Queries
    getSavedQueries: builder.query<{
      queries: SavedQuery[];
      totalCount: number;
    }, {
      category?: string;
      tags?: string[];
      searchTerm?: string;
      isPublic?: boolean;
      page?: number;
      limit?: number;
    }>({
      query: (params) => ({
        url: '/saved-queries',
        params,
      }),
      providesTags: ['SavedQuery'],
    }),

    getSavedQuery: builder.query<SavedQuery, string>({
      query: (queryId) => `/saved-queries/${queryId}`,
      providesTags: (result, error, queryId) => [{ type: 'SavedQuery', id: queryId }],
    }),

    saveQuery: builder.mutation<SavedQuery, Omit<SavedQuery, 'id' | 'createdAt' | 'updatedAt' | 'usage' | 'createdBy'>>({
      query: (data) => ({
        url: '/saved-queries',
        method: 'POST',
        body: data,
      }),
      invalidatesTags: ['SavedQuery'],
    }),

    updateSavedQuery: builder.mutation<SavedQuery, {
      queryId: string;
      updates: Partial<Omit<SavedQuery, 'id' | 'createdAt' | 'createdBy'>>;
    }>({
      query: ({ queryId, updates }) => ({
        url: `/saved-queries/${queryId}`,
        method: 'PUT',
        body: updates,
      }),
      invalidatesTags: (result, error, { queryId }) => [
        { type: 'SavedQuery', id: queryId },
        'SavedQuery',
      ],
    }),

    deleteSavedQuery: builder.mutation<{ success: boolean; message: string }, string>({
      query: (queryId) => ({
        url: `/saved-queries/${queryId}`,
        method: 'DELETE',
      }),
      invalidatesTags: (result, error, queryId) => [
        { type: 'SavedQuery', id: queryId },
        'SavedQuery',
      ],
    }),

    // Data Export
    exportData: builder.mutation<DataExportResponse, DataExportRequest>({
      query: ({ connectionId, ...data }) => ({
        url: `/connections/${connectionId}/export`,
        method: 'POST',
        body: data,
      }),
    }),

    // Vector Store Operations
    storeVectors: builder.mutation<{
      success: boolean;
      storedCount: number;
      errors: string[];
    }, VectorStoreRequest>({
      query: ({ connectionId, ...data }) => ({
        url: `/connections/${connectionId}/vectors`,
        method: 'POST',
        body: data,
      }),
    }),

    searchVectors: builder.query<VectorSearchResponse, VectorSearchRequest>({
      query: (params) => ({
        url: '/vectors/search',
        params,
      }),
    }),

    getVectorCollections: builder.query<Array<{
      name: string;
      objectCount: number;
      vectorDimensions: number;
      lastUpdated: string;
    }>, void>({
      query: () => '/vectors/collections',
    }),

    deleteVectorCollection: builder.mutation<{
      success: boolean;
      message: string;
    }, string>({
      query: (collectionName) => ({
        url: `/vectors/collections/${collectionName}`,
        method: 'DELETE',
      }),
    }),

    // Analytics and Performance
    getDatabaseStats: builder.query<{
      connections: number;
      totalQueries: number;
      avgQueryTime: number;
      errorRate: number;
      mostUsedTables: Array<{
        table: string;
        queryCount: number;
      }>;
      dailyUsage: Array<{
        date: string;
        queries: number;
        avgTime: number;
        errors: number;
      }>;
    }, {
      dateRange?: {
        start: string;
        end: string;
      };
    }>({
      query: (params) => ({
        url: '/stats',
        params,
      }),
    }),

    getSlowQueries: builder.query<Array<{
      query: string;
      connectionName: string;
      executionTime: number;
      executedAt: string;
      rowCount: number;
    }>, {
      threshold?: number;
      limit?: number;
      dateRange?: {
        start: string;
        end: string;
      };
    }>({
      query: (params) => ({
        url: '/stats/slow-queries',
        params,
      }),
    }),
  }),
});

export const {
  useGetConnectionsQuery,
  useGetConnectionQuery,
  useCreateConnectionMutation,
  useUpdateConnectionMutation,
  useDeleteConnectionMutation,
  useTestConnectionMutation,
  useGetSchemaQuery,
  useRefreshSchemaMutation,
  useGetTableInfoQuery,
  useExecuteQueryMutation,
  useBuildQueryMutation,
  useExplainQueryMutation,
  useValidateQueryMutation,
  useGetQueryHistoryQuery,
  useDeleteQueryHistoryMutation,
  useGetSavedQueriesQuery,
  useGetSavedQueryQuery,
  useSaveQueryMutation,
  useUpdateSavedQueryMutation,
  useDeleteSavedQueryMutation,
  useExportDataMutation,
  useStoreVectorsMutation,
  useSearchVectorsQuery,
  useGetVectorCollectionsQuery,
  useDeleteVectorCollectionMutation,
  useGetDatabaseStatsQuery,
  useGetSlowQueriesQuery,
} = databaseApi;