import { createSlice, PayloadAction } from '@reduxjs/toolkit';

export interface FileMetadata {
  id: string;
  filename: string;
  originalName: string;
  fileType: string;
  fileSize: number;
  mimeType: string;
  uploadedAt: string;
  uploadedBy: string;
  status: 'uploading' | 'processing' | 'completed' | 'failed';
  processingProgress: number;
  categories: string[];
  source: 'upload' | 'screenshot' | 'audio' | 'video' | 'document';
  extractedText?: string;
  summary?: string;
  tags: string[];
  url?: string;
  thumbnailUrl?: string;
  error?: string;
}

export interface UploadTask {
  id: string;
  file: File;
  progress: number;
  status: 'pending' | 'uploading' | 'processing' | 'completed' | 'failed';
  error?: string;
  metadata?: FileMetadata;
}

export interface ProcessingStats {
  totalFiles: number;
  processingFiles: number;
  completedFiles: number;
  failedFiles: number;
  categorizedFiles: number;
  extractedTextFiles: number;
  vectorizedFiles: number;
}

interface FileState {
  files: FileMetadata[];
  uploadQueue: UploadTask[];
  selectedFiles: string[];
  filters: {
    category: string[];
    fileType: string[];
    status: string[];
    dateRange: {
      start: string | null;
      end: string | null;
    };
    searchTerm: string;
  };
  sortBy: 'uploadedAt' | 'filename' | 'fileSize' | 'status';
  sortOrder: 'asc' | 'desc';
  currentPage: number;
  itemsPerPage: number;
  totalCount: number;
  loading: boolean;
  processingStats: ProcessingStats;
  bulkActions: {
    selectedCount: number;
    inProgress: boolean;
    action: string | null;
  };
  dragOver: boolean;
  lastSync: string | null;
}

const initialState: FileState = {
  files: [],
  uploadQueue: [],
  selectedFiles: [],
  filters: {
    category: [],
    fileType: [],
    status: [],
    dateRange: {
      start: null,
      end: null,
    },
    searchTerm: '',
  },
  sortBy: 'uploadedAt',
  sortOrder: 'desc',
  currentPage: 1,
  itemsPerPage: 25,
  totalCount: 0,
  loading: false,
  processingStats: {
    totalFiles: 0,
    processingFiles: 0,
    completedFiles: 0,
    failedFiles: 0,
    categorizedFiles: 0,
    extractedTextFiles: 0,
    vectorizedFiles: 0,
  },
  bulkActions: {
    selectedCount: 0,
    inProgress: false,
    action: null,
  },
  dragOver: false,
  lastSync: null,
};

const fileSlice = createSlice({
  name: 'files',
  initialState,
  reducers: {
    // File Management
    setFiles: (state, action: PayloadAction<{ files: FileMetadata[]; totalCount: number }>) => {
      state.files = action.payload.files;
      state.totalCount = action.payload.totalCount;
      state.lastSync = new Date().toISOString();
    },
    addFile: (state, action: PayloadAction<FileMetadata>) => {
      state.files.unshift(action.payload);
      state.totalCount += 1;
    },
    updateFile: (state, action: PayloadAction<FileMetadata>) => {
      const index = state.files.findIndex(file => file.id === action.payload.id);
      if (index !== -1) {
        state.files[index] = action.payload;
      }
    },
    removeFile: (state, action: PayloadAction<string>) => {
      state.files = state.files.filter(file => file.id !== action.payload);
      state.totalCount -= 1;
      state.selectedFiles = state.selectedFiles.filter(id => id !== action.payload);
    },
    
    // Upload Queue Management
    addToUploadQueue: (state, action: PayloadAction<UploadTask[]>) => {
      state.uploadQueue.push(...action.payload);
    },
    updateUploadTask: (state, action: PayloadAction<UploadTask>) => {
      const index = state.uploadQueue.findIndex(task => task.id === action.payload.id);
      if (index !== -1) {
        state.uploadQueue[index] = action.payload;
      }
    },
    removeFromUploadQueue: (state, action: PayloadAction<string>) => {
      state.uploadQueue = state.uploadQueue.filter(task => task.id !== action.payload);
    },
    clearUploadQueue: (state) => {
      state.uploadQueue = [];
    },
    
    // Selection Management
    toggleFileSelection: (state, action: PayloadAction<string>) => {
      const fileId = action.payload;
      const index = state.selectedFiles.indexOf(fileId);
      if (index > -1) {
        state.selectedFiles.splice(index, 1);
      } else {
        state.selectedFiles.push(fileId);
      }
      state.bulkActions.selectedCount = state.selectedFiles.length;
    },
    selectAllFiles: (state) => {
      state.selectedFiles = state.files.map(file => file.id);
      state.bulkActions.selectedCount = state.selectedFiles.length;
    },
    clearSelection: (state) => {
      state.selectedFiles = [];
      state.bulkActions.selectedCount = 0;
    },
    
    // Filtering and Sorting
    setFilters: (state, action: PayloadAction<Partial<typeof initialState.filters>>) => {
      state.filters = { ...state.filters, ...action.payload };
      state.currentPage = 1; // Reset to first page when filters change
    },
    setSorting: (state, action: PayloadAction<{ sortBy: typeof initialState.sortBy; sortOrder: typeof initialState.sortOrder }>) => {
      state.sortBy = action.payload.sortBy;
      state.sortOrder = action.payload.sortOrder;
    },
    setPage: (state, action: PayloadAction<number>) => {
      state.currentPage = action.payload;
    },
    setItemsPerPage: (state, action: PayloadAction<number>) => {
      state.itemsPerPage = action.payload;
      state.currentPage = 1; // Reset to first page
    },
    
    // UI States
    setLoading: (state, action: PayloadAction<boolean>) => {
      state.loading = action.payload;
    },
    setDragOver: (state, action: PayloadAction<boolean>) => {
      state.dragOver = action.payload;
    },
    
    // Statistics
    updateProcessingStats: (state, action: PayloadAction<ProcessingStats>) => {
      state.processingStats = action.payload;
    },
    
    // Bulk Actions
    setBulkAction: (state, action: PayloadAction<{ action: string; inProgress: boolean }>) => {
      state.bulkActions.action = action.payload.action;
      state.bulkActions.inProgress = action.payload.inProgress;
    },
    clearBulkAction: (state) => {
      state.bulkActions.action = null;
      state.bulkActions.inProgress = false;
    },
    
    // Reset
    resetFileState: () => initialState,
  },
});

export const {
  setFiles,
  addFile,
  updateFile,
  removeFile,
  addToUploadQueue,
  updateUploadTask,
  removeFromUploadQueue,
  clearUploadQueue,
  toggleFileSelection,
  selectAllFiles,
  clearSelection,
  setFilters,
  setSorting,
  setPage,
  setItemsPerPage,
  setLoading,
  setDragOver,
  updateProcessingStats,
  setBulkAction,
  clearBulkAction,
  resetFileState,
} = fileSlice.actions;

export default fileSlice.reducer;