/**
 * API Key 管理页 — 生成 / 查看 / 删除。
 */

import { useEffect, useState } from 'react'
import { Plus, Trash2, Copy, Check } from 'lucide-react'
import api from '@/lib/api'

interface ApiKey {
    id: string
    name: string
    key_prefix: string
    is_active: boolean
    created_at: string
    last_used_at: string | null
}

export default function ApiKeysPage() {
    const [keys, setKeys] = useState<ApiKey[]>([])
    const [loading, setLoading] = useState(true)
    const [newKeyName, setNewKeyName] = useState('Default')
    const [createdKey, setCreatedKey] = useState<string | null>(null)
    const [copied, setCopied] = useState(false)
    const [creating, setCreating] = useState(false)

    const fetchKeys = () => {
        api.get('/api-keys')
            .then(({ data }) => setKeys(data))
            .catch(() => { })
            .finally(() => setLoading(false))
    }

    useEffect(() => { fetchKeys() }, [])

    const handleCreate = async () => {
        setCreating(true)
        try {
            const { data } = await api.post('/api-keys', { name: newKeyName })
            setCreatedKey(data.raw_key)
            setNewKeyName('Default')
            fetchKeys()
        } catch {
            alert('创建失败')
        } finally {
            setCreating(false)
        }
    }

    const handleDelete = async (id: string) => {
        if (!confirm('确认撤销此 API Key？')) return
        try {
            await api.delete(`/api-keys/${id}`)
            fetchKeys()
        } catch {
            alert('撤销失败')
        }
    }

    const handleCopy = () => {
        if (createdKey) {
            navigator.clipboard.writeText(createdKey)
            setCopied(true)
            setTimeout(() => setCopied(false), 2000)
        }
    }

    return (
        <div className="space-y-6 animate-fade-in">
            <div>
                <h1 className="text-2xl font-bold">API Key 管理</h1>
                <p className="text-[var(--color-text-muted)] mt-1">
                    管理用于设备端 SDK 鉴权的 API Key
                </p>
            </div>

            {/* 创建区域 */}
            <div className="glass-card p-6">
                <h3 className="font-semibold mb-4">生成新的 API Key</h3>
                <div className="flex gap-3 items-end">
                    <div className="flex-1">
                        <label className="block text-sm text-[var(--color-text-muted)] mb-1">名称</label>
                        <input
                            className="input"
                            value={newKeyName}
                            onChange={(e) => setNewKeyName(e.target.value)}
                            placeholder="Key 用途描述"
                        />
                    </div>
                    <button onClick={handleCreate} disabled={creating} className="btn-primary">
                        <Plus className="w-4 h-4" />
                        {creating ? '生成中…' : '生成'}
                    </button>
                </div>

                {/* 一次性展示的密钥 */}
                {createdKey && (
                    <div className="mt-4 p-4 rounded-lg bg-emerald-900/20 border border-emerald-500/30">
                        <p className="text-sm text-emerald-400 font-medium mb-2">
                            ✅ API Key 已生成 — 请立即复制，此密钥不会再次显示！
                        </p>
                        <div className="flex items-center gap-2">
                            <code className="flex-1 bg-[var(--color-surface)] px-3 py-2 rounded font-mono text-sm break-all">
                                {createdKey}
                            </code>
                            <button onClick={handleCopy} className="btn-secondary py-2">
                                {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
                            </button>
                        </div>
                    </div>
                )}
            </div>

            {/* Key 列表 */}
            <div className="glass-card overflow-hidden">
                <div className="px-6 py-4 border-b border-[var(--color-border)]">
                    <h3 className="font-semibold">已有的 API Key</h3>
                </div>

                {loading ? (
                    <div className="px-6 py-12 text-center text-[var(--color-text-muted)]">加载中…</div>
                ) : keys.length === 0 ? (
                    <div className="px-6 py-12 text-center text-[var(--color-text-muted)]">暂无 API Key</div>
                ) : (
                    <table className="w-full">
                        <thead>
                            <tr className="text-left text-sm text-[var(--color-text-muted)]">
                                <th className="px-6 py-3 font-medium">名称</th>
                                <th className="px-6 py-3 font-medium">前缀</th>
                                <th className="px-6 py-3 font-medium">状态</th>
                                <th className="px-6 py-3 font-medium">创建时间</th>
                                <th className="px-6 py-3 font-medium">上次使用</th>
                                <th className="px-6 py-3 font-medium">操作</th>
                            </tr>
                        </thead>
                        <tbody>
                            {keys.map((k) => (
                                <tr key={k.id} className="border-t border-[var(--color-border)]">
                                    <td className="px-6 py-4 font-medium">{k.name}</td>
                                    <td className="px-6 py-4 font-mono text-sm text-[var(--color-text-muted)]">{k.key_prefix}…</td>
                                    <td className="px-6 py-4">
                                        <span className={`badge ${k.is_active ? 'badge-analyzed' : 'badge-pending'}`}>
                                            {k.is_active ? '有效' : '已撤销'}
                                        </span>
                                    </td>
                                    <td className="px-6 py-4 text-sm text-[var(--color-text-muted)]">
                                        {new Date(k.created_at).toLocaleDateString('zh-CN')}
                                    </td>
                                    <td className="px-6 py-4 text-sm text-[var(--color-text-muted)]">
                                        {k.last_used_at
                                            ? new Date(k.last_used_at).toLocaleDateString('zh-CN')
                                            : '—'}
                                    </td>
                                    <td className="px-6 py-4">
                                        {k.is_active && (
                                            <button onClick={() => handleDelete(k.id)} className="btn-danger text-xs py-1.5">
                                                <Trash2 className="w-3.5 h-3.5" />
                                                撤销
                                            </button>
                                        )}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                )}
            </div>
        </div>
    )
}
