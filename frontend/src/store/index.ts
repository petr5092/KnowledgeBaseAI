// store/index.ts
import { configureStore } from '@reduxjs/toolkit';
import transactionsReducer from './transactionsSlice';
import appReducer from './appSlice';
import analyticsReducer from './analyticsSlice';
import roadmapReducer from './roadmapSlice';
import editReducer from './editSlice';
import exploreReducer from './exploreSlice'

export const store = configureStore({
  reducer: {
    transactions: transactionsReducer,
    app: appReducer,
    analytics: analyticsReducer,
    roadmap: roadmapReducer,
    edit: editReducer,
    explore: exploreReducer,
  },
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;