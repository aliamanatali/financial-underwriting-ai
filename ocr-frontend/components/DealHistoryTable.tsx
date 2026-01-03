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

  const fetchPackages = async () => {
    try {
      setLoading(true);
      const data = await apiClient.getDealPackages();
      // Sort by updated_at desc
      const sorted = data.sort((a, b) => 
        new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
      );
      setPackages(sorted);
    } catch (err) {
      setError("Failed to load deal history");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPackages();
  }, []);

  const handleRowClick = (pkg: DealPackage) => {
    // If completed, go to analysis. If pending/in_progress, go to verification
    if (pkg.normalization_status === "completed") {
        router.push(`/analysis/${pkg.package_id}`);
    } else {
        router.push(`/verification/${pkg.package_id}`);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "completed":
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800 border border-emerald-200">
            Completed
          </span>
        );
      case "in_progress":
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800 border border-blue-200">
            In Progress
          </span>
        );
      case "pending":
      default:
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-800 border border-amber-200">
            Pending
          </span>
        );
    }
  };

  const getTotalDocuments = (pkg: DealPackage) => {
    if (!pkg.documents) return 0;
    return Object.values(pkg.documents).reduce((sum, docs) => sum + docs.length, 0);
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-32">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-center text-red-800">
        <p>{error}</p>
        <button 
            onClick={fetchPackages}
            className="mt-2 text-sm text-red-600 underline hover:text-red-800"
        >
            Try Again
        </button>
      </div>
    );
  }

  if (packages.length === 0) {
    return (
      <div className="text-center py-12 bg-slate-50 rounded-xl border border-slate-200 border-dashed">
        <p className="text-slate-500">No previous analyses found.</p>
      </div>
    );
  }

  return (
    <div className="bg-white shadow-sm ring-1 ring-slate-200 overflow-hidden sm:rounded-xl">
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-slate-200">
          <thead className="bg-slate-50">
            <tr>
              <th
                scope="col"
                className="px-6 py-4 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider"
              >
                Property Name
              </th>
              <th
                scope="col"
                className="px-6 py-4 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider"
              >
                Status
              </th>
              <th
                scope="col"
                className="px-6 py-4 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider"
              >
                Documents
              </th>
              <th
                scope="col"
                className="px-6 py-4 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider"
              >
                Last Updated
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-slate-200">
            {packages.map((pkg) => (
              <tr
                key={pkg.package_id}
                onClick={() => handleRowClick(pkg)}
                className="hover:bg-slate-50 cursor-pointer transition-colors duration-150 ease-in-out"
              >
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className="text-sm font-medium text-slate-900">
                    {pkg.property_name || "Untitled Property"}
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  {getStatusBadge(pkg.normalization_status)}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-500">
                  {getTotalDocuments(pkg)} files
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-500">
                  {new Date(pkg.updated_at).toLocaleDateString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}