import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'
import { postRoadmap } from '../api'

export interface RoadmapItem {
  uid: string
  title: string
  kind: string
  status?: 'completed' | 'in_progress' | 'planned'
  [key: string]: any
}

interface RoadmapState {
  items: RoadmapItem[]
  loading: boolean
  error: string | null
}

const initialState: RoadmapState = {
  items: [],
  loading: false,
  error: null,
}

export const fetchRoadmap = createAsyncThunk(
  'roadmap/fetch',
  async (subjectUid: string | null) => {
    const response = await postRoadmap({
      subject_uid: subjectUid,
      progress: {},
      limit: 30
    })
    return response.items as RoadmapItem[]
  }
)

const roadmapSlice = createSlice({
  name: 'roadmap',
  initialState,
  reducers: {
    clearRoadmap: (state) => {
      state.items = []
    }
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchRoadmap.pending, (state) => {
        state.loading = true
        state.error = null
      })
      .addCase(fetchRoadmap.fulfilled, (state, action) => {
        state.loading = false
        state.items = action.payload
      })
      .addCase(fetchRoadmap.rejected, (state, action) => {
        state.loading = false
        state.error = action.error.message || 'Ошибка загрузки роадмапа'
      })
  },
})

export const { clearRoadmap } = roadmapSlice.actions
export default roadmapSlice.reducer