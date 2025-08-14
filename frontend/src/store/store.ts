import { configureStore } from '@reduxjs/toolkit';
import { authApi } from '@/services/authApi';
import { filesApi } from '@/services/filesApi';
import { chatApi } from '@/services/chatApi';
import { databaseApi } from '@/services/databaseApi';
import authSlice from './slices/authSlice';
import fileSlice from './slices/fileSlice';
import chatSlice from './slices/chatSlice';
import uiSlice from './slices/uiSlice';

export const store = configureStore({
  reducer: {
    // RTK Query APIs
    [authApi.reducerPath]: authApi.reducer,
    [filesApi.reducerPath]: filesApi.reducer,
    [chatApi.reducerPath]: chatApi.reducer,
    [databaseApi.reducerPath]: databaseApi.reducer,
    
    // Slice reducers
    auth: authSlice,
    files: fileSlice,
    chat: chatSlice,
    ui: uiSlice,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware({
      serializableCheck: {
        ignoredActions: [
          // Ignore these action types
          'persist/FLUSH',
          'persist/REHYDRATE',
          'persist/PAUSE',
          'persist/PERSIST',
          'persist/PURGE',
          'persist/REGISTER',
        ],
        ignoredPaths: ['files.uploadQueue'],
      },
    })
    .concat(authApi.middleware)
    .concat(filesApi.middleware)
    .concat(chatApi.middleware)
    .concat(databaseApi.middleware),
  devTools: process.env.NODE_ENV !== 'production',
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;