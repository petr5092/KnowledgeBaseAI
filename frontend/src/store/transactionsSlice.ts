// store/transactionsSlice.ts
import { createSlice, type PayloadAction } from '@reduxjs/toolkit';

export type TxStatus = "pending" | "success" | "failed";

export type TxEntry = {
  txId: string;
  createdAt: number;
  status: TxStatus;
  error?: string;
  payload: any;
};

interface TxState {
  entries: TxEntry[];
}

const initialState: TxState = {
  entries: [],
};

const transactionsSlice = createSlice({
  name: 'transactions',
  initialState,
  reducers: {
    addTransaction: (state, action: PayloadAction<any>) => {
      const txId = `tx_${Date.now()}_${Math.floor(Math.random() * 1e6)}`;
      state.entries.unshift({
        txId,
        createdAt: Date.now(),
        status: "pending",
        payload: action.payload,
      });
    },
    markSuccess: (state, action: PayloadAction<string>) => {
      const tx = state.entries.find(e => e.txId === action.payload);
      if (tx) tx.status = "success";
    },
    markFailed: (state, action: PayloadAction<{ txId: string; error?: string }>) => {
      const tx = state.entries.find(e => e.txId === action.payload.txId);
      if (tx) {
        tx.status = "failed";
        tx.error = action.payload.error;
      }
    },
  },
});

export const { addTransaction, markSuccess, markFailed } = transactionsSlice.actions;
export default transactionsSlice.reducer;