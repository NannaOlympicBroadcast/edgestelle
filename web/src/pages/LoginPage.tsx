/**
 * 登录页 — 飞书授权登录入口。
 */

import { useState } from 'react'
import { Radio } from 'lucide-react'
import api from '@/lib/api'

export default function LoginPage() {
    const [loading, setLoading] = useState(false)

    const handleFeishuLogin = async () => {
        setLoading(true)
        try {
            const { data } = await api.get('/auth/feishu/login')
            window.location.href = data.authorize_url
        } catch {
            alert('无法获取飞书授权链接，请检查后端配置。')
            setLoading(false)
        }
    }

    return (
        <div className="min-h-screen flex items-center justify-center relative overflow-hidden">
            {/* Background effects */}
            <div className="absolute inset-0 bg-gradient-to-br from-indigo-950 via-slate-900 to-cyan-950" />
            <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl" />
            <div className="absolute bottom-1/4 right-1/4 w-80 h-80 bg-cyan-500/10 rounded-full blur-3xl" />

            <div className="relative glass-card p-10 w-full max-w-md animate-fade-in">
                {/* Logo */}
                <div className="flex flex-col items-center mb-8">
                    <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-indigo-500 to-cyan-400 flex items-center justify-center mb-4 animate-pulse-glow">
                        <Radio className="w-8 h-8 text-white" />
                    </div>
                    <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-indigo-400 to-cyan-400 bg-clip-text text-transparent">
                        EdgeStelle
                    </h1>
                    <p className="text-sm text-[var(--color-text-muted)] mt-2">
                        IoT 设备自动化测试与 AI 智能分析平台
                    </p>
                </div>

                {/* Feishu login button */}
                <button
                    onClick={handleFeishuLogin}
                    disabled={loading}
                    className="w-full btn-primary justify-center text-base py-3.5 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                    {loading ? (
                        <span className="animate-spin inline-block w-5 h-5 border-2 border-white/30 border-t-white rounded-full" />
                    ) : (
                        <>
                            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none">
                                <path d="M3 12.5L10.5 5L12 6.5L6 12.5L12 18.5L10.5 20L3 12.5Z" fill="currentColor" />
                                <path d="M11 12.5L18.5 5L20 6.5L14 12.5L20 18.5L18.5 20L11 12.5Z" fill="currentColor" />
                            </svg>
                            飞书授权登录
                        </>
                    )}
                </button>

                <p className="text-center text-xs text-[var(--color-text-muted)] mt-6">
                    首次登录将自动注册账号
                </p>
            </div>
        </div>
    )
}
