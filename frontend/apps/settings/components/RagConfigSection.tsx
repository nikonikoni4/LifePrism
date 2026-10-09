import React, { useEffect, useState } from 'react';
import { Database, Loader2, RefreshCw } from 'lucide-react';
import { RagAPI, RagIndexStatus, RagSettings, RagSettingsPatch } from '../ragApi';
import { getUserTimezone, parseISOString } from '../../../core/utils/dateUtils';

const inputStyle =
  'w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-200 disabled:opacity-50';
const buttonStyle =
  'rounded-xl bg-slate-900 px-4 py-2 text-sm text-white hover:bg-slate-700 disabled:opacity-40';

export const RagConfigSection: React.FC = () => {
  const [settings, setSettings] = useState<RagSettings | null>(null);
  const [directories, setDirectories] = useState('user\ndiary');
  const [keys, setKeys] = useState({ embedding: '', rerank: '' });
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [indexStatus, setIndexStatus] = useState<RagIndexStatus | null>(null);
  const [indexError, setIndexError] = useState('');
  const [startingIndex, setStartingIndex] = useState(false);

  useEffect(() => {
    let active = true;
    RagAPI.get()
      .then((value) => {
        if (active) {
          setSettings(value);
          setDirectories(value.index_directories.join('\n'));
        }
      })
      .catch((reason) => {
        if (active) setError(reason instanceof Error ? reason.message : '读取配置失败');
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    async function refresh() {
      try {
        const status = await RagAPI.indexStatus();
        if (active) {
          setIndexStatus(status);
          setIndexError('');
        }
      } catch (reason) {
        if (active) setIndexError(reason instanceof Error ? reason.message : '读取索引状态失败');
      } finally {
        if (active) timer = setTimeout(() => void refresh(), 2000);
      }
    }
    void refresh();
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [settings?.enabled, settings?.embedding.configured]);

  async function buildIndex() {
    setStartingIndex(true);
    setIndexError('');
    setMessage('');
    try {
      setIndexStatus(await RagAPI.buildIndex());
    } catch (reason) {
      setIndexError(reason instanceof Error ? reason.message : '启动索引失败');
    } finally {
      setStartingIndex(false);
    }
  }

  async function update(patch: RagSettingsPatch) {
    setBusy(true);
    setError('');
    setMessage('');
    try {
      setSettings(await RagAPI.update(patch));
      setMessage('配置已保存');
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '保存失败');
    } finally {
      setBusy(false);
    }
  }

  async function saveKey(purpose: 'embedding' | 'rerank', clear = false) {
    setBusy(true);
    setError('');
    setMessage('');
    try {
      setSettings(await RagAPI.saveKey(purpose, clear ? '' : keys[purpose]));
      setKeys((value) => ({ ...value, [purpose]: '' }));
      setMessage(clear ? '密钥已清除，对应功能已关闭' : '密钥已安全保存');
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '密钥保存失败');
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="mb-5 flex items-center gap-3">
        <Database className="h-5 w-5 text-indigo-600" />
        <h2 className="text-lg font-semibold text-slate-900">个人记录检索 · RAG</h2>
        {busy && <Loader2 className="h-4 w-4 animate-spin text-slate-500" />}
      </div>
      {error && (
        <p role="alert" className="mb-4 text-sm text-red-600">
          {error}
        </p>
      )}
      {message && (
        <p role="status" className="mb-4 text-sm text-emerald-700">
          {message}
        </p>
      )}
      {!settings ? (
        <p className="text-sm text-slate-500">正在读取 RAG 配置…</p>
      ) : (
        <div className="space-y-6">
          <div className="rounded-xl border border-slate-100 bg-slate-50 p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="text-sm text-slate-600">
                <span className="text-slate-400">上次成功索引：</span>
                <span className="font-medium">
                  {!indexStatus
                    ? '正在读取…'
                    : indexStatus.last_index_time
                      ? parseISOString(indexStatus.last_index_time).toLocaleString('sv-SE', {
                          timeZone: getUserTimezone(),
                          hour12: false,
                        })
                      : '尚未索引'}
                </span>
              </div>
              <button
                type="button"
                onClick={() => void buildIndex()}
                disabled={
                  busy ||
                  startingIndex ||
                  !indexStatus?.can_build ||
                  indexStatus.building ||
                  !settings.enabled ||
                  !settings.embedding.configured
                }
                className={`${buttonStyle} flex items-center gap-2`}
              >
                {startingIndex || indexStatus?.building ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    索引中…
                  </>
                ) : (
                  <>
                    <RefreshCw className="h-4 w-4" />
                    立即更新索引
                  </>
                )}
              </button>
            </div>
            {(indexError || indexStatus?.error) && (
              <p role="alert" className="mt-2 text-sm text-red-600">
                {indexError || indexStatus?.error}
              </p>
            )}
            <p className="mt-2 text-xs leading-relaxed text-slate-500">
              手动更新使用已保存的目录完整重建，只更新本地索引，会产生嵌入模型 API 费用。
              云端仍按每日一次规则同步；当天已同步后，手动更新的内容将在下一次每日任务中同步。
            </p>
          </div>
          <div className="flex flex-wrap gap-6">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                aria-label="启用 RAG"
                checked={settings.enabled}
                disabled={busy || !settings.embedding.configured}
                onChange={(event) => void update({ enabled: event.target.checked })}
              />
              启用 RAG
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                aria-label="启用 rerank"
                checked={settings.rerank_enabled}
                disabled={busy || !settings.rerank.configured}
                onChange={(event) => void update({ rerank_enabled: event.target.checked })}
              />
              使用 rerank 重排
            </label>
          </div>
          <p className="text-sm leading-relaxed text-slate-500">
            先保存对应模型密钥再开启。每日
            10:00（用户时区）在记忆更新完成后更新索引，再单独同步到云端；错过时启动后补执行。检索默认使用
            vec，只有明确关键词时才由工具选择 BM25。
          </p>
          <div>
            <label htmlFor="rag-directories" className="mb-2 block text-sm font-medium">
              索引目录
            </label>
            <textarea
              id="rag-directories"
              rows={3}
              className={inputStyle}
              value={directories}
              disabled={busy}
              onChange={(event) => setDirectories(event.target.value)}
            />
            <div className="mt-2 flex flex-wrap items-center justify-between gap-3">
              <p className="text-xs text-slate-500">
                数据目录内的相对文件夹，每行一个；递归索引 Markdown。默认 user、diary。
              </p>
              <button
                type="button"
                className={buttonStyle}
                disabled={busy}
                onClick={() =>
                  void update({
                    index_directories: directories
                      .split('\n')
                      .map((value) => value.trim())
                      .filter(Boolean),
                  })
                }
              >
                保存索引目录
              </button>
            </div>
          </div>
          {(['embedding', 'rerank'] as const).map((purpose) => {
            const label = purpose === 'embedding' ? '豆包嵌入' : '阿里云重排';
            const info = settings[purpose];
            return (
              <div key={purpose} className="space-y-3 rounded-xl bg-slate-50 p-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-semibold">{label}</h3>
                  <span className="text-xs text-slate-500">
                    {info.configured ? '密钥已配置' : '密钥未配置'}
                  </span>
                </div>
                <label className="block text-xs text-slate-500">
                  模型 ID（固定）
                  <input
                    aria-label={`${label}模型`}
                    readOnly
                    value={info.model}
                    className={`${inputStyle} mt-1 bg-slate-100`}
                  />
                </label>
                <label className="block text-xs text-slate-500">
                  Base URL（固定）
                  <input
                    aria-label={`${label}地址`}
                    readOnly
                    value={info.base_url}
                    className={`${inputStyle} mt-1 bg-slate-100`}
                  />
                </label>
                <label className="block text-xs text-slate-500">
                  API Key
                  <input
                    aria-label={`${label} API Key`}
                    type="password"
                    autoComplete="new-password"
                    disabled={busy}
                    value={keys[purpose]}
                    placeholder={info.configured ? '输入新密钥以替换' : '输入 API Key'}
                    className={`${inputStyle} mt-1`}
                    onChange={(event) =>
                      setKeys((value) => ({ ...value, [purpose]: event.target.value }))
                    }
                  />
                </label>
                <div className="flex gap-3">
                  <button
                    type="button"
                    className={buttonStyle}
                    disabled={busy || !keys[purpose].trim()}
                    onClick={() => void saveKey(purpose)}
                  >
                    保存{label}密钥
                  </button>
                  {info.configured && (
                    <button
                      type="button"
                      className="px-3 py-2 text-sm text-slate-500 hover:text-red-600 disabled:opacity-40"
                      disabled={busy}
                      onClick={() => void saveKey(purpose, true)}
                    >
                      清除{label}密钥
                    </button>
                  )}
                </div>
              </div>
            );
          })}
          <p className="text-xs leading-relaxed text-slate-500">
            本地更新失败时保留旧索引；云端上传失败每 15 分钟重试，复用当天已建索引。rerank
            不可用时回退到重排前结果。首次启用后可手动更新或等待每日索引任务；云端模型密钥通过“生成云端配置”部署。
          </p>
        </div>
      )}
    </section>
  );
};
