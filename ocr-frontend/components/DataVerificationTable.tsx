"use client";

import { useState } from "react";

export interface NormalizedDataItem {
  id: string;
  raw_text: string;
  normalized_value: string;
  field_type: string;
  confidence: number;
  user_verified: boolean;
  user_correction?: string | null;
  source_document: string;
}

interface DataVerificationTableProps {
  items: NormalizedDataItem[];
  availableCategories: string[];
  onVerify: (itemId: string, userCorrection?: string) => void;
  onVerifyAll: () => void;
}

export default function DataVerificationTable({
  items,
  availableCategories,
  onVerify,
  onVerifyAll,
}: DataVerificationTableProps) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState<string>("");

  const handleEdit = (item: NormalizedDataItem) => {
    setEditingId(item.id);
    setEditValue(item.user_correction || item.normalized_value);
  };

  const handleSave = (itemId: string) => {
    const originalItem = items.find((i) => i.id === itemId);
    if (originalItem && editValue !== originalItem.normalized_value) {
      onVerify(itemId, editValue);
    } else {
      onVerify(itemId);
    }
    setEditingId(null);
    setEditValue("");
  };

  const handleCancel = () => {
    setEditingId(null);
    setEditValue("");
  };

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.95) return "text-emerald-700 bg-emerald-50 border border-emerald-100";
    if (confidence >= 0.85) return "text-amber-700 bg-amber-50 border border-amber-100";
    return "text-rose-700 bg-rose-50 border border-rose-100";
  };

  const verifiedCount = items.filter((item) => item.user_verified).length;
  const totalCount = items.length;
  const progressPercentage = totalCount > 0 ? (verifiedCount / totalCount) * 100 : 0;

  return (
    <div className="space-y-6">
      {/* Header with Progress */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-8">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-2xl font-bold text-slate-900">
              Data Verification
            </h2>
            <p className="text-base text-slate-500 mt-1">
              Review and correct AI-mapped categories
            </p>
          </div>
          <button
            onClick={onVerifyAll}
            disabled={verifiedCount === totalCount}
            className={`px-6 py-2.5 rounded-lg font-medium transition-colors ${
              verifiedCount === totalCount
                ? "bg-slate-100 text-slate-400 cursor-not-allowed"
                : "bg-blue-600 text-white hover:bg-blue-700 shadow-md hover:shadow-lg"
            }`}
          >
            Verify All
          </button>
        </div>

        {/* Progress Bar */}
        <div className="space-y-3">
          <div className="flex justify-between text-sm font-medium text-slate-600">
            <span>
              Verified: <span className="text-slate-900">{verifiedCount}</span> / {totalCount}
            </span>
            <span className="text-slate-900">{progressPercentage.toFixed(0)}%</span>
          </div>
          <div className="w-full bg-slate-100 rounded-full h-3 overflow-hidden">
            <div
              className="bg-blue-600 h-3 rounded-full transition-all duration-500 ease-out"
              style={{ width: `${progressPercentage}%` }}
            />
          </div>
        </div>
      </div>

      {/* Split-Screen Table */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200">
            <thead className="bg-slate-50">
              <tr>
                <th className="px-6 py-4 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">
                  Source Document
                </th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">
                  Raw Text (PDF)
                </th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">
                  Mapped Category
                </th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">
                  Confidence
                </th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-4 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-slate-200">
              {items.map((item) => (
                <tr
                  key={item.id}
                  className={`transition-colors duration-150 ${
                    item.user_verified ? "bg-emerald-50/30" : "hover:bg-slate-50"
                  }`}
                >
                  {/* Source Document */}
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-500">
                    <div className="flex items-center">
                        <svg className="w-4 h-4 mr-2 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                        {item.source_document}
                    </div>
                  </td>

                  {/* Raw Text */}
                  <td className="px-6 py-4 text-sm text-slate-900">
                    <div className="max-w-xs">
                      <span className="font-mono text-xs bg-slate-100 px-2 py-1.5 rounded-md text-slate-600 border border-slate-200">
                        {item.raw_text}
                      </span>
                    </div>
                  </td>

                  {/* Mapped Category */}
                  <td className="px-6 py-4 text-sm">
                    {editingId === item.id ? (
                      <select
                        value={editValue}
                        onChange={(e) => setEditValue(e.target.value)}
                        className="block w-full px-3 py-2 text-sm border-slate-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
                        autoFocus
                      >
                        {availableCategories.map((category) => (
                          <option key={category} value={category}>
                            {category}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <div className="flex items-center space-x-2">
                        <span
                          className={`font-medium ${
                            item.user_correction
                              ? "text-blue-700"
                              : "text-slate-900"
                          }`}
                        >
                          {item.user_correction || item.normalized_value}
                        </span>
                        {item.user_correction && (
                          <span className="text-[10px] uppercase font-bold text-blue-600 bg-blue-50 px-2 py-1 rounded-full border border-blue-100">
                            Edited
                          </span>
                        )}
                      </div>
                    )}
                  </td>

                  {/* Confidence */}
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span
                      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getConfidenceColor(
                        item.confidence
                      )}`}
                    >
                      {(item.confidence * 100).toFixed(0)}%
                    </span>
                  </td>

                  {/* Status */}
                  <td className="px-6 py-4 whitespace-nowrap">
                    {item.user_verified ? (
                      <span className="inline-flex items-center text-emerald-700 font-medium text-sm">
                        <svg
                          className="w-4 h-4 mr-1.5"
                          fill="currentColor"
                          viewBox="0 0 20 20"
                        >
                          <path
                            fillRule="evenodd"
                            d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                            clipRule="evenodd"
                          />
                        </svg>
                        Verified
                      </span>
                    ) : (
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-600 border border-slate-200">
                        Pending
                      </span>
                    )}
                  </td>

                  {/* Actions */}
                  <td className="px-6 py-4 whitespace-nowrap text-sm">
                    {editingId === item.id ? (
                      <div className="flex space-x-3">
                        <button
                          onClick={() => handleSave(item.id)}
                          className="text-emerald-600 hover:text-emerald-800 font-semibold"
                        >
                          Save
                        </button>
                        <button
                          onClick={handleCancel}
                          className="text-slate-500 hover:text-slate-700 font-medium"
                        >
                          Cancel
                        </button>
                      </div>
                    ) : (
                      <div className="flex items-center space-x-4">
                        {!item.user_verified && (
                          <>
                            <button
                              onClick={() => handleEdit(item)}
                              className="text-slate-500 hover:text-blue-600 font-medium transition-colors"
                            >
                              Edit
                            </button>
                            <button
                              onClick={() => onVerify(item.id)}
                              className="text-blue-600 hover:text-blue-800 font-semibold transition-colors flex items-center"
                            >
                              Verify
                            </button>
                          </>
                        )}
                         {item.user_verified && (
                             <button
                              onClick={() => handleEdit(item)}
                              className="text-slate-400 hover:text-blue-600 text-xs transition-colors"
                            >
                              Re-Edit
                            </button>
                         )}
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Legend */}
      <div className="bg-white rounded-lg p-4 border border-slate-200">
        <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
          Confidence Score Legend
        </h3>
        <div className="flex space-x-6 text-sm">
          <div className="flex items-center">
            <span className="w-2.5 h-2.5 bg-emerald-500 rounded-full mr-2"></span>
            <span className="text-slate-600">High Confidence (≥95%)</span>
          </div>
          <div className="flex items-center">
            <span className="w-2.5 h-2.5 bg-amber-500 rounded-full mr-2"></span>
            <span className="text-slate-600">Medium Confidence (85-94%)</span>
          </div>
          <div className="flex items-center">
            <span className="w-2.5 h-2.5 bg-rose-500 rounded-full mr-2"></span>
            <span className="text-slate-600">Low Confidence (Less than 85%)</span>
          </div>
        </div>
      </div>
    </div>
  );
}
