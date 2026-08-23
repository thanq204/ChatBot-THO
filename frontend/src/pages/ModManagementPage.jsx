import { useCallback, useState } from "react";
import { useQueries, useQueryClient } from "@tanstack/react-query";
import { Copy, Check, PaperPlaneTilt } from "@phosphor-icons/react";
import Card from "../components/Card.jsx";
import Badge from "../components/Badge.jsx";
import { ErrorState, EmptyState } from "../components/StatePanels.jsx";
import { auth } from "../api/client.js";
import { queryKeys } from "../lib/queryClient.js";

const EMPTY = { email: "", display_name: "", password: "", role: "mod" };

function inviteLink(token) {
  return `${window.location.origin}/dang-ky?token=${token}`;
}

export default function ModManagementPage() {
  const queryClient = useQueryClient();
  const [form, setForm] = useState(EMPTY); const [inviteEmail, setInviteEmail] = useState(""); const [saving, setSaving] = useState(false); const [actionError, setActionError] = useState(""); const [copiedEmail, setCopiedEmail] = useState("");
  // A Mod accepts their invite from a link on a different device, so this tab
  // never gets a window-focus event to trigger React Query's default refetch.
  // Poll while this page is open so a pending invite clears itself once used.
  const [usersQuery, invitesQuery] = useQueries({ queries: [
    { queryKey: queryKeys.users, queryFn: auth.users, refetchInterval: 15_000 },
    { queryKey: queryKeys.modInvites, queryFn: auth.modInvites, refetchInterval: 15_000 },
  ] });
  const users = usersQuery.data ?? []; const invites = invitesQuery.data ?? [];
  const loading = usersQuery.isPending || invitesQuery.isPending;
  const error = actionError || (usersQuery.error || invitesQuery.error)?.message || "";
  // Writes return the saved row, so patch it into the cache instead of refetching.
  const patchUsers = (updater) => queryClient.setQueryData(queryKeys.users, (items) => updater(items ?? []));
  const patchInvites = (updater) => queryClient.setQueryData(queryKeys.modInvites, (items) => updater(items ?? []));
  const load = useCallback(() => { setActionError(""); queryClient.invalidateQueries({ queryKey: ["auth"] }); }, [queryClient]);
  const create = async (event) => { event.preventDefault(); setSaving(true); try { const user = await auth.createUser(form); patchUsers((items) => [...items, user]); setForm(EMPTY); setActionError(""); } catch (err) { setActionError(err.message); } finally { setSaving(false); } };
  const invite = async (event) => { event.preventDefault(); setSaving(true); try { const pending = await auth.inviteMod(inviteEmail); patchInvites((items) => [pending, ...items.filter((item) => item.email !== pending.email)]); setInviteEmail(""); setActionError(""); } catch (err) { setActionError(err.message); } finally { setSaving(false); } };
  const resendInvite = async (email) => { setSaving(true); try { const pending = await auth.inviteMod(email); patchInvites((items) => [pending, ...items.filter((item) => item.email !== pending.email)]); setActionError(""); } catch (err) { setActionError(err.message); } finally { setSaving(false); } };
  const cancelInvite = async (email) => { if (!window.confirm(`Hủy lời mời gửi tới ${email}?`)) return; try { await auth.deleteModInvite(email); patchInvites((items) => items.filter((item) => item.email !== email)); } catch (err) { setActionError(err.message); } };
  const copyInviteLink = async (invite) => { try { await navigator.clipboard.writeText(inviteLink(invite.token)); setCopiedEmail(invite.email); window.setTimeout(() => setCopiedEmail(""), 2000); } catch { setActionError("Không sao chép được link. Hãy tự chọn và copy thủ công."); } };
  const update = async (id, changes) => { try { const user = changes.role ? await auth.updateRole(id, changes.role) : await auth.updateStatus(id, changes.is_active); patchUsers((items) => items.map((item) => item.user_id === id ? user : item)); } catch (err) { setActionError(err.message); } };
  const remove = async (user) => { if (!window.confirm(`Xóa tài khoản ${user.email}? Thao tác này không thể hoàn tác.`)) return; try { await auth.deleteUser(user.user_id); patchUsers((items) => items.filter((item) => item.user_id !== user.user_id)); } catch (err) { setActionError(err.message); } };
  const mods = users.filter((user) => user.role === "mod");
  const normalizedInviteEmail = inviteEmail.trim().toLowerCase();
  const inviteeExisting = normalizedInviteEmail ? users.find((user) => user.email.toLowerCase() === normalizedInviteEmail) : null;
  return <div className="page-grid">
    {error && <div className="page-grid__row"><ErrorState message={error} onRetry={load} /></div>}
    <div className="page-grid__row">
      <Card title="Tạo tài khoản thủ công" className="span-5"><p className="muted small">Chỉ Admin có thể tạo tài khoản và phân quyền. Mật khẩu được lưu dưới dạng hash.</p><form className="stack-form" onSubmit={create}><label>Email<input required type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></label><label>Tên hiển thị<input required value={form.display_name} onChange={(e) => setForm({ ...form, display_name: e.target.value })} /></label><label>Mật khẩu tạm thời<input required minLength="8" type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></label><label>Vai trò<select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}><option value="mod">Kiểm duyệt viên</option><option value="admin">Quản trị viên</option></select></label><button className="btn btn--primary" disabled={saving}>{saving ? "Đang lưu…" : "Tạo tài khoản"}</button></form></Card>
      <Card title="Mời Mod đăng ký" className="span-7"><p className="muted small">Chỉ email trong danh sách mời mới đăng ký được. Khi mời, hệ thống tự gửi email chứa link mời (nếu đã cấu hình SMTP). Nếu gửi thất bại hoặc chưa cấu hình, hãy copy link bên dưới và tự gửi cho Mod qua kênh khác.</p><form className="stack-form" onSubmit={invite}><label>Email Mod<input required type="email" value={inviteEmail} onChange={(e) => setInviteEmail(e.target.value)} placeholder="mod@example.com" /></label>{inviteeExisting && <p className="small" style={{ color: "var(--sev-critical)" }}>Email này đã là {inviteeExisting.role === "admin" ? "Admin" : "Mod"}{inviteeExisting.is_root_admin ? " (Admin gốc)" : ""}, không thể mời lại.</p>}<button className="btn btn--primary" disabled={saving || Boolean(inviteeExisting)}>{saving ? "Đang lưu…" : "Mời email"}</button></form><div className="list">{invites.length === 0 ? <p className="muted small">Chưa có lời mời đang chờ.</p> : invites.map((item) => <div className="list-row" key={item.email}><div className="list-row__head"><div className="chip-row"><strong>{item.email}</strong><Badge tone={item.email_sent ? "success" : "alert"}>{item.email_sent ? "Đã gửi email" : "Chưa gửi được email"}</Badge></div><button className="btn btn--danger" onClick={() => cancelInvite(item.email)}>Hủy lời mời</button></div><div className="stack-form" style={{ display: "flex", alignItems: "center", gap: 8 }}><input readOnly value={inviteLink(item.token)} onFocus={(e) => e.target.select()} style={{ flex: 1, fontSize: 12.5 }} /><button type="button" className="btn btn--ghost" onClick={() => copyInviteLink(item)}>{copiedEmail === item.email ? <><Check size={13} /> Đã copy</> : <><Copy size={13} /> Copy link</>}</button><button type="button" className="btn btn--ghost" disabled={saving} onClick={() => resendInvite(item.email)}><PaperPlaneTilt size={13} /> Gửi lại email</button></div></div>)}</div></Card>
    </div>
    <div className="page-grid__row"><Card title={`Tài khoản Mod (${mods.length})`} className="span-12">{loading && <p className="muted">Đang tải…</p>}{!loading && users.length === 0 && <EmptyState message="Chưa có tài khoản nào." />}{!loading && users.length > 0 && <div className="list">{users.map((user) => <div className="list-row" key={user.user_id}><div className="list-row__head"><div><strong>{user.display_name}</strong><p className="muted small">{user.email}</p></div><div className="chip-row"><Badge tone={user.role === "admin" ? "brand" : "neutral"}>{user.role === "admin" ? "Admin" : "Mod"}</Badge><Badge tone={user.is_active ? "success" : "alert"}>{user.is_active ? "Đang hoạt động" : "Đã khoá"}</Badge>{user.is_root_admin && <Badge tone="brand">Admin gốc</Badge>}</div></div>{!user.is_root_admin && <div className="chip-row"><button className="btn btn--ghost" onClick={() => update(user.user_id, { role: user.role === "admin" ? "mod" : "admin" })}>Đổi thành {user.role === "admin" ? "Mod" : "Admin"}</button><button className="btn btn--ghost" onClick={() => update(user.user_id, { is_active: !user.is_active })}>{user.is_active ? "Khoá tài khoản" : "Kích hoạt"}</button><button className="btn btn--danger" onClick={() => remove(user)}>Xóa tài khoản</button></div>}</div>)}</div>}</Card></div>
  </div>;
}
