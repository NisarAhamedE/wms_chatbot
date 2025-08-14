import { createSlice, PayloadAction } from '@reduxjs/toolkit';

export interface Notification {
  id: string;
  type: 'success' | 'error' | 'warning' | 'info';
  title: string;
  message: string;
  timestamp: string;
  autoHide: boolean;
  duration?: number;
  actions?: {
    label: string;
    action: string;
  }[];
}

export interface ConfirmDialog {
  isOpen: boolean;
  title: string;
  message: string;
  confirmText: string;
  cancelText: string;
  onConfirm: string; // Action type to dispatch
  onCancel?: string; // Action type to dispatch
  data?: any; // Additional data to pass to the action
}

export interface Modal {
  id: string;
  type: 'file-preview' | 'agent-config' | 'database-connection' | 'bulk-action' | 'settings';
  isOpen: boolean;
  title: string;
  data?: any;
  size?: 'small' | 'medium' | 'large' | 'fullscreen';
}

interface UIState {
  // Navigation
  sidebarOpen: boolean;
  currentPage: string;
  breadcrumbs: Array<{ label: string; path: string }>;
  
  // Theme and Layout
  theme: 'light' | 'dark';
  sidebarWidth: number;
  headerHeight: number;
  contentPadding: number;
  
  // Loading States
  globalLoading: boolean;
  loadingStates: Record<string, boolean>;
  
  // Notifications
  notifications: Notification[];
  notificationSettings: {
    position: 'top-right' | 'top-left' | 'bottom-right' | 'bottom-left';
    maxVisible: number;
    defaultDuration: number;
  };
  
  // Dialogs and Modals
  confirmDialog: ConfirmDialog;
  modals: Modal[];
  
  // Connection Status
  connectionStatus: {
    api: 'connected' | 'disconnected' | 'connecting' | 'error';
    database: 'connected' | 'disconnected' | 'connecting' | 'error';
    weaviate: 'connected' | 'disconnected' | 'connecting' | 'error';
    lastCheck: string | null;
  };
  
  // Page-specific UI States
  fileManagement: {
    viewMode: 'list' | 'grid' | 'timeline';
    showPreview: boolean;
    previewFileId: string | null;
    showFilters: boolean;
    showUploadArea: boolean;
  };
  
  dashboard: {
    widgetLayout: Array<{
      id: string;
      x: number;
      y: number;
      w: number;
      h: number;
    }>;
    timeRange: '1h' | '6h' | '24h' | '7d' | '30d' | 'custom';
    customDateRange: {
      start: string | null;
      end: string | null;
    };
    autoRefresh: boolean;
    refreshInterval: number;
  };
  
  chatbot: {
    showAgentPanel: boolean;
    showContextFiles: boolean;
    showHistory: boolean;
    messageLayout: 'compact' | 'comfortable' | 'spacious';
    showTypingIndicator: boolean;
  };
  
  database: {
    showSchema: boolean;
    selectedTable: string | null;
    queryMode: 'visual' | 'sql';
    showQueryHistory: boolean;
  };
  
  // Search and Filters
  globalSearch: {
    isOpen: boolean;
    query: string;
    filters: string[];
    results: any[];
    loading: boolean;
  };
  
  // Keyboard Shortcuts
  shortcutsEnabled: boolean;
  keyboardShortcuts: Record<string, string>;
  
  // Performance
  performanceMetrics: {
    pageLoadTime: number;
    apiResponseTimes: Record<string, number>;
    errorCount: number;
    lastOptimization: string | null;
  };
  
  // Error Boundary
  errorBoundary: {
    hasError: boolean;
    errorMessage: string | null;
    errorStack: string | null;
    lastErrorTime: string | null;
  };
}

const initialState: UIState = {
  sidebarOpen: true,
  currentPage: '/dashboard',
  breadcrumbs: [{ label: 'Dashboard', path: '/dashboard' }],
  
  theme: 'light',
  sidebarWidth: 280,
  headerHeight: 64,
  contentPadding: 24,
  
  globalLoading: false,
  loadingStates: {},
  
  notifications: [],
  notificationSettings: {
    position: 'top-right',
    maxVisible: 5,
    defaultDuration: 5000,
  },
  
  confirmDialog: {
    isOpen: false,
    title: '',
    message: '',
    confirmText: 'Confirm',
    cancelText: 'Cancel',
    onConfirm: '',
  },
  modals: [],
  
  connectionStatus: {
    api: 'disconnected',
    database: 'disconnected',
    weaviate: 'disconnected',
    lastCheck: null,
  },
  
  fileManagement: {
    viewMode: 'list',
    showPreview: false,
    previewFileId: null,
    showFilters: true,
    showUploadArea: true,
  },
  
  dashboard: {
    widgetLayout: [],
    timeRange: '24h',
    customDateRange: {
      start: null,
      end: null,
    },
    autoRefresh: true,
    refreshInterval: 30000,
  },
  
  chatbot: {
    showAgentPanel: true,
    showContextFiles: true,
    showHistory: true,
    messageLayout: 'comfortable',
    showTypingIndicator: true,
  },
  
  database: {
    showSchema: true,
    selectedTable: null,
    queryMode: 'visual',
    showQueryHistory: true,
  },
  
  globalSearch: {
    isOpen: false,
    query: '',
    filters: [],
    results: [],
    loading: false,
  },
  
  shortcutsEnabled: true,
  keyboardShortcuts: {
    'ctrl+k': 'OPEN_GLOBAL_SEARCH',
    'ctrl+b': 'TOGGLE_SIDEBAR',
    'ctrl+n': 'NEW_CHAT_SESSION',
    'ctrl+shift+f': 'TOGGLE_FILE_FILTERS',
  },
  
  performanceMetrics: {
    pageLoadTime: 0,
    apiResponseTimes: {},
    errorCount: 0,
    lastOptimization: null,
  },
  
  errorBoundary: {
    hasError: false,
    errorMessage: null,
    errorStack: null,
    lastErrorTime: null,
  },
};

const uiSlice = createSlice({
  name: 'ui',
  initialState,
  reducers: {
    // Navigation
    toggleSidebar: (state) => {
      state.sidebarOpen = !state.sidebarOpen;
    },
    setSidebarOpen: (state, action: PayloadAction<boolean>) => {
      state.sidebarOpen = action.payload;
    },
    setCurrentPage: (state, action: PayloadAction<string>) => {
      state.currentPage = action.payload;
    },
    setBreadcrumbs: (state, action: PayloadAction<Array<{ label: string; path: string }>>) => {
      state.breadcrumbs = action.payload;
    },
    
    // Theme and Layout
    setTheme: (state, action: PayloadAction<'light' | 'dark'>) => {
      state.theme = action.payload;
    },
    setSidebarWidth: (state, action: PayloadAction<number>) => {
      state.sidebarWidth = action.payload;
    },
    
    // Loading States
    setGlobalLoading: (state, action: PayloadAction<boolean>) => {
      state.globalLoading = action.payload;
    },
    setLoadingState: (state, action: PayloadAction<{ key: string; loading: boolean }>) => {
      state.loadingStates[action.payload.key] = action.payload.loading;
    },
    clearLoadingState: (state, action: PayloadAction<string>) => {
      delete state.loadingStates[action.payload];
    },
    
    // Notifications
    addNotification: (state, action: PayloadAction<Omit<Notification, 'id' | 'timestamp'>>) => {
      const notification: Notification = {
        ...action.payload,
        id: Date.now().toString(),
        timestamp: new Date().toISOString(),
      };
      state.notifications.unshift(notification);
      
      // Limit visible notifications
      if (state.notifications.length > state.notificationSettings.maxVisible) {
        state.notifications = state.notifications.slice(0, state.notificationSettings.maxVisible);
      }
    },
    removeNotification: (state, action: PayloadAction<string>) => {
      state.notifications = state.notifications.filter(n => n.id !== action.payload);
    },
    clearNotifications: (state) => {
      state.notifications = [];
    },
    updateNotificationSettings: (state, action: PayloadAction<Partial<typeof initialState.notificationSettings>>) => {
      state.notificationSettings = { ...state.notificationSettings, ...action.payload };
    },
    
    // Dialogs and Modals
    openConfirmDialog: (state, action: PayloadAction<Omit<ConfirmDialog, 'isOpen'>>) => {
      state.confirmDialog = { ...action.payload, isOpen: true };
    },
    closeConfirmDialog: (state) => {
      state.confirmDialog.isOpen = false;
    },
    openModal: (state, action: PayloadAction<Omit<Modal, 'isOpen'>>) => {
      const modal: Modal = { ...action.payload, isOpen: true };
      state.modals.push(modal);
    },
    closeModal: (state, action: PayloadAction<string>) => {
      state.modals = state.modals.filter(m => m.id !== action.payload);
    },
    closeAllModals: (state) => {
      state.modals = [];
    },
    
    // Connection Status
    updateConnectionStatus: (state, action: PayloadAction<Partial<typeof initialState.connectionStatus>>) => {
      state.connectionStatus = { ...state.connectionStatus, ...action.payload };
      if (action.payload.api || action.payload.database || action.payload.weaviate) {
        state.connectionStatus.lastCheck = new Date().toISOString();
      }
    },
    
    // Page-specific UI States
    updateFileManagementUI: (state, action: PayloadAction<Partial<typeof initialState.fileManagement>>) => {
      state.fileManagement = { ...state.fileManagement, ...action.payload };
    },
    updateDashboardUI: (state, action: PayloadAction<Partial<typeof initialState.dashboard>>) => {
      state.dashboard = { ...state.dashboard, ...action.payload };
    },
    updateChatbotUI: (state, action: PayloadAction<Partial<typeof initialState.chatbot>>) => {
      state.chatbot = { ...state.chatbot, ...action.payload };
    },
    updateDatabaseUI: (state, action: PayloadAction<Partial<typeof initialState.database>>) => {
      state.database = { ...state.database, ...action.payload };
    },
    
    // Global Search
    openGlobalSearch: (state) => {
      state.globalSearch.isOpen = true;
    },
    closeGlobalSearch: (state) => {
      state.globalSearch.isOpen = false;
      state.globalSearch.query = '';
      state.globalSearch.results = [];
    },
    setGlobalSearchQuery: (state, action: PayloadAction<string>) => {
      state.globalSearch.query = action.payload;
    },
    setGlobalSearchResults: (state, action: PayloadAction<any[]>) => {
      state.globalSearch.results = action.payload;
    },
    setGlobalSearchLoading: (state, action: PayloadAction<boolean>) => {
      state.globalSearch.loading = action.payload;
    },
    
    // Keyboard Shortcuts
    setShortcutsEnabled: (state, action: PayloadAction<boolean>) => {
      state.shortcutsEnabled = action.payload;
    },
    updateKeyboardShortcuts: (state, action: PayloadAction<Record<string, string>>) => {
      state.keyboardShortcuts = { ...state.keyboardShortcuts, ...action.payload };
    },
    
    // Performance Metrics
    updatePerformanceMetrics: (state, action: PayloadAction<Partial<typeof initialState.performanceMetrics>>) => {
      state.performanceMetrics = { ...state.performanceMetrics, ...action.payload };
    },
    recordApiResponseTime: (state, action: PayloadAction<{ endpoint: string; time: number }>) => {
      state.performanceMetrics.apiResponseTimes[action.payload.endpoint] = action.payload.time;
    },
    incrementErrorCount: (state) => {
      state.performanceMetrics.errorCount += 1;
    },
    
    // Error Boundary
    setErrorBoundary: (state, action: PayloadAction<{ 
      hasError: boolean; 
      errorMessage?: string; 
      errorStack?: string; 
    }>) => {
      state.errorBoundary = {
        hasError: action.payload.hasError,
        errorMessage: action.payload.errorMessage || null,
        errorStack: action.payload.errorStack || null,
        lastErrorTime: action.payload.hasError ? new Date().toISOString() : null,
      };
    },
    clearErrorBoundary: (state) => {
      state.errorBoundary = {
        hasError: false,
        errorMessage: null,
        errorStack: null,
        lastErrorTime: null,
      };
    },
    
    // Reset
    resetUIState: () => initialState,
  },
});

export const {
  toggleSidebar,
  setSidebarOpen,
  setCurrentPage,
  setBreadcrumbs,
  setTheme,
  setSidebarWidth,
  setGlobalLoading,
  setLoadingState,
  clearLoadingState,
  addNotification,
  removeNotification,
  clearNotifications,
  updateNotificationSettings,
  openConfirmDialog,
  closeConfirmDialog,
  openModal,
  closeModal,
  closeAllModals,
  updateConnectionStatus,
  updateFileManagementUI,
  updateDashboardUI,
  updateChatbotUI,
  updateDatabaseUI,
  openGlobalSearch,
  closeGlobalSearch,
  setGlobalSearchQuery,
  setGlobalSearchResults,
  setGlobalSearchLoading,
  setShortcutsEnabled,
  updateKeyboardShortcuts,
  updatePerformanceMetrics,
  recordApiResponseTime,
  incrementErrorCount,
  setErrorBoundary,
  clearErrorBoundary,
  resetUIState,
} = uiSlice.actions;

export default uiSlice.reducer;