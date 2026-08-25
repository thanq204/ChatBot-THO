import { useCallback, useMemo, useState } from "react";
import { useQueries, useQueryClient } from "@tanstack/react-query";
import { Check, Copy, LockSimple, LockSimpleOpen, MagnifyingGlass, PaperPlaneTilt, Trash } from "@phosphor-icons/react";
import Card from "../components/Card.jsx";
import Badge from "../components/Badge.jsx";
import Pagination, { usePagination } from "../components/Pagination.jsx";
import LoadMore, { useLoadMore } from "../components/LoadMore.jsx";
import { useToast } from "../components/ToastProvider.jsx";
import { EmptyState, ErrorState } from "../components/StatePanels.jsx";
import { SkeletonBlock } from "../components/Skeleton.jsx";
import { auth } from "../api/client.js";
import { queryKeys } from "../lib/queryClient.js";

function inviteLink(token) {
  return `${window.location.origin}/dang-ky?token=${token}`;
}

const ROLE_FILTERS = [
  { value: "", label: "Tất cả" },
  { value: "admin", label: "Admin" },
  { value: "mod", label: "Mod" },
];

const PAGE_SIZE_OPTIONS = [10, 25, 50];
const INVITES_STEP = 3;

/** Two letters, so "NGUYEN THAI TU" and "admin" both give a usable monogram. */
function initials(name, email) {
  const source = (name || email || "?").trim();
  const words = source.split(/\s+/).filter(Boolean);
  if (words.length >= 2) return (words[0][0] + words[words.length - 1][0]).toUpperCase();
  return source.slice(0, 2).toUpperCase();
}

export default function ModManagementPage() {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [inviteEmail, setInviteEmail] = useState("");
  const [saving, setSaving] = useState(false);
  const [actionError, setActionError] = useState("");
  const [copiedEmail, setCopiedEmail] = useState("");
  const [query, setQuery] = useState("");
  const [roleFilter, setRoleFilter] = useState("");
  const [pageSize, setPageSize] = useState(10);
  const [busyId, setBusyId] = useState("");

  const [usersQuery, invitesQuery] = useQueries({
    queries: [
      { queryKey: queryKeys.users, queryFn: auth.users, refetchInterval: 15_000 },
      { queryKey: queryKeys.modInvites, queryFn: auth.modInvites, refetchInterval: 15_000 },
    ],
  });
  const users = usersQuery.data ?? [];
  const invites = invitesQuery.data ?? [];
  const loading = usersQuery.isPending || invitesQuery.isPending;
  const error = actionError || (usersQuery.error || invitesQuery.error)?.message || "";

  const adminCount = users.filter((user) => user.role === "admin").length;
  const modCount = users.filter((user) => user.role === "mod").length;

  const normalizedInviteEmail = inviteEmail.trim().toLowerCase();
  const inviteeExisting = normalizedInviteEmail
    ? users.find((user) => user.email.toLowerCase() === normalizedInviteEmail)
    : null;

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return users.filter((user) => {
      if (roleFilter && user.role !== roleFilter) return false;
      if (!needle) return true;
      return user.display_name?.toLowerCase().includes(needle) || user.email?.toLowerCase().includes(needle);
    });
  }, [users, roleFilter, query]);

  const paged = usePagination(filtered, pageSize, `${roleFilter}|${query}`);
  const pendingInvites = useLoadMore(invites, INVITES_STEP);

  const patchUsers = (updater) => queryClient.setQueryData(queryKeys.users, (items) => updater(items ?? []));
  const patchInvites = (updater) => queryClient.setQueryData(queryKeys.modInvites, (items) => updater(items ?? []));
  const load = useCallback(() => {
    setActionError("");
    queryClient.invalidateQueries({ queryKey: ["auth"] });
  }, [queryClient]);

  const invite = async (event) => {
    event.preventDefault();
    setSaving(true);
    try {
      const pending = await auth.inviteMod(inviteEmail);
      patchInvites((items) => [pending, ...items.filter((item) => item.email !== pending.email)]);
      setInviteEmail("");
      setActionError("");
      toast.success(pending.email_sent ? `Đã gửi lời mời tới ${pending.email}.` : `Đã tạo lời mời cho ${pending.email}. Hãy copy link và gửi thủ công.`);
    } catch (err) {
      setActionError(err.message);
      toast.error(err.message);
    } finally {
      setSaving(false);
    }
  };

  const resendInvite = async (email) => {
    setSaving(true);
    try {
      const pending = await auth.inviteMod(email);
      patchInvites((items) => [pending, ...items.filter((item) => item.email !== pending.email)]);
      setActionError("");
      toast.success(pending.email_sent ? `Đã gửi lại email tới ${pending.email}.` : `Chưa gửi được email tới ${pending.email}. Hãy copy link và gửi thủ công.`);
    } catch (err) {
      setActionError(err.message);
      toast.error(err.message);
    } finally {
      setSaving(false);
    }
  };

  const cancelInvite = async (email) => {
    if (!window.confirm(`Hủy lời mời gửi tới ${email}?`)) return;
    try {
      await auth.deleteModInvite(email);
      patchInvites((items) => items.filter((item) => item.email !== email));
      toast.success(`Đã hủy lời mời tới ${email}.`);
    } catch (err) {
      setActionError(err.message);
      toast.error(err.message);
    }
  };

  const copyInviteLink = async (inviteItem) => {
    try {
      await navigator.clipboard.writeText(inviteLink(inviteItem.token));
      setCopiedEmail(inviteItem.email);
      window.setTimeout(() => setCopiedEmail(""), 2000);
    } catch {
      setActionError("Không sao chép được link. Hãy tự chọn và copy thủ công.");
    }
  };

  const updateStatus = async (id, isActive) => {
    setBusyId(id);
    try {
      const user = await auth.updateStatus(id, isActive);
      patchUsers((items) => items.map((item) => (item.user_id === id ? user : item)));
      toast.success(isActive ? `Đã kích hoạt lại ${user.email}.` : `Đã khoá tài khoản ${user.email}.`);
    } catch (err) {
      setActionError(err.message);
      toast.error(err.message);
    } finally {
      setBusyId("");
    }
  };

  const remove = async (user) => {
    if (!window.confirm(`Xóa tài khoản ${user.email}? Thao tác này không thể hoàn tác.`)) return;
    setBusyId(user.user_id);
    try {
      await auth.deleteUser(user.user_id);
      patchUsers((items) => items.filter((item) => item.user_id !== user.user_id));
      toast.success(`Đã xóa tài khoản ${user.email}.`);
    } catch (err) {
      setActionError(err.message);
      toast.error(err.message);
    } finally {
      setBusyId("");
    }
  };

  return (
    <div className="page-grid">
      {error && <div className="page-grid__row"><ErrorState message={error} onRetry={load} /></div>}

      <div className="page-grid__row">
        <Card title="Mời Mod đăng ký" className="span-12">
          <p className="muted small">
            Chỉ email trong danh sách mời mới đăng ký được. Hệ thống tự gửi email chứa link mời nếu đã cấu hình SMTP; nếu
            không, hãy copy link và tự gửi cho Mod.
          </p>

          <form className="invite-form" onSubmit={invite}>
            <label className="invite-form__field">
              <span>Email Mod</span>
              <input
                required
                type="email"
                value={inviteEmail}
                onChange={(event) => setInviteEmail(event.target.value)}
                placeholder="mod@example.com"
              />
            </label>
            <button className="btn btn--primary" disabled={saving || Boolean(inviteeExisting)}>
              {saving ? "Đang lưu…" : "Mời email"}
            </button>
          </form>
          {inviteeExisting && (
            <p className="invite-form__warning" role="alert">
              Email này đã là {inviteeExisting.role === "admin" ? "Admin" : "Mod"}
              {inviteeExisting.is_root_admin ? " (Admin gốc)" : ""}, không thể mời lại.
            </p>
          )}

          <div className="card__divider-block">
            <p className="section-label">
              Lời mời đang chờ
              {invites.length > 0 && <span className="section-label__count">{invites.length}</span>}
            </p>

            {invites.length === 0 ? (
              <p className="muted small">Chưa có lời mời đang chờ.</p>
            ) : (
              <>
                <div className="invite-list">
                  {pendingInvites.visible.map((item) => (
                    <div className="invite-card" key={item.email}>
                      <div className="invite-card__head">
                        <span className="invite-card__email">{item.email}</span>
                        <Badge tone={item.email_sent ? "var(--sev-low)" : "var(--sev-medium)"}>
                          {item.email_sent ? "Đã gửi email" : "Chưa gửi được email"}
                        </Badge>
                        <button type="button" className="btn btn--danger" onClick={() => cancelInvite(item.email)}>
                          Hủy lời mời
                        </button>
                      </div>
                      <div className="invite-card__link">
                        <input
                          readOnly
                          value={inviteLink(item.token)}
                          onFocus={(event) => event.target.select()}
                          aria-label={`Link mời cho ${item.email}`}
                        />
                        <button type="button" className="btn btn--ghost" onClick={() => copyInviteLink(item)}>
                          {copiedEmail === item.email ? <><Check size={13} /> Đã copy</> : <><Copy size={13} /> Copy link</>}
                        </button>
                        <button type="button" className="btn btn--ghost" disabled={saving} onClick={() => resendInvite(item.email)}>
                          <PaperPlaneTilt size={13} /> Gửi lại email
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
                <LoadMore
                  remaining={pendingInvites.remaining}
                  step={INVITES_STEP}
                  unit="lời mời"
                  onMore={pendingInvites.showMore}
                  canCollapse={pendingInvites.canCollapse}
                  onCollapse={pendingInvites.collapse}
                />
              </>
            )}
          </div>
        </Card>
      </div>

      <div className="page-grid__row">
        <Card
          title="Tài khoản"
          className="span-12"
          action={
            <div className="account-tally">
              <span className="account-tally__item"><strong>{adminCount}</strong> Admin</span>
              <span className="account-tally__sep" aria-hidden="true">·</span>
              <span className="account-tally__item"><strong>{modCount}</strong> Mod</span>
            </div>
          }
        >
          <div className="table-toolbar">
            <div className="segmented" role="tablist" aria-label="Lọc theo vai trò">
              {ROLE_FILTERS.map(({ value, label }) => (
                <button
                  key={value || "all"}
                  type="button"
                  role="tab"
                  aria-selected={roleFilter === value}
                  className={`segmented__option ${roleFilter === value ? "is-active" : ""}`.trim()}
                  onClick={() => setRoleFilter(value)}
                >
                  {label}
                </button>
              ))}
            </div>
            <div className="search-box">
              <MagnifyingGlass size={15} />
              <input
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Tìm theo tên hoặc email..."
                aria-label="Tìm tài khoản"
              />
            </div>
          </div>

          {loading && <SkeletonBlock height={280} />}
          {!loading && users.length === 0 && <EmptyState message="Chưa có tài khoản nào." />}
          {!loading && users.length > 0 && filtered.length === 0 && (
            <EmptyState
              message={query ? `Không có tài khoản nào khớp "${query}".` : "Không có tài khoản nào ở vai trò này."}
            />
          )}

          {!loading && paged.slice.length > 0 && (
            <>
              <div className="data-table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th scope="col">Tên</th>
                      <th scope="col">Email</th>
                      <th scope="col">Vai trò</th>
                      <th scope="col">Trạng thái</th>
                      <th scope="col" className="data-table__actions-head">Tác động</th>
                    </tr>
                  </thead>
                  <tbody>
                    {paged.slice.map((user) => {
                      const busy = busyId === user.user_id;
                      return (
                        <tr key={user.user_id} className={user.is_active ? undefined : "data-table__row--muted"}>
                          <td>
                            <div className="user-cell">
                              <span
                                className={`user-cell__avatar ${user.role === "admin" ? "is-admin" : ""}`.trim()}
                                aria-hidden="true"
                              >
                                {initials(user.display_name, user.email)}
                              </span>
                              <span className="user-cell__name">{user.display_name || "—"}</span>
                            </div>
                          </td>
                          <td className="data-table__email">{user.email}</td>
                          <td>
                            <div className="chip-row">
                              <Badge tone={user.role === "admin" ? "var(--accent-solid)" : "var(--status-open)"}>
                                {user.role === "admin" ? "Admin" : "Mod"}
                              </Badge>
                              {user.is_root_admin && <Badge tone="var(--text-secondary)">Admin gốc</Badge>}
                            </div>
                          </td>
                          <td>
                            <span className={`status-dot ${user.is_active ? "status-dot--on" : "status-dot--off"}`}>
                              {user.is_active ? "Đang hoạt động" : "Đã khoá"}
                            </span>
                          </td>
                          <td className="data-table__actions">
                            {user.is_root_admin ? (
                              <span className="muted small">Không thể thay đổi</span>
                            ) : (
                              <div className="row-actions">
                                <button
                                  type="button"
                                  className="btn btn--ghost"
                                  disabled={busy}
                                  onClick={() => updateStatus(user.user_id, !user.is_active)}
                                  title={user.is_active ? "Khoá tài khoản" : "Kích hoạt lại tài khoản"}
                                >
                                  {user.is_active ? <LockSimple size={13} /> : <LockSimpleOpen size={13} />}
                                  {user.is_active ? "Khoá" : "Kích hoạt"}
                                </button>
                                <button
                                  type="button"
                                  className="icon-btn icon-btn--danger"
                                  disabled={busy}
                                  onClick={() => remove(user)}
                                  aria-label={`Xóa tài khoản ${user.email}`}
                                  title="Xóa tài khoản"
                                >
                                  <Trash size={15} />
                                </button>
                              </div>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              <Pagination
                page={paged.page}
                pageCount={paged.pageCount}
                onPageChange={paged.setPage}
                from={paged.from}
                to={paged.to}
                total={paged.total}
                unit="tài khoản"
                pageSize={pageSize}
                pageSizeOptions={PAGE_SIZE_OPTIONS}
                onPageSizeChange={setPageSize}
              />
            </>
          )}
        </Card>
      </div>
    </div>
  );
}
