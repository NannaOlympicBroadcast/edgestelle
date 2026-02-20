/**
 * 系统设置页 — 管理员配置飞书推送等参数。
 */

import { useEffect, useState } from 'react'
import { Save } from 'lucide-react'
import { useAuthStore } from '@/stores/authStore'
import api from '@/lib/api'

interface ConfigItem {
    key: string
    value: string
    updated_at?: string
}

const CONFIG_FIELDS = [
    { key: 'feishu_bot_webhook_url', label: '飞书机器人 Webhook URL', placeholder: 'https://open.feishu.cn/open-apis/bot/v2/hook/...' },
    { key: 'feishu_target_chat_id', label: '飞书目标群 Chat ID', placeholder: 'oc_xxxx (可选)' },
    { key: 'notification_enabled', label: '启用飞书推送', placeholder: 'true / false' },
]

export default function SystemSettingsPage() {
    const user = useAuthStore((s) => s.user)
    const [configs, setConfigs] = useState<Record<string, string>>({})
    const [loading, setLoading] = useState(true)
    const [saving, setSaving] = useState(false)
    const [saved, setSaved] = useState(false)

    useEffect(() => {
        api.get('/system/config')
            .then(({ data }) => {
                const map: Record<string, string> = {}
                data.forEach((c: ConfigItem) => { map[c.key] = c.value })
                setConfigs(map)
            })
            .catch(() => { })
            .finally(() => setLoading(false))
    }, [])

    const handleSave = async () => {
        setSaving(true)
        try {
            const items = CONFIG_FIELDS.map((f) => ({
                key: f.key,
                value: configs[f.key] || '',
            }))
            await api.put('/system/config', { configs: items })
            setSaved(true)
            setTimeout(() => setSaved(false), 2000)
        } catch {
            alert('保存失败')
        } finally {
            setSaving(false)
        }
    }

    if (!user?.is_admin) {
        return (
            <div className="text-center py-16 text-[var(--color-text-muted)] animate-fade-in">
                <p className="text-lg">🔒 需要管理员权限</p>
                <p className="mt-2">请联系管理员获取访问权限</p>
            </div>
        )
    }

    return (
        <div className="space-y-6 animate-fade-in">
            <div>
                <h1 className="text-2xl font-bold">系统设置</h1>
                <p className="text-[var(--color-text-muted)] mt-1">配置飞书群推送及相关参数</p>
            </div>

            <div className="glass-card p-6 space-y-6">
                {loading ? (
                    <div className="text-center py-8 text-[var(--color-text-muted)]">加载中…</div>
                ) : (
                    <>
                        {CONFIG_FIELDS.map((field) => (
                            <div key={field.key}>
                                <label className="block text-sm font-medium mb-1">{field.label}</label>
                                <input
                                    className="input"
                                    value={configs[field.key] || ''}
                                    onChange={(e) => setConfigs({ ...configs, [field.key]: e.target.value })}
                                    placeholder={field.placeholder}
                                />
                                <p className="text-xs text-[var(--color-text-muted)] mt-1">
                                    配置键: <code className="bg-[var(--color-surface)] px-1 rounded">{field.key}</code>
                                </p>
                            </div>
                        ))}

                        <div className="flex items-center gap-3 pt-2">
                            <button onClick={handleSave} disabled={saving} className="btn-primary">
                                <Save className="w-4 h-4" />
                                {saving ? '保存中…' : '保存配置'}
                            </button>
                            {saved && (
                                <span className="text-sm text-emerald-400 animate-fade-in">
                                    ✅ 已保存
                                </span>
                            )}
                        </div>
                    </>
                )}
            </div>
        </div>
    )
}
