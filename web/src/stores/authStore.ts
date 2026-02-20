/**
 * Zustand 鉴权状态管理 — JWT Token + 用户信息。
 */

import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export interface User {
    id: string
    feishu_open_id: string
    nickname: string
    avatar_url: string | null
    is_admin: boolean
    created_at: string
}

interface AuthState {
    token: string | null
    user: User | null
    setAuth: (token: string, user: User) => void
    setToken: (token: string) => void
    setUser: (user: User) => void
    logout: () => void
    isAuthenticated: () => boolean
}

export const useAuthStore = create<AuthState>()(
    persist(
        (set, get) => ({
            token: null,
            user: null,
            setAuth: (token, user) => set({ token, user }),
            setToken: (token) => set({ token }),
            setUser: (user) => set({ user }),
            logout: () => set({ token: null, user: null }),
            isAuthenticated: () => !!get().token,
        }),
        {
            name: 'edgestelle-auth',
        }
    )
)
