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
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
            Completed
          </span>
        );
      case "in_progress":
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
            In Progress
          </span>
        );
      case "pending":
      default:
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
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
      <div className="text-center py-8 bg-gray-50 rounded-lg border border-gray-200 border-dashed">
        <p className="text-gray-500">No previous analyses found.</p>
      </div>
    );
  }

  return (
    <div className="bg-white shadow overflow-hidden sm:rounded-lg">
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th
                scope="col"
                className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
              >
                Property Name
              </th>
              <th
                scope="col"
                className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
              >
                Status
              </th>
              <th
                scope="col"
                className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
              >
                Documents
              </th>
              <th
                scope="col"
                className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
              >
                Last Updated
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {packages.map((pkg) => (
              <tr
                key={pkg.package_id}
                onClick={() => handleRowClick(pkg)}
                className="hover:bg-gray-50 cursor-pointer transition-colors"
              >
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className="text-sm font-medium text-gray-900">
                    {pkg.property_name || "Untitled Property"}
                  </div>
                  <div className="text-xs text-gray-500 font-mono">
                    {pkg.package_id.substring(0, 8)}...
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  {getStatusBadge(pkg.normalization_status)}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {getTotalDocuments(pkg)} files
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
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