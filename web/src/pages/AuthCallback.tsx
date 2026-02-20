/**
 * OAuth 回调中间页 — 从 URL 解析 JWT Token 并跳转到首页。
 */

import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import api from '@/lib/api'

export default function AuthCallback() {
    const navigate = useNavigate()
    const [searchParams] = useSearchParams()
    const { setAuth } = useAuthStore()
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        const token = searchParams.get('token')
        if (!token) {
            setError('未收到登录凭证')
            return
        }

        // 存储 token 并获取用户信息
        useAuthStore.getState().setToken(token)

        api
            .get('/auth/me', {
                headers: { Authorization: `Bearer ${token}` },
            })
            .then(({ data }) => {
                setAuth(token, data)
                navigate('/', { replace: true })
            })
            .catch(() => {
                setError('获取用户信息失败，请重新登录')
                useAuthStore.getState().logout()
            })
    }, [searchParams, setAuth, navigate])

    if (error) {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <div className="glass-card p-8 text-center">
                    <p className="text-[var(--color-danger)] mb-4">{error}</p>
                    <button className="btn-primary" onClick={() => navigate('/login')}>
                        返回登录
                    </button>
                </div>
            </div>
        )
    }

    return (
        <div className="min-h-screen flex items-center justify-center">
            <div className="flex flex-col items-center gap-4">
                <span className="animate-spin inline-block w-8 h-8 border-3 border-[var(--color-primary)]/30 border-t-[var(--color-primary)] rounded-full" />
                <p className="text-[var(--color-text-muted)]">正在登录…</p>
            </div>
        </div>
    )
}
