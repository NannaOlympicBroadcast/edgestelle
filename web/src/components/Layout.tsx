/**
 * 全局布局 — 侧边导航 + 顶部栏 + 内容区。
 */

import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import {
    LayoutDashboard,
    FileText,
    Key,
    Settings,
    LogOut,
    Radio,
} from 'lucide-react'

const navItems = [
    { to: '/', icon: LayoutDashboard, label: '仪表盘' },
    { to: '/templates', icon: FileText, label: '模板管理' },
    { to: '/settings/api-keys', icon: Key, label: 'API Key' },
    { to: '/settings/system', icon: Settings, label: '系统设置' },
]

export default function Layout() {
    const { user, logout } = useAuthStore()
    const navigate = useNavigate()

    const handleLogout = () => {
        logout()
        navigate('/login')
    }

    return (
        <div className="flex h-screen overflow-hidden">
            {/* ── 侧边栏 ── */}
            <aside className="w-64 flex-shrink-0 flex flex-col border-r border-[var(--color-border)] bg-[var(--color-surface)]">
                {/* Logo */}
                <div className="px-6 py-5 border-b border-[var(--color-border)]">
                    <div className="flex items-center gap-3">
                        <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-indigo-500 to-cyan-400 flex items-center justify-center">
                            <Radio className="w-5 h-5 text-white" />
                        </div>
                        <div>
                            <h1 className="text-lg font-bold tracking-tight">EdgeStelle</h1>
                            <p className="text-xs text-[var(--color-text-muted)]">IoT Testing Platform</p>
                        </div>
                    </div>
                </div>

                {/* Nav */}
                <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
                    {navItems.map((item) => (
                        <NavLink
                            key={item.to}
                            to={item.to}
                            end={item.to === '/'}
                            className={({ isActive }) =>
                                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${isActive
                                    ? 'bg-[var(--color-primary)]/15 text-[var(--color-primary-light)] border border-[var(--color-primary)]/30'
                                    : 'text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)] hover:text-[var(--color-text)]'
                                }`
                            }
                        >
                            <item.icon className="w-4.5 h-4.5" />
                            {item.label}
                        </NavLink>
                    ))}
                </nav>

                {/* 用户信息 */}
                <div className="px-3 py-4 border-t border-[var(--color-border)]">
                    <div className="flex items-center gap-3 px-3 py-2">
                        {user?.avatar_url ? (
                            <img
                                src={user.avatar_url}
                                alt={user.nickname}
                                className="w-8 h-8 rounded-full ring-2 ring-[var(--color-border)]"
                            />
                        ) : (
                            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-indigo-500 to-purple-500 flex items-center justify-center text-xs font-bold text-white">
                                {user?.nickname?.charAt(0) || 'U'}
                            </div>
                        )}
                        <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium truncate">{user?.nickname || '用户'}</p>
                            <p className="text-xs text-[var(--color-text-muted)] truncate">
                                {user?.is_admin ? '管理员' : '成员'}
                            </p>
                        </div>
                        <button
                            onClick={handleLogout}
                            className="p-1.5 rounded-lg hover:bg-[var(--color-surface-hover)] text-[var(--color-text-muted)] hover:text-[var(--color-danger)] transition-colors"
                            title="登出"
                        >
                            <LogOut className="w-4 h-4" />
                        </button>
                    </div>
                </div>
            </aside>

            {/* ── 主内容区 ── */}
            <main className="flex-1 overflow-y-auto p-8">
                <Outlet />
            </main>
        </div>
    )
}
