/**
 * 模板管理页 — 列表 + 创建。
 */

import { useEffect, useState } from 'react'
import { Plus, FileText } from 'lucide-react'
import api from '@/lib/api'

interface Template {
    id: string
    name: string
    version: string
    description?: string | null
    schema_definition: Record<string, unknown>
    created_at: string
    updated_at: string
}

export default function TemplatesPage() {
    const [templates, setTemplates] = useState<Template[]>([])
    const [loading, setLoading] = useState(true)
    const [showCreate, setShowCreate] = useState(false)
    const [form, setForm] = useState({ name: '', version: '1.0', description: '' })
    const [creating, setCreating] = useState(false)

    const fetchTemplates = () => {
        api.get('/templates')
            .then(({ data }) => setTemplates(data))
            .catch(() => { })
            .finally(() => setLoading(false))
    }

    useEffect(() => { fetchTemplates() }, [])

    const handleCreate = async () => {
        if (!form.name.trim()) return
        setCreating(true)
        try {
            await api.post('/templates', {
                name: form.name,
                version: form.version,
                description: form.description || undefined,
                schema_definition: {
                    metrics: [
                        { name: 'cpu_temperature', unit: '°C', threshold_max: 80, description: 'CPU 核心温度' },
                        { name: 'memory_usage', unit: '%', threshold_max: 90, description: '内存使用率' },
                    ],
                },
            })
            setShowCreate(false)
            setForm({ name: '', version: '1.0', description: '' })
            fetchTemplates()
        } catch {
            alert('创建失败')
        } finally {
            setCreating(false)
        }
    }

    return (
        <div className="space-y-6 animate-fade-in">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold">模板管理</h1>
                    <p className="text-[var(--color-text-muted)] mt-1">管理设备测试模板定义</p>
                </div>
                <button className="btn-primary" onClick={() => setShowCreate(!showCreate)}>
                    <Plus className="w-4 h-4" />
                    创建模板
                </button>
            </div>

            {/* 创建表单 */}
            {showCreate && (
                <div className="glass-card p-6 space-y-4">
                    <h3 className="font-semibold">新建模板</h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                            <label className="block text-sm text-[var(--color-text-muted)] mb-1">名称</label>
                            <input
                                className="input"
                                value={form.name}
                                onChange={(e) => setForm({ ...form, name: e.target.value })}
                                placeholder="例：智能摄像头深度测试"
                            />
                        </div>
                        <div>
                            <label className="block text-sm text-[var(--color-text-muted)] mb-1">版本</label>
                            <input
                                className="input"
                                value={form.version}
                                onChange={(e) => setForm({ ...form, version: e.target.value })}
                            />
                        </div>
                    </div>
                    <div>
                        <label className="block text-sm text-[var(--color-text-muted)] mb-1">描述</label>
                        <input
                            className="input"
                            value={form.description}
                            onChange={(e) => setForm({ ...form, description: e.target.value })}
                            placeholder="模板说明"
                        />
                    </div>
                    <p className="text-xs text-[var(--color-text-muted)]">
                        ℹ️ 默认指标 (cpu_temperature, memory_usage) 将作为初始模板创建，后续可通过 API 修改。
                    </p>
                    <div className="flex gap-3">
                        <button onClick={handleCreate} disabled={creating} className="btn-primary">
                            {creating ? '创建中…' : '确认创建'}
                        </button>
                        <button onClick={() => setShowCreate(false)} className="btn-secondary">
                            取消
                        </button>
                    </div>
                </div>
            )}

            {/* 模板列表 */}
            {loading ? (
                <div className="text-center py-12 text-[var(--color-text-muted)]">加载中…</div>
            ) : templates.length === 0 ? (
                <div className="glass-card p-12 text-center text-[var(--color-text-muted)]">
                    暂无模板，点击上方按钮创建
                </div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {templates.map((t) => (
                        <div key={t.id} className="glass-card p-5 space-y-3">
                            <div className="flex items-start gap-3">
                                <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-violet-500 to-fuchsia-500 flex items-center justify-center flex-shrink-0">
                                    <FileText className="w-5 h-5 text-white" />
                                </div>
                                <div className="min-w-0">
                                    <h3 className="font-semibold truncate">{t.name}</h3>
                                    <p className="text-xs text-[var(--color-text-muted)]">v{t.version}</p>
                                </div>
                            </div>
                            <p className="text-sm text-[var(--color-text-muted)] line-clamp-2">
                                {t.description || '暂无描述'}
                            </p>
                            <div className="flex items-center justify-between text-xs text-[var(--color-text-muted)]">
                                <span>{new Date(t.created_at).toLocaleDateString('zh-CN')}</span>
                                <code className="bg-[var(--color-surface)] px-2 py-0.5 rounded text-[10px]">
                                    {t.id.slice(0, 8)}…
                                </code>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    )
}
