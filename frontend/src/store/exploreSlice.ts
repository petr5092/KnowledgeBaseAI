import { createSlice, createAsyncThunk, type PayloadAction } from '@reduxjs/toolkit'
import { getViewport, type ViewportResponse } from '../api'

interface ExploreState {
  viewport: ViewportResponse | null
  depth: number
  loading: boolean
  error: string | null
}

const initialState: ExploreState = {
  viewport: null,
  depth: 1,
  loading: false,
  error: null,
}

// Асинхронный экшен для загрузки данных
export const fetchViewport = createAsyncThunk(
  'explore/fetchViewport',
  async ({ uid, depth }: { uid: string; depth: number }) => {
    return await getViewport({ center_uid: uid, depth })
  }
)

const exploreSlice = createSlice({
  name: 'explore',
  initialState,
  reducers: {
    setDepth: (state, action: PayloadAction<number>) => {
      state.depth = action.payload
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchViewport.pending, (state) => {
        state.loading = true
        state.error = null
      })
      .addCase(fetchViewport.fulfilled, (state, action) => {
        state.loading = false
        state.viewport = action.payload
      })
      .addCase(fetchViewport.rejected, (state, action) => {
        state.loading = false
        state.error = action.error.message || 'Ошибка загрузки'
      })
  },
})

export const { setDepth } = exploreSlice.actions
export default exploreSlice.reducer