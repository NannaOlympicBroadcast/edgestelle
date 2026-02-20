/**
 * Dashboard 仪表盘 — 报告列表 + 统计卡片。
 */

import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Activity, AlertTriangle, CheckCircle, Clock } from 'lucide-react'
import api from '@/lib/api'

interface Report {
    id: string
    template_id: string
    device_id: string
    status: string
    created_at: string
    ai_analysis: string | null
}

export default function Dashboard() {
    const [reports, setReports] = useState<Report[]>([])
    const [loading, setLoading] = useState(true)
    const navigate = useNavigate()

    useEffect(() => {
        api.get('/reports?limit=50')
            .then(({ data }) => setReports(data))
            .catch(() => { })
            .finally(() => setLoading(false))
    }, [])

    const total = reports.length
    const analyzed = reports.filter((r) => r.status === 'analyzed').length
    const pending = reports.filter((r) => r.status === 'pending').length
    const devices = new Set(reports.map((r) => r.device_id)).size

    const stats = [
        { label: '总报告数', value: total, icon: Activity, color: 'from-indigo-500 to-purple-500' },
        { label: '已分析', value: analyzed, icon: CheckCircle, color: 'from-emerald-500 to-green-500' },
        { label: '待处理', value: pending, icon: Clock, color: 'from-amber-500 to-orange-500' },
        { label: '设备数', value: devices, icon: AlertTriangle, color: 'from-cyan-500 to-blue-500' },
    ]

    return (
        <div className="space-y-8 animate-fade-in">
            <div>
                <h1 className="text-2xl font-bold">仪表盘</h1>
                <p className="text-[var(--color-text-muted)] mt-1">设备测试报告概览与统计</p>
            </div>

            {/* 统计卡片 */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                {stats.map((s) => (
                    <div key={s.label} className="glass-card p-5">
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-sm text-[var(--color-text-muted)]">{s.label}</p>
                                <p className="text-3xl font-bold mt-1">{s.value}</p>
                            </div>
                            <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${s.color} flex items-center justify-center opacity-80`}>
                                <s.icon className="w-6 h-6 text-white" />
                            </div>
                        </div>
                    </div>
                ))}
            </div>

            {/* 报告列表 */}
            <div className="glass-card overflow-hidden">
                <div className="px-6 py-4 border-b border-[var(--color-border)]">
                    <h2 className="text-lg font-semibold">最新报告</h2>
                </div>

                {loading ? (
                    <div className="px-6 py-12 text-center text-[var(--color-text-muted)]">
                        加载中…
                    </div>
                ) : reports.length === 0 ? (
                    <div className="px-6 py-12 text-center text-[var(--color-text-muted)]">
                        暂无报告数据
                    </div>
                ) : (
                    <div className="overflow-x-auto">
                        <table className="w-full">
                            <thead>
                                <tr className="text-left text-sm text-[var(--color-text-muted)]">
                                    <th className="px-6 py-3 font-medium">设备 ID</th>
                                    <th className="px-6 py-3 font-medium">状态</th>
                                    <th className="px-6 py-3 font-medium">时间</th>
                                    <th className="px-6 py-3 font-medium">操作</th>
                                </tr>
                            </thead>
                            <tbody>
                                {reports.map((report) => (
                                    <tr
                                        key={report.id}
                                        className="border-t border-[var(--color-border)] hover:bg-[var(--color-surface-hover)] transition-colors cursor-pointer"
                                        onClick={() => navigate(`/reports/${report.id}`)}
                                    >
                                        <td className="px-6 py-4 font-mono text-sm">{report.device_id}</td>
                                        <td className="px-6 py-4">
                                            <span className={`badge ${report.status === 'analyzed' ? 'badge-analyzed' : 'badge-pending'}`}>
                                                {report.status === 'analyzed' ? '已分析' : '待处理'}
                                            </span>
                                        </td>
                                        <td className="px-6 py-4 text-sm text-[var(--color-text-muted)]">
                                            {new Date(report.created_at).toLocaleString('zh-CN')}
                                        </td>
                                        <td className="px-6 py-4">
                                            <button className="btn-secondary text-xs py-1.5 px-3">
                                                查看详情
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>
        </div>
    )
}
