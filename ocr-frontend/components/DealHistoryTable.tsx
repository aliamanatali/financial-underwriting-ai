"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiClient } from "@/lib/api";
import { DealPackage } from "@/lib/types";
import LoadingSpinner from "./LoadingSpinner";

type FilterType = "all" | "completed" | "in_progress" | "pending";

const STATUS_META: Record<string, { label: string; dot: string; pill: string; bar: string }> = {
  completed: {
    label: "Completed",
    dot: "bg-[#22C55E]",
    pill: "bg-[rgba(34,197,94,0.1)] text-[#16A34A] border border-[rgba(34,197,94,0.2)]",
    bar: "bg-[#22C55E]",
  },
  in_progress: {
    label: "Processing",
    dot: "bg-[#F97316] animate-pulse",
    pill: "bg-[rgba(249,115,22,0.1)] text-[#EA6C0A] border border-[rgba(249,115,22,0.2)]",
    bar: "bg-[#F97316]",
  },
  pending: {
    label: "Pending",
    dot: "bg-[#F59E0B]",
    pill: "bg-[rgba(245,158,11,0.1)] text-[#D97706] border border-[rgba(245,158,11,0.2)]",
    bar: "bg-[#F59E0B]",
  },
  failed: {
    label: "Failed",
    dot: "bg-[#EF4444]",
    pill: "bg-[rgba(239,68,68,0.1)] text-[#DC2626] border border-[rgba(239,68,68,0.2)]",
    bar: "bg-[#EF4444]",
  },
};

function getStatusMeta(status: string) {
  return STATUS_META[status] ?? STATUS_META.pending;
}

function formatDate(iso: string) {
  try {
    return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  } catch { return "—"; }
}

function formatRelativeDate(iso: string) {
  try {
    const date = new Date(iso);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    if (diffDays === 0) return "Today";
    if (diffDays === 1) return "Yesterday";
    if (diffDays < 7) return `${diffDays}d ago`;
    return formatDate(iso);
  } catch { return "—"; }
}

export default function DealHistoryTable() {
  const router = useRouter();
  const [packages, setPackages] = useState<DealPackage[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [renaming, setRenaming] = useState<string | null>(null);
  const [editingName, setEditingName] = useState<string | null>(null);
  const [newName, setNewName] = useState<string>("");
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);
  const [activeFilter, setActiveFilter] = useState<FilterType>("all");

  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(5);
  const [totalPackages, setTotalPackages] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [cache, setCache] = useState<Record<string, { data: unknown; timestamp: number }>>({});

  const fetchPackages = async (page: number = 1, limit: number = itemsPerPage) => {
    const cacheKey = `page_${page}_limit_${limit}`;
    const CACHE_DURATION = 30_000;
    if (cache[cacheKey] && Date.now() - (cache[cacheKey] as any).timestamp < CACHE_DURATION) {
      const cached = (cache[cacheKey] as any).data;
      setPackages(cached.packages);
      setTotalPackages(cached.total);
      setHasMore(cached.has_more);
      setCurrentPage(page);
      setLoading(false);
      return;
    }
    try {
      setLoading(true);
      const offset = (page - 1) * limit;
      const data = await apiClient.getDealPackages(limit, offset);
      setPackages(data.packages);
      setTotalPackages(data.total);
      setHasMore(data.has_more);
      setCurrentPage(page);
      setCache((prev) => ({ ...prev, [cacheKey]: { data, timestamp: Date.now() } }));
    } catch (err) {
      setError("Failed to load deal history");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { setCache({}); fetchPackages(1, itemsPerPage); }, [itemsPerPage]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    const handler = () => { if (openMenuId) setOpenMenuId(null); };
    document.addEventListener("click", handler);
    return () => document.removeEventListener("click", handler);
  }, [openMenuId]);

  const handleRowClick = (pkg: DealPackage) => {
    if (pkg.normalization_status === "pending") router.push(`/processing/${pkg.package_id}`);
    else router.push(`/analysis/${pkg.package_id}`);
  };

  const handleRename = async (e: React.MouseEvent, packageId: string) => {
    e.stopPropagation();
    if (!newName.trim()) { alert("Please enter a valid name."); return; }
    try {
      setRenaming(packageId);
      await apiClient.renameDealPackage(packageId, newName.trim());
      const updatedName = newName.trim();
      const now = new Date().toISOString();
      setPackages((prev) => prev.map((pkg) => pkg.package_id === packageId ? { ...pkg, property_name: updatedName, updated_at: now } : pkg));
      const cacheKey = `page_${currentPage}_limit_${itemsPerPage}`;
      setCache((prev) => {
        if (!prev[cacheKey]) return prev;
        const cached = prev[cacheKey] as any;
        return { ...prev, [cacheKey]: { ...prev[cacheKey], data: { ...cached.data, packages: cached.data.packages.map((pkg: DealPackage) => pkg.package_id === packageId ? { ...pkg, property_name: updatedName, updated_at: now } : pkg) } } };
      });
      setEditingName(null); setNewName(""); setOpenMenuId(null);
    } catch { alert("Failed to rename. Please try again."); }
    finally { setRenaming(null); }
  };

  const startRename = (e: React.MouseEvent, packageId: string, currentName: string) => {
    e.stopPropagation(); setEditingName(packageId); setNewName(currentName); setOpenMenuId(null);
  };
  const cancelRename = (e: React.MouseEvent) => { e.stopPropagation(); setEditingName(null); setNewName(""); };
  const toggleMenu = (e: React.MouseEvent, packageId: string) => { e.stopPropagation(); setOpenMenuId(openMenuId === packageId ? null : packageId); };

  const handleDelete = async (e: React.MouseEvent, packageId: string, propertyName: string) => {
    e.stopPropagation();
    if (!confirm(`Delete "${propertyName}"? This cannot be undone.`)) return;
    try {
      setDeleting(packageId);
      await apiClient.deleteDealPackage(packageId);
      setCache({});
      await fetchPackages(currentPage, itemsPerPage);
    } catch { alert("Failed to delete. Please try again."); }
    finally { setDeleting(null); }
  };

  const getTotalDocuments = (pkg: DealPackage) => {
    if (!pkg.documents) return 0;
    return Object.values(pkg.documents).reduce((sum, docs) => sum + docs.length, 0);
  };

  const handleItemsPerPageChange = (newSize: number) => {
    setItemsPerPage(newSize);
    setCache({});
    setCurrentPage(1);
    fetchPackages(1, newSize);
  };

  const filteredPackages = packages.filter((pkg) => {
    if (activeFilter === "all") return true;
    if (activeFilter === "completed") return pkg.normalization_status === "completed";
    if (activeFilter === "in_progress") return pkg.normalization_status === "in_progress";
    if (activeFilter === "pending") return pkg.normalization_status === "pending";
    return true;
  });

  const totalPages = Math.ceil(totalPackages / itemsPerPage);
  const startItem = (currentPage - 1) * itemsPerPage + 1;
  const endItem = Math.min(currentPage * itemsPerPage, totalPackages);

  const counts = {
    all: packages.length,
    completed: packages.filter((p) => p.normalization_status === "completed").length,
    in_progress: packages.filter((p) => p.normalization_status === "in_progress").length,
    pending: packages.filter((p) => p.normalization_status === "pending").length,
  };

  // ── States ───────────────────────────────────────────
  if (loading && packages.length === 0) {
    return <div className="flex justify-center items-center h-40"><LoadingSpinner /></div>;
  }

  if (error) {
    return (
      <div className="rounded-xl border border-[rgba(239,68,68,0.2)] bg-[rgba(239,68,68,0.06)] p-6 text-center">
        <p className="text-[#EF4444] text-sm">{error}</p>
        <button onClick={() => fetchPackages(currentPage, itemsPerPage)} className="mt-3 text-xs text-[#F97316] underline hover:no-underline">Try Again</button>
      </div>
    );
  }

  if (packages.length === 0 && !loading) {
    return (
      <div className="flex flex-col items-center justify-center py-24 rounded-2xl border border-dashed border-[#E2E8F0] bg-white">
        <div className="w-14 h-14 bg-[#F8FAFC] border border-[#E2E8F0] rounded-2xl flex items-center justify-center mb-4">
          <svg className="w-6 h-6 text-[#CBD5E1]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
            <path strokeLinecap="round" strokeLinejoin="round" d="M3 7a2 2 0 012-2h14a2 2 0 012 2v10a2 2 0 01-2 2H5a2 2 0 01-2-2V7z" /><path strokeLinecap="round" strokeLinejoin="round" d="M8 11h8M8 15h5" />
          </svg>
        </div>
        <p className="text-[#475569] font-semibold text-sm">No deals yet</p>
        <p className="text-[#94A3B8] text-xs mt-1">Upload a deal package to get started.</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">

      {/* ── Filter bar ─────────────────────────────────── */}
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-1.5 flex-wrap">
          {(["all", "completed", "in_progress", "pending"] as FilterType[]).map((f) => {
            const label = f === "all" ? "All" : f === "in_progress" ? "Processing" : f.charAt(0).toUpperCase() + f.slice(1);
            const count = counts[f];
            const isActive = activeFilter === f;
            return (
              <button
                key={f}
                onClick={() => setActiveFilter(f)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all ${
                  isActive
                    ? "bg-[#F97316] text-white shadow-[0_2px_8px_rgba(249,115,22,0.35)]"
                    : "bg-white text-[#64748B] border border-[#E2E8F0] hover:border-[#CBD5E1] hover:text-[#0F172A]"
                }`}
              >
                {label}
                <span className={`inline-flex items-center justify-center w-4 h-4 rounded-full text-[10px] font-bold ${isActive ? "bg-white/20 text-white" : "bg-[#F1F5F9] text-[#64748B]"}`}>
                  {count}
                </span>
              </button>
            );
          })}
        </div>
        <p className="text-xs text-[#94A3B8] shrink-0">
          Showing <span className="text-[#475569] font-medium">{startItem}–{endItem}</span> of <span className="text-[#475569] font-medium">{totalPackages}</span> deals
        </p>
      </div>

      {/* ── Table ──────────────────────────────────────── */}
      <div className="relative">
        {loading && packages.length > 0 && (
          <div className="absolute inset-0 bg-white/70 backdrop-blur-[2px] z-10 flex items-center justify-center rounded-2xl">
            <div className="flex items-center gap-2.5 bg-white border border-[#E2E8F0] px-4 py-2.5 rounded-xl shadow-sm">
              <svg className="animate-spin h-4 w-4 text-[#F97316]" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              <span className="text-xs font-medium text-[#0F172A]">Loading…</span>
            </div>
          </div>
        )}

        <div className="bg-white rounded-2xl border border-[#E2E8F0] overflow-hidden shadow-[0_1px_4px_rgba(0,0,0,0.05)]">
          {/* Table header */}
          <div className="grid grid-cols-[auto_1fr_140px_80px_100px_48px] items-center px-5 py-3 bg-[#F8FAFC] border-b border-[#E2E8F0]">
            <div className="w-1 mr-4" />
            <span className="text-[10px] font-bold text-[#94A3B8] uppercase tracking-widest">Deal Name</span>
            <span className="text-[10px] font-bold text-[#94A3B8] uppercase tracking-widest">Status</span>
            <span className="text-[10px] font-bold text-[#94A3B8] uppercase tracking-widest">Files</span>
            <span className="text-[10px] font-bold text-[#94A3B8] uppercase tracking-widest">Updated</span>
            <span />
          </div>

          {/* Rows */}
          {filteredPackages.map((pkg) => {
            const meta = getStatusMeta(pkg.normalization_status);
            const isDisabled = deleting === pkg.package_id || renaming === pkg.package_id;
            const docs = getTotalDocuments(pkg);

            return (
              <div
                key={pkg.package_id}
                onClick={() => !isDisabled && handleRowClick(pkg)}
                className={`group grid grid-cols-[auto_1fr_140px_80px_100px_48px] items-center px-5 py-4 border-b border-[#F1F5F9] last:border-b-0 transition-colors cursor-pointer ${
                  isDisabled ? "opacity-50 pointer-events-none" : "hover:bg-[#FAFBFF]"
                }`}
              >
                {/* Status color bar */}
                <div className={`w-1 h-8 rounded-full mr-4 shrink-0 ${meta.bar}`} />

                {/* Deal name */}
                <div className="min-w-0 pr-6">
                  {editingName === pkg.package_id ? (
                    <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
                      <input
                        type="text"
                        value={newName}
                        onChange={(e) => setNewName(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") handleRename(e as unknown as React.MouseEvent, pkg.package_id);
                          if (e.key === "Escape") cancelRename(e as unknown as React.MouseEvent);
                        }}
                        className="flex-1 px-2 py-1 text-sm bg-[#F8FAFC] border border-[#F97316]/40 rounded-lg text-[#0F172A] outline-none focus:ring-1 focus:ring-[#F97316]/50"
                        autoFocus
                      />
                      <button onClick={(e) => handleRename(e, pkg.package_id)} disabled={!!renaming} className="text-[#22C55E] hover:text-[#16A34A] disabled:opacity-40">
                        {renaming === pkg.package_id
                          ? <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" /></svg>
                          : <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
                        }
                      </button>
                      <button onClick={cancelRename} className="text-[#94A3B8] hover:text-[#475569]">
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                      </button>
                    </div>
                  ) : (
                    <div>
                      <p className="text-sm font-semibold text-[#0F172A] truncate leading-snug" title={pkg.property_name}>
                        {pkg.property_name || "Untitled Property"}
                      </p>
                    </div>
                  )}
                </div>

                {/* Status badge */}
                <div>
                  <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-semibold uppercase tracking-wide ${meta.pill}`}>
                    <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${meta.dot}`} />
                    {meta.label}
                  </span>
                </div>

                {/* Files */}
                <div className="flex items-center gap-1.5 text-xs text-[#64748B]">
                  <svg className="w-3.5 h-3.5 text-[#CBD5E1] shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                  </svg>
                  <span className="font-medium text-[#475569]">{docs}</span>
                  <span className="text-[#94A3B8]">{docs === 1 ? "file" : "files"}</span>
                </div>

                {/* Date */}
                <div className="text-xs text-[#94A3B8] tabular-nums">
                  {formatRelativeDate(pkg.updated_at)}
                  <p className="text-[9px] text-[#CBD5E1] mt-px">{formatDate(pkg.updated_at)}</p>
                </div>

                {/* Actions */}
                <div className="flex items-center justify-end" onClick={(e) => e.stopPropagation()}>
                  <div className="relative">
                    <button
                      onClick={(e) => toggleMenu(e, pkg.package_id)}
                      className="p-1.5 rounded-lg text-[#CBD5E1] hover:text-[#64748B] hover:bg-[#F1F5F9] transition-all"
                      aria-label="Deal actions"
                    >
                      <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                        <circle cx="12" cy="5" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="12" cy="19" r="1.5"/>
                      </svg>
                    </button>

                    {openMenuId === pkg.package_id && (
                      <div className="absolute right-0 mt-1 w-40 bg-white rounded-xl shadow-[0_8px_30px_rgba(0,0,0,0.12)] border border-[#E2E8F0] py-1 z-20">
                        <button
                          onClick={(e) => startRename(e, pkg.package_id, pkg.property_name)}
                          disabled={editingName === pkg.package_id || !!renaming}
                          className="w-full text-left px-3 py-2 text-xs text-[#475569] hover:text-[#0F172A] hover:bg-[#F8FAFC] disabled:opacity-40 flex items-center gap-2 transition-colors"
                        >
                          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" /></svg>
                          Rename
                        </button>
                        <div className="my-1 h-px bg-[#F1F5F9]" />
                        <button
                          onClick={(e) => handleDelete(e, pkg.package_id, pkg.property_name)}
                          disabled={!!deleting}
                          className="w-full text-left px-3 py-2 text-xs text-[#EF4444] hover:bg-[rgba(239,68,68,0.06)] disabled:opacity-40 flex items-center gap-2 transition-colors"
                        >
                          {deleting === pkg.package_id
                            ? <><svg className="animate-spin h-3.5 w-3.5" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" /></svg> Deleting…</>
                            : <><svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg> Delete</>
                          }
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}

          {/* ── Table footer / Pagination ─────────────────── */}
          {totalPackages > 0 && (
            <div className="flex items-center justify-between px-5 py-3 bg-[#F8FAFC] border-t border-[#E2E8F0]">
              {/* Left: per-page selector */}
              <div className="flex items-center gap-1.5">
                <span className="text-[11px] text-[#94A3B8]">Show</span>
                <select
                  value={itemsPerPage}
                  onChange={(e) => handleItemsPerPageChange(Number(e.target.value))}
                  className="h-7 px-1.5 rounded-lg border border-[#E2E8F0] bg-white text-[11px] font-medium text-[#475569] hover:border-[#CBD5E1] focus:outline-none focus:ring-1 focus:ring-[#F97316]/50 focus:border-[#F97316]/40 cursor-pointer transition-all appearance-none pr-5 bg-[url('data:image/svg+xml;charset=utf-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%2210%22%20height%3D%226%22%20fill%3D%22none%22%3E%3Cpath%20d%3D%22M1%201l4%204%204-4%22%20stroke%3D%22%2394A3B8%22%20stroke-width%3D%221.5%22%20stroke-linecap%3D%22round%22%20stroke-linejoin%3D%22round%22%2F%3E%3C%2Fsvg%3E')] bg-[length:10px_6px] bg-[right_6px_center] bg-no-repeat"
                >
                  {[5, 10, 25, 50].map((n) => (
                    <option key={n} value={n}>{n}</option>
                  ))}
                </select>
                <span className="text-[11px] text-[#94A3B8]">per page</span>
              </div>

              {/* Right: nav */}
              <div className="flex items-center gap-1">
                {/* Prev */}
                <button
                  onClick={() => fetchPackages(currentPage - 1, itemsPerPage)}
                  disabled={currentPage === 1 || loading}
                  className="flex items-center gap-1 pl-2 pr-2.5 h-7 rounded-lg border border-[#E2E8F0] bg-white text-[11px] font-medium text-[#64748B] hover:border-[#CBD5E1] hover:text-[#0F172A] disabled:opacity-30 disabled:cursor-not-allowed transition-all"
                >
                  <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}><path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" /></svg>
                  Prev
                </button>

                {/* Page pills */}
                <div className="flex items-center gap-0.5">
                  {(() => {
                    const pages: (number | "…")[] = [];
                    if (totalPages <= 5) {
                      for (let i = 1; i <= totalPages; i++) pages.push(i);
                    } else {
                      pages.push(1);
                      if (currentPage > 3) pages.push("…");
                      for (let i = Math.max(2, currentPage - 1); i <= Math.min(totalPages - 1, currentPage + 1); i++) pages.push(i);
                      if (currentPage < totalPages - 2) pages.push("…");
                      pages.push(totalPages);
                    }
                    return pages.map((p, i) =>
                      p === "…" ? (
                        <span key={`ell-${i}`} className="w-7 h-7 flex items-center justify-center text-[11px] text-[#94A3B8] select-none">…</span>
                      ) : (
                        <button
                          key={p}
                          onClick={() => fetchPackages(p as number, itemsPerPage)}
                          disabled={loading}
                          className={`w-7 h-7 flex items-center justify-center rounded-lg text-[11px] font-medium border transition-all ${
                            currentPage === p
                              ? "bg-[#0F172A] text-white border-[#0F172A] shadow-sm"
                              : "bg-white text-[#64748B] border-[#E2E8F0] hover:border-[#CBD5E1] hover:text-[#0F172A]"
                          }`}
                        >
                          {p}
                        </button>
                      )
                    );
                  })()}
                </div>

                {/* Next */}
                <button
                  onClick={() => fetchPackages(currentPage + 1, itemsPerPage)}
                  disabled={!hasMore || loading}
                  className="flex items-center gap-1 pl-2.5 pr-2 h-7 rounded-lg border border-[#E2E8F0] bg-white text-[11px] font-medium text-[#64748B] hover:border-[#CBD5E1] hover:text-[#0F172A] disabled:opacity-30 disabled:cursor-not-allowed transition-all"
                >
                  Next
                  <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}><path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" /></svg>
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
