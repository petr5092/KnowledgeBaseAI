// store/analyticsSlice.ts
import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import { getAnalyticsStats, type AnalyticsStats } from '../api';

export const fetchStats = createAsyncThunk('analytics/fetch', async () => {
  return await getAnalyticsStats();
});

interface AnalyticsState {
  data: AnalyticsStats | null;
  loading: boolean;
  error: string | null;
}

const analyticsSlice = createSlice({
  name: 'analytics',
  initialState: { data: null, loading: false, error: null } as AnalyticsState,
  reducers: {},
  extraReducers: (builder) => {
    builder
      .addCase(fetchStats.pending, (state) => { state.loading = true; })
      .addCase(fetchStats.fulfilled, (state, action) => {
        state.loading = false;
        state.data = action.payload;
      })
      .addCase(fetchStats.rejected, (state, action) => {
        state.loading = false;
        state.error = action.error.message || 'Error';
      });
  }
});

export default analyticsSlice.reducer;