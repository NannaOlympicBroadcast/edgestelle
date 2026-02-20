/**
 * App 根组件 — 路由配置。
 */

import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import Layout from '@/components/Layout'
import LoginPage from '@/pages/LoginPage'
import AuthCallback from '@/pages/AuthCallback'
import Dashboard from '@/pages/Dashboard'
import ReportDetail from '@/pages/ReportDetail'
import TemplatesPage from '@/pages/TemplatesPage'
import ApiKeysPage from '@/pages/ApiKeysPage'
import SystemSettingsPage from '@/pages/SystemSettingsPage'

function PrivateRoute({ children }: { children: React.ReactNode }) {
    const token = useAuthStore((s) => s.token)
    if (!token) return <Navigate to="/login" replace />
    return <>{children}</>
}

export default function App() {
    return (
        <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/auth/callback" element={<AuthCallback />} />
            <Route
                path="/"
                element={
                    <PrivateRoute>
                        <Layout />
                    </PrivateRoute>
                }
            >
                <Route index element={<Dashboard />} />
                <Route path="reports/:id" element={<ReportDetail />} />
                <Route path="templates" element={<TemplatesPage />} />
                <Route path="settings/api-keys" element={<ApiKeysPage />} />
                <Route path="settings/system" element={<SystemSettingsPage />} />
            </Route>
        </Routes>
    )
}
