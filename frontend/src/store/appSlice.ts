// store/appSlice.ts
import { createSlice, type PayloadAction } from '@reduxjs/toolkit';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  createdAt: number;
}

interface AppState {
  selectedUid: string;
  messages: ChatMessage[];
  isChatOpen: boolean;
}

const initialState: AppState = {
  selectedUid: 'TOP-DEMO',
  isChatOpen: false,
  messages: [{
    id: 'initial',
    role: 'assistant',
    text: 'Привет! Я ассистент KnowledgeBase.',
    createdAt: Date.now(),
  }],
};

const appSlice = createSlice({
  name: 'app',
  initialState,
  reducers: {
    setSelectedUid: (state, action: PayloadAction<string>) => {
      state.selectedUid = action.payload;
    },
    toggleChat: (state) => {
      state.isChatOpen = !state.isChatOpen;
    },
    addMessage: (state, action: PayloadAction<ChatMessage>) => {
      state.messages.push(action.payload);
    },
  },
});

export const { setSelectedUid, toggleChat, addMessage } = appSlice.actions;
export default appSlice.reducer;