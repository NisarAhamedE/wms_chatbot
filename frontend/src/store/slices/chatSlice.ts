import { createSlice, PayloadAction } from '@reduxjs/toolkit';

export interface ChatMessage {
  id: string;
  content: string;
  role: 'user' | 'assistant' | 'system';
  timestamp: string;
  category?: string;
  subcategory?: string;
  agent?: string;
  sources?: string[];
  metadata?: {
    queryType: 'general' | 'file_specific' | 'database' | 'analytics';
    confidence: number;
    processingTime: number;
    tokensUsed: number;
  };
  attachments?: {
    id: string;
    type: 'file' | 'image' | 'document';
    name: string;
    url: string;
  }[];
  reactions?: {
    helpful: boolean;
    accurate: boolean;
    feedback?: string;
  };
}

export interface ChatSession {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  category?: string;
  messageCount: number;
  lastMessage?: string;
  isActive: boolean;
}

export interface AgentInfo {
  id: string;
  name: string;
  category: string;
  subcategory: string;
  description: string;
  capabilities: string[];
  isActive: boolean;
  lastUsed?: string;
}

interface ChatState {
  // Current Session
  currentSession: ChatSession | null;
  messages: ChatMessage[];
  
  // Session Management
  sessions: ChatSession[];
  
  // Agent Management
  availableAgents: AgentInfo[];
  selectedAgent: AgentInfo | null;
  
  // UI State
  isTyping: boolean;
  isProcessing: boolean;
  inputValue: string;
  showAgentSelector: boolean;
  showFileAttachment: boolean;
  
  // Filters and Search
  filters: {
    category: string[];
    dateRange: {
      start: string | null;
      end: string | null;
    };
    agent: string[];
    searchTerm: string;
  };
  
  // Context and Settings
  contextFiles: string[];
  settings: {
    autoSave: boolean;
    showTimestamps: boolean;
    enableNotifications: boolean;
    maxMessagesPerSession: number;
    retainHistory: boolean;
  };
  
  // Statistics
  stats: {
    totalSessions: number;
    totalMessages: number;
    avgResponseTime: number;
    mostUsedAgent: string;
    totalTokensUsed: number;
  };
  
  // Error Handling
  error: string | null;
  lastSync: string | null;
}

const initialState: ChatState = {
  currentSession: null,
  messages: [],
  sessions: [],
  availableAgents: [],
  selectedAgent: null,
  isTyping: false,
  isProcessing: false,
  inputValue: '',
  showAgentSelector: false,
  showFileAttachment: false,
  filters: {
    category: [],
    dateRange: {
      start: null,
      end: null,
    },
    agent: [],
    searchTerm: '',
  },
  contextFiles: [],
  settings: {
    autoSave: true,
    showTimestamps: true,
    enableNotifications: true,
    maxMessagesPerSession: 100,
    retainHistory: true,
  },
  stats: {
    totalSessions: 0,
    totalMessages: 0,
    avgResponseTime: 0,
    mostUsedAgent: '',
    totalTokensUsed: 0,
  },
  error: null,
  lastSync: null,
};

const chatSlice = createSlice({
  name: 'chat',
  initialState,
  reducers: {
    // Session Management
    createSession: (state, action: PayloadAction<{ title: string; category?: string }>) => {
      const newSession: ChatSession = {
        id: Date.now().toString(),
        title: action.payload.title,
        category: action.payload.category,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        messageCount: 0,
        isActive: true,
      };
      
      // Deactivate current session
      if (state.currentSession) {
        state.currentSession.isActive = false;
      }
      
      state.currentSession = newSession;
      state.sessions.unshift(newSession);
      state.messages = [];
      state.stats.totalSessions += 1;
    },
    
    switchSession: (state, action: PayloadAction<string>) => {
      const session = state.sessions.find(s => s.id === action.payload);
      if (session) {
        // Deactivate current session
        if (state.currentSession) {
          state.currentSession.isActive = false;
        }
        
        session.isActive = true;
        state.currentSession = session;
        // Messages will be loaded separately via API call
        state.messages = [];
      }
    },
    
    deleteSession: (state, action: PayloadAction<string>) => {
      state.sessions = state.sessions.filter(s => s.id !== action.payload);
      if (state.currentSession?.id === action.payload) {
        state.currentSession = null;
        state.messages = [];
      }
      state.stats.totalSessions = Math.max(0, state.stats.totalSessions - 1);
    },
    
    updateSession: (state, action: PayloadAction<Partial<ChatSession> & { id: string }>) => {
      const sessionIndex = state.sessions.findIndex(s => s.id === action.payload.id);
      if (sessionIndex !== -1) {
        state.sessions[sessionIndex] = { ...state.sessions[sessionIndex], ...action.payload };
        if (state.currentSession?.id === action.payload.id) {
          state.currentSession = { ...state.currentSession, ...action.payload };
        }
      }
    },
    
    // Message Management
    addMessage: (state, action: PayloadAction<ChatMessage>) => {
      state.messages.push(action.payload);
      state.stats.totalMessages += 1;
      
      // Update current session
      if (state.currentSession) {
        state.currentSession.messageCount += 1;
        state.currentSession.lastMessage = action.payload.content.substring(0, 100);
        state.currentSession.updatedAt = new Date().toISOString();
        
        // Update session in sessions array
        const sessionIndex = state.sessions.findIndex(s => s.id === state.currentSession!.id);
        if (sessionIndex !== -1) {
          state.sessions[sessionIndex] = { ...state.currentSession };
        }
      }
    },
    
    updateMessage: (state, action: PayloadAction<ChatMessage>) => {
      const messageIndex = state.messages.findIndex(m => m.id === action.payload.id);
      if (messageIndex !== -1) {
        state.messages[messageIndex] = action.payload;
      }
    },
    
    deleteMessage: (state, action: PayloadAction<string>) => {
      state.messages = state.messages.filter(m => m.id !== action.payload);
      state.stats.totalMessages = Math.max(0, state.stats.totalMessages - 1);
    },
    
    clearMessages: (state) => {
      state.messages = [];
    },
    
    // Agent Management
    setAvailableAgents: (state, action: PayloadAction<AgentInfo[]>) => {
      state.availableAgents = action.payload;
    },
    
    selectAgent: (state, action: PayloadAction<AgentInfo | null>) => {
      state.selectedAgent = action.payload;
    },
    
    updateAgentUsage: (state, action: PayloadAction<string>) => {
      const agent = state.availableAgents.find(a => a.id === action.payload);
      if (agent) {
        agent.lastUsed = new Date().toISOString();
      }
    },
    
    // UI State Management
    setTyping: (state, action: PayloadAction<boolean>) => {
      state.isTyping = action.payload;
    },
    
    setProcessing: (state, action: PayloadAction<boolean>) => {
      state.isProcessing = action.payload;
    },
    
    setInputValue: (state, action: PayloadAction<string>) => {
      state.inputValue = action.payload;
    },
    
    toggleAgentSelector: (state) => {
      state.showAgentSelector = !state.showAgentSelector;
    },
    
    toggleFileAttachment: (state) => {
      state.showFileAttachment = !state.showFileAttachment;
    },
    
    // Context Management
    addContextFile: (state, action: PayloadAction<string>) => {
      if (!state.contextFiles.includes(action.payload)) {
        state.contextFiles.push(action.payload);
      }
    },
    
    removeContextFile: (state, action: PayloadAction<string>) => {
      state.contextFiles = state.contextFiles.filter(id => id !== action.payload);
    },
    
    clearContextFiles: (state) => {
      state.contextFiles = [];
    },
    
    // Filters and Settings
    setFilters: (state, action: PayloadAction<Partial<typeof initialState.filters>>) => {
      state.filters = { ...state.filters, ...action.payload };
    },
    
    updateSettings: (state, action: PayloadAction<Partial<typeof initialState.settings>>) => {
      state.settings = { ...state.settings, ...action.payload };
    },
    
    // Statistics
    updateStats: (state, action: PayloadAction<Partial<typeof initialState.stats>>) => {
      state.stats = { ...state.stats, ...action.payload };
    },
    
    // Error Handling
    setError: (state, action: PayloadAction<string | null>) => {
      state.error = action.payload;
    },
    
    // Data Loading
    setSessions: (state, action: PayloadAction<ChatSession[]>) => {
      state.sessions = action.payload;
      state.lastSync = new Date().toISOString();
    },
    
    setMessages: (state, action: PayloadAction<ChatMessage[]>) => {
      state.messages = action.payload;
    },
    
    // Reset
    resetChatState: () => initialState,
  },
});

export const {
  createSession,
  switchSession,
  deleteSession,
  updateSession,
  addMessage,
  updateMessage,
  deleteMessage,
  clearMessages,
  setAvailableAgents,
  selectAgent,
  updateAgentUsage,
  setTyping,
  setProcessing,
  setInputValue,
  toggleAgentSelector,
  toggleFileAttachment,
  addContextFile,
  removeContextFile,
  clearContextFiles,
  setFilters,
  updateSettings,
  updateStats,
  setError,
  setSessions,
  setMessages,
  resetChatState,
} = chatSlice.actions;

export default chatSlice.reducer;