"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiClient } from "@/lib/api";
import { DealPackage } from "@/lib/types";
import LoadingSpinner from "./LoadingSpinner";

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
  
  // Pagination state
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(5);
  const [totalPackages, setTotalPackages] = useState(0);
  const [hasMore, setHasMore] = useState(false);

  // Cache state
  const [cache, setCache] = useState<Record<string, { data: any, timestamp: number }>>({});

  const fetchPackages = async (page: number = 1, limit: number = itemsPerPage) => {
    const cacheKey = `page_${page}_limit_${limit}`;
    const CACHE_DURATION = 30000; // 30 seconds

    // Check cache first
    if (cache[cacheKey] && Date.now() - cache[cacheKey].timestamp < CACHE_DURATION) {
      const cached = cache[cacheKey].data;
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
      
      // Update cache
      setCache(prev => ({
        ...prev,
        [cacheKey]: { data, timestamp: Date.now() }
      }));
    } catch (err) {
      setError("Failed to load deal history");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // Clear cache when changing items per page to avoid stale/mismatched data logic
    setCache({});
    fetchPackages(1, itemsPerPage);
  }, [itemsPerPage]);

  // Close menu when clicking outside
  useEffect(() => {
    const handleClickOutside = () => {
      if (openMenuId) {
        setOpenMenuId(null);
      }
    };
    
    document.addEventListener('click', handleClickOutside);
    return () => document.removeEventListener('click', handleClickOutside);
  }, [openMenuId]);

  const handleRowClick = (pkg: DealPackage) => {
    if (pkg.normalization_status === "pending") {
      router.push(`/processing/${pkg.package_id}`);
    } else {
      router.push(`/analysis/${pkg.package_id}`);
    }
  };

  const handleRename = async (e: React.MouseEvent, packageId: string) => {
    e.stopPropagation(); // Prevent row click
    
    if (!newName.trim()) {
      alert("Please enter a valid name.");
      return;
    }

    try {
      setRenaming(packageId);
      await apiClient.renameDealPackage(packageId, newName.trim());
      
      // Update local state without refetching
      const updatedName = newName.trim();
      const now = new Date().toISOString();
      
      setPackages(prev => prev.map(pkg =>
        pkg.package_id === packageId
          ? { ...pkg, property_name: updatedName, updated_at: now }
          : pkg
      ));

      // Update cache
      const cacheKey = `page_${currentPage}_limit_${itemsPerPage}`;
      setCache(prev => {
        if (!prev[cacheKey]) return prev;
        return {
          ...prev,
          [cacheKey]: {
            ...prev[cacheKey],
            data: {
              ...prev[cacheKey].data,
              packages: prev[cacheKey].data.packages.map((pkg: DealPackage) =>
                pkg.package_id === packageId
                  ? { ...pkg, property_name: updatedName, updated_at: now }
                  : pkg
              )
            }
          }
        };
      });

      setEditingName(null);
      setNewName("");
      setOpenMenuId(null);
    } catch (err) {
      console.error("Failed to rename package:", err);
      alert("Failed to rename package. Please try again.");
    } finally {
      setRenaming(null);
    }
  };

  const startRename = (e: React.MouseEvent, packageId: string, currentName: string) => {
    e.stopPropagation(); // Prevent row click
    setEditingName(packageId);
    setNewName(currentName);
    setOpenMenuId(null);
  };

  const cancelRename = (e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent row click
    setEditingName(null);
    setNewName("");
  };

  const toggleMenu = (e: React.MouseEvent, packageId: string) => {
    e.stopPropagation(); // Prevent row click
    setOpenMenuId(openMenuId === packageId ? null : packageId);
  };

  const closeMenu = () => {
    setOpenMenuId(null);
  };

  const handleDelete = async (e: React.MouseEvent, packageId: string, propertyName: string) => {
    e.stopPropagation(); // Prevent row click
    
    if (!confirm(`Are you sure you want to delete "${propertyName}"? This action cannot be undone.`)) {
      return;
    }

    try {
      setDeleting(packageId);
      await apiClient.deleteDealPackage(packageId);
      // Clear cache to force refresh
      setCache({});
      // Refresh the current page
      await fetchPackages(currentPage, itemsPerPage);
    } catch (err) {
      console.error("Failed to delete package:", err);
      alert("Failed to delete package. Please try again.");
    } finally {
      setDeleting(null);
    }
  };

  const handleNextPage = () => {
    if (hasMore) {
      fetchPackages(currentPage + 1, itemsPerPage);
    }
  };

  const handlePrevPage = () => {
    if (currentPage > 1) {
      fetchPackages(currentPage - 1, itemsPerPage);
    }
  };

  const handleItemsPerPageChange = (newLimit: number) => {
    setItemsPerPage(newLimit);
    setCurrentPage(1);
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "completed":
        return (
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full border border-emerald-100 bg-emerald-50 w-fit">
            <div className="w-1.5 h-1.5 rounded-full bg-emerald-500"></div>
            <span className="text-[10px] font-semibold text-emerald-700 uppercase tracking-wide">
              Completed
            </span>
          </div>
        );
      case "in_progress":
        return (
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full border border-sky-100 bg-sky-50 w-fit">
            <div className="w-1.5 h-1.5 rounded-full bg-sky-500 animate-pulse"></div>
            <span className="text-[10px] font-semibold text-sky-700 uppercase tracking-wide">
              In Progress
            </span>
          </div>
        );
      case "pending":
      default:
        return (
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full border border-amber-100 bg-amber-50 w-fit">
            <div className="w-1.5 h-1.5 rounded-full bg-amber-500"></div>
            <span className="text-[10px] font-semibold text-amber-700 uppercase tracking-wide">
              Pending
            </span>
          </div>
        );
    }
  };

  const getTotalDocuments = (pkg: DealPackage) => {
    if (!pkg.documents) return 0;
    return Object.values(pkg.documents).reduce((sum, docs) => sum + docs.length, 0);
  };

  const totalPages = Math.ceil(totalPackages / itemsPerPage);
  const startItem = (currentPage - 1) * itemsPerPage + 1;
  const endItem = Math.min(currentPage * itemsPerPage, totalPackages);

  if (loading && packages.length === 0) {
    return (
      <div className="flex justify-center items-center h-32">
        <LoadingSpinner />
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-center text-red-800">
        <p>{error}</p>
        <button 
            onClick={() => fetchPackages(currentPage, itemsPerPage)}
            className="mt-2 text-sm text-red-600 underline hover:text-red-800"
        >
            Try Again
        </button>
      </div>
    );
  }

  if (packages.length === 0 && !loading) {
    return (
      <div className="text-center py-12 bg-neutral-50 rounded-xl border border-neutral-200 border-dashed">
        <p className="text-neutral-500">No previous analyses found.</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col">
      {/* Toolbar */}
      <div className="px-6 py-4 border-b border-neutral-100 flex items-center justify-between bg-neutral-50/30">
        <div className="flex items-center gap-3">
          <button className="flex items-center gap-1.5 px-3 py-1.5 bg-white border border-neutral-200 rounded-md text-xs font-medium text-neutral-600 shadow-sm hover:text-neutral-900 transition-colors">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="12"
              height="12"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"></polygon>
            </svg>
            Status
          </button>
          <div className="flex items-center gap-2">
            <label htmlFor="itemsPerPage" className="text-xs text-neutral-600">
              Show:
            </label>
            <select
              id="itemsPerPage"
              value={itemsPerPage}
              onChange={(e) => handleItemsPerPageChange(Number(e.target.value))}
              className="px-3 py-1.5 text-xs border border-neutral-200 rounded-md focus:outline-none focus:ring-1 focus:ring-neutral-300 bg-white shadow-sm"
            >
              <option value={5}>5 per page</option>
              <option value={10}>10 per page</option>
              <option value={20}>20 per page</option>
              <option value={50}>50 per page</option>
            </select>
          </div>
        </div>
        <div className="text-xs text-neutral-500 font-medium">
          Showing {startItem}-{endItem} of {totalPackages} packages
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto relative">
        {/* Loading Overlay */}
        {loading && packages.length > 0 && (
          <div className="absolute inset-0 bg-white/60 backdrop-blur-[2px] z-10 flex items-center justify-center">
            <div className="flex items-center gap-3 bg-white px-4 py-3 rounded-lg shadow-lg border border-neutral-200">
              <svg className="animate-spin h-5 w-5 text-neutral-600" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              <span className="text-sm font-medium text-neutral-700">Loading deals...</span>
            </div>
          </div>
        )}
        
        <table className="w-full text-left whitespace-nowrap">
          <thead>
            <tr className="bg-neutral-50/50 border-b border-neutral-100">
              <th className="py-3 px-6 text-xs font-semibold uppercase tracking-wider text-neutral-500">
                Property Name
              </th>
              <th className="py-3 px-6 text-xs font-semibold uppercase tracking-wider text-neutral-500">
                Status
              </th>
              <th className="py-3 px-6 text-xs font-semibold uppercase tracking-wider text-neutral-500">
                Documents
              </th>
              <th className="py-3 px-6 text-xs font-semibold uppercase tracking-wider text-neutral-500">
                Last Updated
              </th>
              <th className="py-3 px-6 text-xs font-semibold uppercase tracking-wider text-neutral-500 text-center">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-neutral-100">
            {packages.map((pkg) => (
              <tr
                key={pkg.package_id}
                onClick={() => handleRowClick(pkg)}
                className={`group hover:bg-neutral-50 transition-colors cursor-pointer ${
                  (deleting === pkg.package_id || renaming === pkg.package_id) ? 'opacity-60 pointer-events-none' : ''
                }`}
              >
                <td className="py-4 px-6">
                  <div className="flex flex-col">
                    {editingName === pkg.package_id ? (
                      <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
                        <input
                          type="text"
                          value={newName}
                          onChange={(e) => setNewName(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') {
                              const mouseEvent = new MouseEvent('click') as unknown as React.MouseEvent;
                              handleRename(mouseEvent, pkg.package_id);
                            } else if (e.key === 'Escape') {
                              const mouseEvent = new MouseEvent('click') as unknown as React.MouseEvent;
                              cancelRename(mouseEvent);
                            }
                          }}
                          className="px-2 py-1 text-sm border border-neutral-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                          autoFocus
                        />
                        <button
                          onClick={(e) => handleRename(e, pkg.package_id)}
                          disabled={renaming === pkg.package_id}
                          className="text-green-600 hover:text-green-800 disabled:opacity-50 flex items-center justify-center w-6 h-6"
                          title="Save"
                        >
                          {renaming === pkg.package_id ? (
                            <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                            </svg>
                          ) : (
                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                            </svg>
                          )}
                        </button>
                        <button
                          onClick={cancelRename}
                          className="text-neutral-600 hover:text-neutral-800"
                          title="Cancel"
                        >
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                          </svg>
                        </button>
                      </div>
                    ) : (
                      <span className="font-semibold text-neutral-900 text-sm group-hover:text-neutral-700 transition-colors">
                        {pkg.property_name || "Untitled Property"}
                      </span>
                    )}
                  </div>
                </td>
                <td className="py-4 px-6">
                  {getStatusBadge(pkg.normalization_status)}
                </td>
                <td className="py-4 px-6">
                  <span className="text-sm text-neutral-600">
                    {getTotalDocuments(pkg)} files
                  </span>
                </td>
                <td className="py-4 px-6">
                  <span className="text-sm text-neutral-600">
                    {new Date(pkg.updated_at).toLocaleDateString()}
                  </span>
                </td>
                <td className="py-4 px-6 text-center relative">
                  <div className="relative inline-block">
                    <button
                      onClick={(e) => toggleMenu(e, pkg.package_id)}
                      className="p-1 rounded hover:bg-neutral-100 transition-colors"
                      title="More actions"
                    >
                      <svg className="w-5 h-5 text-neutral-600" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M12 8c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zm0 2c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2zm0 6c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2z" />
                      </svg>
                    </button>
                    
                    {openMenuId === pkg.package_id && (
                      <div className="absolute right-0 mt-1 w-48 bg-white rounded-lg shadow-lg border border-neutral-200 py-1 z-10">
                        <button
                          onClick={(e) => startRename(e, pkg.package_id, pkg.property_name)}
                          disabled={editingName === pkg.package_id || renaming === pkg.package_id}
                          className="w-full text-left px-4 py-2 text-sm text-neutral-700 hover:bg-neutral-50 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                        >
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                          </svg>
                          Rename
                        </button>
                        <button
                          onClick={(e) => handleDelete(e, pkg.package_id, pkg.property_name)}
                          disabled={deleting === pkg.package_id}
                          className="w-full text-left px-4 py-2 text-sm text-red-600 hover:bg-red-50 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                        >
                          {deleting === pkg.package_id ? (
                            <>
                              <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                              </svg>
                              Deleting...
                            </>
                          ) : (
                            <>
                              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                              </svg>
                              Delete
                            </>
                          )}
                        </button>
                      </div>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="px-6 py-4 border-t border-neutral-100 flex items-center justify-between bg-neutral-50/30">
          <button
            onClick={handlePrevPage}
            disabled={currentPage === 1 || loading}
            className="flex items-center gap-1.5 text-xs font-medium text-neutral-500 hover:text-neutral-900 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            Previous
          </button>
          <div className="flex items-center gap-1">
            {Array.from({ length: Math.min(totalPages, 5) }, (_, i) => {
              const pageNum = i + 1;
              return (
                <button
                  key={pageNum}
                  onClick={() => fetchPackages(pageNum, itemsPerPage)}
                  disabled={loading}
                  className={`w-7 h-7 flex items-center justify-center rounded-md text-xs font-medium transition-colors ${
                    currentPage === pageNum
                      ? "bg-white border border-neutral-200 text-neutral-900 shadow-sm"
                      : "text-neutral-500 hover:bg-neutral-100"
                  }`}
                >
                  {pageNum}
                </button>
              );
            })}
          </div>
          <button
            onClick={handleNextPage}
            disabled={!hasMore || loading}
            className="flex items-center gap-1.5 text-xs font-medium text-neutral-500 hover:text-neutral-900 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            Next
            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </button>
        </div>
      )}
    </div>
  );
}
