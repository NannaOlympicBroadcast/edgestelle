/**
 * 报告详情页 — 展示设备测试数据 + AI 分析 (Markdown 渲染)。
 */

import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { ArrowLeft, RefreshCw } from 'lucide-react'
import api from '@/lib/api'

interface Report {
    id: string
    template_id: string
    device_id: string
    report_data: Record<string, unknown>
    ai_analysis: string | null
    status: string
    created_at: string
}

export default function ReportDetail() {
    const { id } = useParams<{ id: string }>()
    const navigate = useNavigate()
    const [report, setReport] = useState<Report | null>(null)
    const [loading, setLoading] = useState(true)
    const [analyzing, setAnalyzing] = useState(false)

    const fetchReport = () => {
        setLoading(true)
        api.get(`/reports/${id}`)
            .then(({ data }) => setReport(data))
            .catch(() => { })
            .finally(() => setLoading(false))
    }

    useEffect(() => { fetchReport() }, [id])

    const triggerAnalysis = async () => {
        setAnalyzing(true)
        try {
            const { data } = await api.post(`/reports/${id}/analyze`)
            setReport(data)
        } catch {
            alert('AI 分析触发失败')
        } finally {
            setAnalyzing(false)
        }
    }

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <span className="animate-spin inline-block w-8 h-8 border-3 border-[var(--color-primary)]/30 border-t-[var(--color-primary)] rounded-full" />
            </div>
        )
    }

    if (!report) {
        return (
            <div className="text-center py-16 text-[var(--color-text-muted)]">
                报告不存在
            </div>
        )
    }

    return (
        <div className="space-y-6 animate-fade-in">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                    <button onClick={() => navigate(-1)} className="btn-secondary py-2 px-3">
                        <ArrowLeft className="w-4 h-4" />
                    </button>
                    <div>
                        <h1 className="text-xl font-bold">设备 {report.device_id}</h1>
                        <p className="text-sm text-[var(--color-text-muted)]">
                            {new Date(report.created_at).toLocaleString('zh-CN')}
                        </p>
                    </div>
                </div>
                <div className="flex items-center gap-3">
                    <span className={`badge ${report.status === 'analyzed' ? 'badge-analyzed' : 'badge-pending'}`}>
                        {report.status === 'analyzed' ? '已分析' : '待处理'}
                    </span>
                    <button
                        onClick={triggerAnalysis}
                        disabled={analyzing}
                        className="btn-primary"
                    >
                        <RefreshCw className={`w-4 h-4 ${analyzing ? 'animate-spin' : ''}`} />
                        {analyzing ? '分析中…' : '重新分析'}
                    </button>
                </div>
            </div>

            {/* 原始数据 */}
            <div className="glass-card p-6">
                <h2 className="text-lg font-semibold mb-4">📊 原始测试数据</h2>
                <pre className="overflow-x-auto text-sm text-[var(--color-text-muted)] bg-[var(--color-surface)] rounded-lg p-4 border border-[var(--color-border)]">
                    {JSON.stringify(report.report_data, null, 2)}
                </pre>
            </div>

            {/* AI 分析 */}
            <div className="glass-card p-6">
                <h2 className="text-lg font-semibold mb-4">🤖 AI 智能分析</h2>
                {report.ai_analysis ? (
                    <div className="markdown-content">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                            {report.ai_analysis}
                        </ReactMarkdown>
                    </div>
                ) : (
                    <p className="text-[var(--color-text-muted)] text-center py-8">
                        暂无分析结果，请点击"重新分析"按钮触发 AI 分析
                    </p>
                )}
            </div>
        </div>
    )
}
