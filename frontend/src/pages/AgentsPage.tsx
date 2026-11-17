import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { api, ApiError, type McpToken, type McpTokenCreated } from "../lib/api";

const MAX_TOKENS = 10;

function formatDate(seconds: number): string {
  return new Date(seconds * 1000).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function messageOf(error: unknown): string {
  if (error instanceof ApiError && error.status === 409) {
    return `You have reached the limit of ${MAX_TOKENS} tokens. Revoke one to create another.`;
  }
  return error instanceof Error && error.message ? error.message : "Something went wrong. Try again.";
}

/** A copy button that confirms for two seconds. */
function CopyButton({ text, label }: { text: string; label: string }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard access can be blocked; the text stays selectable.
    }
  }
  return (
    <button type="button" className="btn btn-secondary shrink-0" onClick={copy} aria-label={label}>
      <span aria-live="polite">{copied ? "Copied" : "Copy"}</span>
    </button>
  );
}

function Snippet({ title, text }: { title: string; text: string }) {
  return (
    <div className="mt-4">
      <div className="mb-1.5 flex items-center justify-between gap-3">
        <h3 className="m-0 text-[13px] font-semibold text-ink">{title}</h3>
        <CopyButton text={text} label={`Copy the ${title} snippet`} />
      </div>
      <pre className="m-0 overflow-x-auto rounded-md border border-rule bg-sunk p-3.5 font-mono text-[12.5px] leading-[1.6] text-ink-2">
        <code>{text}</code>
      </pre>
    </div>
  );
}

/**
 * Agent access: create and revoke the tokens that let an AI agent use the
 * course's MCP server on your behalf.
 */
export default function AgentsPage() {
  const [url, setUrl] = useState("");
  const [tokens, setTokens] = useState<McpToken[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [created, setCreated] = useState<McpTokenCreated | null>(null);
  const [revoking, setRevoking] = useState<number | null>(null);
  const [listError, setListError] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoadError(null);
    return api
      .mcpTokens()
      .then((body) => {
        setUrl(body.url);
        setTokens(body.tokens);
      })
      .catch((error) => setLoadError(messageOf(error)))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function onCreate(event: FormEvent) {
    event.preventDefault();
    const trimmed = name.trim();
    if (!trimmed || creating) return;
    setCreating(true);
    setFormError(null);
    try {
      const token = await api.createMcpToken(trimmed);
      setCreated(token);
      setName("");
      await load();
    } catch (error) {
      setFormError(messageOf(error));
    } finally {
      setCreating(false);
    }
  }

  async function onRevoke(token: McpToken) {
    if (!window.confirm(`Revoke "${token.name}"? Agents that use it lose access immediately.`)) return;
    setRevoking(token.id);
    setListError(null);
    try {
      await api.revokeMcpToken(token.id);
      if (created?.id === token.id) setCreated(null);
      await load();
    } catch (error) {
      setListError(messageOf(error));
    } finally {
      setRevoking(null);
    }
  }

  const atLimit = tokens.length >= MAX_TOKENS;
  const claudeCode = created
    ? `claude mcp add --transport http os ${url} --header "Authorization: Bearer ${created.token}"`
    : "";
  const json = created
    ? JSON.stringify(
        { mcpServers: { os: { type: "http", url, headers: { Authorization: `Bearer ${created.token}` } } } },
        null,
        2,
      )
    : "";

  return (
    <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
      <div className="mx-auto max-w-3xl px-5 pb-16 pt-10 sm:px-8 lg:pt-14">
        <nav aria-label="Breadcrumb" className="mb-4 flex items-center gap-1.5 text-[13px] text-ink-3">
          <Link to="/" className="hover:text-ink">
            Contents
          </Link>
          <span aria-hidden>/</span>
          <span>Agent access</span>
        </nav>

        <header>
          <h1 className="font-serif text-[2.1rem] font-semibold leading-[1.15] tracking-[-0.015em] text-ink sm:text-[2.5rem]">
            Agent access (MCP)
          </h1>
          <p className="mt-3 max-w-[38rem] font-serif text-[1.08rem] leading-relaxed text-ink-3">
            Connect an AI agent, such as Claude Code, Claude Desktop, or Cursor, to read lessons and
            exercises, to see your progress, and to run checks. Each agent uses its own token, which
            you can revoke at any time.
          </p>
        </header>

        <section className="mt-8 rounded-xl border border-rule bg-raise p-5" aria-labelledby="mcp-url">
          <h2 id="mcp-url" className="m-0 text-[15px] font-semibold text-ink">
            Server URL
          </h2>
          {loading ? (
            <p className="mt-3 text-[14px] text-ink-3" aria-busy="true">
              Loading…
            </p>
          ) : url ? (
            <div className="mt-3 flex items-center gap-2">
              <code className="min-w-0 flex-1 overflow-x-auto whitespace-nowrap rounded-md border border-rule bg-sunk px-3 py-2.5 font-mono text-[13px] text-ink">
                {url}
              </code>
              <CopyButton text={url} label="Copy the server URL" />
            </div>
          ) : null}
        </section>

        {loadError && (
          <div role="alert" className="mt-4 rounded-md border border-bad/40 p-3.5 text-[14px] text-bad">
            {loadError}{" "}
            <button
              type="button"
              className="font-semibold underline"
              onClick={() => {
                setLoading(true);
                void load();
              }}
            >
              Try again
            </button>
          </div>
        )}

        <section className="mt-6 rounded-xl border border-rule bg-raise p-5" aria-labelledby="mcp-create">
          <h2 id="mcp-create" className="m-0 text-[15px] font-semibold text-ink">
            Create a token
          </h2>
          <form onSubmit={onCreate} className="mt-3 flex flex-col gap-2 sm:flex-row">
            <label className="sr-only" htmlFor="mcp-name">
              Token name
            </label>
            <input
              id="mcp-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              maxLength={64}
              required
              disabled={atLimit}
              placeholder="Name, such as Claude Code on my laptop"
              className="field min-w-0 flex-1"
            />
            <button type="submit" className="btn btn-primary" disabled={creating || atLimit || !name.trim()}>
              {creating ? "Creating…" : "Create token"}
            </button>
          </form>
          {atLimit && (
            <p className="mt-2 text-[13px] text-ink-3">
              You have {MAX_TOKENS} tokens, the maximum. Revoke one to create another.
            </p>
          )}
          {formError && (
            <p role="alert" className="mt-2 text-[13px] text-bad">
              {formError}
            </p>
          )}

          {created && (
            <div className="mt-5 rounded-lg border border-accent/50 bg-sunk p-4" role="status">
              <h3 className="m-0 text-[14px] font-semibold text-ink">Copy your token now</h3>
              <p className="mt-1 text-[13px] leading-[1.6] text-ink-2">
                This is the only time the token for "{created.name}" is shown. Store it somewhere
                safe. Anyone who has it can act as you, including running code in the course's
                container.
              </p>
              <div className="mt-3 flex items-center gap-2">
                <code className="min-w-0 flex-1 overflow-x-auto whitespace-nowrap rounded-md border border-rule bg-raise px-3 py-2.5 font-mono text-[13px] text-ink">
                  {created.token}
                </code>
                <CopyButton text={created.token} label="Copy the token" />
              </div>
              <Snippet title="Claude Code" text={claudeCode} />
              <Snippet title="JSON config (Claude Desktop, Cursor, and others)" text={json} />
              <button type="button" className="btn btn-secondary mt-4" onClick={() => setCreated(null)}>
                I have copied it
              </button>
            </div>
          )}
        </section>

        <section className="mt-6" aria-labelledby="mcp-tokens">
          <h2 id="mcp-tokens" className="m-0 text-[15px] font-semibold text-ink">
            Your tokens{" "}
            {!loading && (
              <span className="font-normal text-ink-3">
                ({tokens.length} of {MAX_TOKENS})
              </span>
            )}
          </h2>
          {listError && (
            <p role="alert" className="mt-2 text-[13px] text-bad">
              {listError}
            </p>
          )}
          {loading ? (
            <p className="mt-3 text-[14px] text-ink-3" aria-busy="true">
              Loading your tokens…
            </p>
          ) : tokens.length === 0 ? (
            <p className="mt-3 text-[14px] text-ink-3">You have no tokens yet. Create one to connect an agent.</p>
          ) : (
            <ul className="m-0 mt-3 list-none divide-y divide-rule overflow-hidden rounded-xl border border-rule bg-raise p-0">
              {tokens.map((token) => (
                <li key={token.id} className="flex flex-wrap items-center justify-between gap-3 p-4">
                  <div className="min-w-0">
                    <div className="truncate text-[14px] font-semibold text-ink">{token.name}</div>
                    <div className="mt-1 text-[12.5px] text-ink-3">
                      <code className="font-mono">{token.prefix}…</code>
                      {" · "}Created {formatDate(token.created_at)}
                      {" · "}
                      {token.last_used_at ? `Last used ${formatDate(token.last_used_at)}` : "Never used"}
                    </div>
                  </div>
                  <button
                    type="button"
                    className="btn btn-danger"
                    onClick={() => onRevoke(token)}
                    disabled={revoking === token.id}
                    aria-label={`Revoke ${token.name}`}
                  >
                    {revoking === token.id ? "Revoking…" : "Revoke"}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}
